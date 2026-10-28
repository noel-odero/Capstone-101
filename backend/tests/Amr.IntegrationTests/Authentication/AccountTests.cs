using System.Net;
using System.Text.Json;
using System.Collections.Concurrent;
using System.Security.Claims;
using Amr.Api.Authentication;
using Amr.Infrastructure.Persistence.Entities;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Python;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Amr.IntegrationTests.Authentication;

/// <summary>
/// Real accounts end to end: registration, cookie sessions, lockout and per-user ownership, on real PostgreSQL with real
/// password hashing. No identity is faked here. Needs AMR_TEST_POSTGRES.
/// </summary>
public class AccountTests(AmrApiFactory factory, PostgresDatabaseFixture db) : IClassFixture<AmrApiFactory>, IClassFixture<PostgresDatabaseFixture>
{
    private const string Password = "a long enough password";
    private const string CompareBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";
    private readonly TestEmailSender emails = new();
    private readonly TestClock clock = new();

    private sealed class TestClock : TimeProvider
    {
        public DateTimeOffset Now { get; set; } = DateTimeOffset.UtcNow;
        public override DateTimeOffset GetUtcNow() => Now;
    }

    private sealed class TestEmailSender : IVerificationEmailSender
    {
        public ConcurrentDictionary<string, string> Codes { get; } = new(StringComparer.OrdinalIgnoreCase);
        public bool Fail { get; set; }
        public void EnsureConfigured() { }
        public Task SendAsync(string recipient, string code, CancellationToken cancellationToken)
        {
            if (Fail) throw new Amr.Application.Errors.AmrException(Amr.Application.Errors.ErrorCategory.DependencyUnavailable,
                "verification_unavailable", "Verification email is temporarily unavailable.");
            Codes[recipient] = code;
            return Task.CompletedTask;
        }
    }

    private WebApplicationFactory<Program> Host(Dictionary<string, string?>? settings = null) =>
        factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureAppConfiguration((_, configuration) =>
            {
                configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["ConnectionStrings:Amr"] = db.ConnectionString });
                if (settings is not null)
                {
                    configuration.AddInMemoryCollection(settings);
                }
            });
            builder.ConfigureTestServices(services =>
            {
                services.AddSingleton<IVerificationEmailSender>(emails);
                services.AddSingleton<TimeProvider>(clock);
                services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => new StubHandler(StubbedPythonHost.Route));
            });
        });

    private static string NewEmail() => $"user-{Guid.NewGuid():N}@example.org";

    private static string Credentials(string email, string password = Password, string? name = null) =>
        name is null ? JsonSerializer.Serialize(new { email, password }) : JsonSerializer.Serialize(new { email, password, displayName = name });

    private static async Task<HttpResponseMessage> BeginRegistrationAsync(HttpClient client, string email, string password = Password, string? name = null) =>
        await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/register", Credentials(email, password, name), await AuthenticationTests.CsrfTokenAsync(client)));

    private async Task<HttpResponseMessage> RegisterAsync(HttpClient client, string email, string password = Password, string? name = null)
    {
        var pending = await BeginRegistrationAsync(client, email, password, name);
        Assert.Equal(HttpStatusCode.Accepted, pending.StatusCode);
        var ticket = (await pending.ReadJsonAsync()).GetProperty("challengeToken").GetString()!;
        return await VerifyAsync(client, ticket, emails.Codes[email]);
    }

    private static async Task<HttpResponseMessage> VerifyAsync(HttpClient client, string ticket, string code) =>
        await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/verify-email",
            JsonSerializer.Serialize(new { challengeToken = ticket, code }), await AuthenticationTests.CsrfTokenAsync(client)));

    private static async Task<HttpResponseMessage> SignInAsync(HttpClient client, string email, string password = Password) =>
        await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/sign-in", Credentials(email, password), await AuthenticationTests.CsrfTokenAsync(client)));

    private static async Task SignOutAsync(HttpClient client) =>
        Assert.Equal(HttpStatusCode.NoContent, (await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/sign-out", "{}", await AuthenticationTests.CsrfTokenAsync(client)))).StatusCode);

    private static async Task<Guid> CreateComparisonAsync(HttpClient client)
    {
        var response = await client.SendAsync(AuthenticationTests.Post("/api/v1/comparisons", CompareBody, await AuthenticationTests.CsrfTokenAsync(client)));
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        return (await response.ReadJsonAsync()).GetProperty("id").GetGuid();
    }

    [PostgresFact]
    public async Task Verifying_creates_the_account_signs_the_user_in_and_stores_only_a_password_hash()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();

        var response = await RegisterAsync(client, email, Password, "Ada Researcher");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("no-store", response.Headers.CacheControl?.ToString(), StringComparison.Ordinal);
        var cookie = response.Headers.GetValues("Set-Cookie").Single(value => value.StartsWith("amr.session=", StringComparison.Ordinal));
        Assert.Contains("httponly", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("samesite=lax", cookie, StringComparison.OrdinalIgnoreCase);

        var body = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain(Password, body, StringComparison.Ordinal);
        Assert.DoesNotContain("passwordHash", body, StringComparison.OrdinalIgnoreCase);
        var session = JsonDocument.Parse(body).RootElement;
        Assert.True(session.GetProperty("isAuthenticated").GetBoolean());
        Assert.Equal("Ada Researcher", session.GetProperty("user").GetProperty("displayName").GetString());
        Assert.Equal(email, session.GetProperty("user").GetProperty("email").GetString());

        var current = await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync();
        Assert.True(current.GetProperty("isAuthenticated").GetBoolean());
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/v1/simulations/recent")).StatusCode);

        await using var context = db.CreateContext();
        var stored = await context.Users.SingleAsync(user => user.NormalizedEmail == email);
        Assert.NotEqual(Password, stored.PasswordHash);
        Assert.DoesNotContain(Password, stored.PasswordHash, StringComparison.Ordinal);
        Assert.NotNull(stored.EmailVerifiedAtUtc);
    }

    [PostgresFact]
    public async Task The_token_returned_at_sign_in_works_and_the_anonymous_one_does_not()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var anonymousToken = await AuthenticationTests.CsrfTokenAsync(client);
        var registered = await RegisterAsync(client, NewEmail());
        var signedInToken = (await registered.ReadJsonAsync()).GetProperty("csrfToken").GetString()!;
        const string body = """{"resistanceProfile":[0,1,0,0,0,0,0]}""";

        var withOld = await client.SendAsync(AuthenticationTests.Post("/api/v1/profiles/validate", body, anonymousToken));
        var withNew = await client.SendAsync(AuthenticationTests.Post("/api/v1/profiles/validate", body, signedInToken));

        await withOld.ReadProblemAsync(HttpStatusCode.Forbidden, "csrf_validation_failed");
        Assert.Equal(HttpStatusCode.OK, withNew.StatusCode);
    }

    [PostgresFact]
    public async Task An_email_can_be_registered_only_once_whatever_its_case_or_spacing()
    {
        var host = Host();
        using var first = AuthenticationTests.BrowserClient(host);
        using var second = AuthenticationTests.BrowserClient(host);
        var email = NewEmail();
        Assert.Equal(HttpStatusCode.OK, (await RegisterAsync(first, email)).StatusCode);

        var again = await BeginRegistrationAsync(second, email.ToUpperInvariant(), "another long password");

        Assert.Equal(HttpStatusCode.Accepted, again.StatusCode);
        Assert.False((await again.ReadJsonAsync()).TryGetProperty("isAuthenticated", out _));
        Assert.False((await (await second.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("isAuthenticated").GetBoolean());
    }

    [PostgresFact]
    public async Task Signing_out_ends_the_session_and_signing_in_again_restores_it()
    {
        var host = Host();
        using var client = AuthenticationTests.BrowserClient(host);
        var email = NewEmail();
        await RegisterAsync(client, email);

        await SignOutAsync(client);

        Assert.False((await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("isAuthenticated").GetBoolean());
        await (await client.GetAsync("/api/v1/simulations/recent")).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");

        var signedIn = await SignInAsync(client, email.ToUpperInvariant());

        Assert.Equal(HttpStatusCode.OK, signedIn.StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/v1/simulations/recent")).StatusCode);
    }

    [PostgresFact]
    public async Task A_wrong_password_and_an_unknown_email_get_the_same_401_and_no_session()
    {
        var host = Host();
        using var client = AuthenticationTests.BrowserClient(host);
        var email = NewEmail();
        await RegisterAsync(client, email);
        await SignOutAsync(client);

        var wrongPassword = await SignInAsync(client, email, "definitely not it");
        var unknownEmail = await SignInAsync(client, NewEmail());

        var first = await wrongPassword.ReadProblemAsync(HttpStatusCode.Unauthorized, "invalid_credentials");
        var second = await unknownEmail.ReadProblemAsync(HttpStatusCode.Unauthorized, "invalid_credentials");
        Assert.Equal(first.GetProperty("detail").GetString(), second.GetProperty("detail").GetString());
        Assert.Equal("The email or password is incorrect.", first.GetProperty("detail").GetString());
        Assert.False((await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("isAuthenticated").GetBoolean());
        Assert.False(wrongPassword.Headers.Contains("Set-Cookie") && wrongPassword.Headers.GetValues("Set-Cookie").Any(value => value.StartsWith("amr.session=", StringComparison.Ordinal)));
    }

    [PostgresFact]
    public async Task Repeated_wrong_passwords_lock_the_account_with_a_429_and_retry_after()
    {
        var host = Host(new Dictionary<string, string?> { ["Auth:MaxFailedSignIns"] = "3", ["Auth:LockoutMinutes"] = "10" });
        using var client = AuthenticationTests.BrowserClient(host);
        var email = NewEmail();
        await RegisterAsync(client, email);
        await SignOutAsync(client);

        for (var attempt = 0; attempt < 3; attempt++)
        {
            await (await SignInAsync(client, email, "wrong password!")).ReadProblemAsync(HttpStatusCode.Unauthorized, "invalid_credentials");
        }

        var locked = await SignInAsync(client, email);

        var problem = await locked.ReadProblemAsync(HttpStatusCode.TooManyRequests, "too_many_attempts");
        Assert.Contains("10 minutes", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
        Assert.True(int.Parse(locked.Headers.GetValues("Retry-After").Single(), System.Globalization.CultureInfo.InvariantCulture) > 0);
        Assert.False((await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("isAuthenticated").GetBoolean());
    }

    [PostgresFact]
    public async Task Each_user_sees_only_their_own_runs()
    {
        var host = Host();
        using var ada = AuthenticationTests.BrowserClient(host);
        using var grace = AuthenticationTests.BrowserClient(host);
        await RegisterAsync(ada, NewEmail());
        await RegisterAsync(grace, NewEmail());

        var comparison = await CreateComparisonAsync(ada);

        Assert.Equal(HttpStatusCode.OK, (await ada.GetAsync($"/api/v1/comparisons/{comparison}")).StatusCode);
        await (await grace.GetAsync($"/api/v1/comparisons/{comparison}")).ReadProblemAsync(HttpStatusCode.NotFound, "not_found");
        var graceRuns = await (await grace.GetAsync("/api/v1/simulations/recent?page=1&pageSize=50")).ReadJsonAsync();
        Assert.Equal(0, graceRuns.GetProperty("totalCount").GetInt32());
        var adaRuns = await (await ada.GetAsync("/api/v1/simulations/recent?page=1&pageSize=50")).ReadJsonAsync();
        Assert.Equal(1, adaRuns.GetProperty("totalCount").GetInt32());

        await using var context = db.CreateContext();
        var owner = (await context.ExperimentRuns.SingleAsync(run => run.Id == comparison)).OwnerId;
        Assert.True(Guid.TryParse(owner, out _), owner);
    }

    [PostgresFact]
    public async Task Registration_does_not_create_an_account_or_session_before_email_ownership_is_proven()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();
        var response = await BeginRegistrationAsync(client, email);
        Assert.Equal(HttpStatusCode.Accepted, response.StatusCode);
        var body = await response.ReadJsonAsync();
        Assert.False(body.TryGetProperty("code", out _));
        Assert.False(body.TryGetProperty("passwordHash", out _));
        Assert.False(response.Headers.TryGetValues("Set-Cookie", out var cookies) && cookies.Any(value => value.StartsWith("amr.session=", StringComparison.Ordinal)));
        await (await client.GetAsync("/api/v1/simulations/recent")).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
        await using var context = db.CreateContext();
        Assert.False(await context.Users.AnyAsync(user => user.NormalizedEmail == email));
        var pending = await context.EmailVerifications.SingleAsync(value => value.NormalizedEmail == email);
        Assert.NotEqual(body.GetProperty("challengeToken").GetString(), pending.TicketHash);
        Assert.NotEqual(emails.Codes[email], pending.CodeHash);
        Assert.NotEqual(Password, pending.PasswordHash);
    }

    [PostgresFact]
    public async Task Wrong_codes_are_limited_and_resending_replaces_the_old_ticket_and_code()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();
        var pending = await (await BeginRegistrationAsync(client, email)).ReadJsonAsync();
        var ticket = pending.GetProperty("challengeToken").GetString()!;
        var correct = emails.Codes[email];
        var wrong = correct == "000000" ? "000001" : "000000";
        for (var attempt = 0; attempt < 5; attempt++)
            await (await VerifyAsync(client, ticket, wrong)).ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "invalid_verification_code");
        await (await VerifyAsync(client, ticket, correct)).ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "invalid_verification_code");
        var resendBody = JsonSerializer.Serialize(new { challengeToken = ticket });
        await (await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/resend-verification", resendBody,
            await AuthenticationTests.CsrfTokenAsync(client)))).ReadProblemAsync(HttpStatusCode.TooManyRequests, "verification_rate_limited");
        clock.Now += TimeSpan.FromMinutes(1);
        var resent = await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/resend-verification", resendBody,
            await AuthenticationTests.CsrfTokenAsync(client)));
        Assert.Equal(HttpStatusCode.Accepted, resent.StatusCode);
        var newTicket = (await resent.ReadJsonAsync()).GetProperty("challengeToken").GetString()!;
        Assert.NotEqual(ticket, newTicket);
        await (await VerifyAsync(client, ticket, correct)).ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "invalid_verification_code");
        Assert.Equal(HttpStatusCode.OK, (await VerifyAsync(client, newTicket, emails.Codes[email])).StatusCode);
        await (await VerifyAsync(client, newTicket, emails.Codes[email])).ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "invalid_verification_code");
    }

    [PostgresFact]
    public async Task Codes_expire_and_the_recipient_send_limit_survives_a_new_host()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();
        var pending = await (await BeginRegistrationAsync(client, email)).ReadJsonAsync();
        var ticket = pending.GetProperty("challengeToken").GetString()!;
        clock.Now += TimeSpan.FromMinutes(10);
        await (await VerifyAsync(client, ticket, emails.Codes[email])).ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "verification_code_expired");
        for (var send = 1; send < 5; send++)
        {
            clock.Now += TimeSpan.FromMinutes(1);
            var resent = await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/resend-verification",
                JsonSerializer.Serialize(new { challengeToken = ticket }), await AuthenticationTests.CsrfTokenAsync(client)));
            Assert.Equal(HttpStatusCode.Accepted, resent.StatusCode);
            ticket = (await resent.ReadJsonAsync()).GetProperty("challengeToken").GetString()!;
        }
        clock.Now += TimeSpan.FromMinutes(1);
        using var restarted = AuthenticationTests.BrowserClient(Host());
        await (await BeginRegistrationAsync(restarted, email)).ReadProblemAsync(HttpStatusCode.TooManyRequests, "verification_rate_limited");
        Assert.Equal(HttpStatusCode.OK, (await VerifyAsync(restarted, ticket, emails.Codes[email])).StatusCode);
    }

    [PostgresFact]
    public async Task An_existing_unverified_account_keeps_its_id_and_must_verify_after_password_authentication()
    {
        var email = NewEmail();
        var id = Guid.NewGuid();
        await using (var context = db.CreateContext())
        {
            context.Users.Add(new AppUser
            {
                Id = id, Email = email, NormalizedEmail = email, DisplayName = "Existing researcher",
                PasswordHash = new PasswordService().Hash(Password), CreatedAtUtc = clock.Now,
            });
            await context.SaveChangesAsync();
        }
        using var client = AuthenticationTests.BrowserClient(Host());
        await (await SignInAsync(client, email, "incorrect password")).ReadProblemAsync(HttpStatusCode.Unauthorized, "invalid_credentials");
        Assert.False(emails.Codes.ContainsKey(email));
        var signedIn = await SignInAsync(client, email);
        Assert.Equal(HttpStatusCode.Accepted, signedIn.StatusCode);
        await (await client.GetAsync("/api/v1/simulations/recent")).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
        var ticket = (await signedIn.ReadJsonAsync()).GetProperty("challengeToken").GetString()!;
        Assert.Equal(HttpStatusCode.OK, (await VerifyAsync(client, ticket, emails.Codes[email])).StatusCode);
        await using var stored = db.CreateContext();
        var user = await stored.Users.SingleAsync(value => value.NormalizedEmail == email);
        Assert.Equal(id, user.Id);
        Assert.NotNull(user.EmailVerifiedAtUtc);
    }

    [PostgresFact]
    public async Task Concurrent_verification_consumes_a_code_only_once()
    {
        var host = Host();
        using var first = AuthenticationTests.BrowserClient(host);
        using var second = AuthenticationTests.BrowserClient(host);
        var email = NewEmail();
        var ticket = (await (await BeginRegistrationAsync(first, email)).ReadJsonAsync()).GetProperty("challengeToken").GetString()!;
        var results = await Task.WhenAll(VerifyAsync(first, ticket, emails.Codes[email]), VerifyAsync(second, ticket, emails.Codes[email]));
        Assert.Single(results, response => response.StatusCode == HttpStatusCode.OK);
        Assert.Single(results, response => response.StatusCode == HttpStatusCode.UnprocessableEntity);
        await using var context = db.CreateContext();
        Assert.Equal(1, await context.Users.CountAsync(user => user.NormalizedEmail == email));
    }

    [PostgresFact]
    public async Task Email_delivery_failure_cannot_create_or_authenticate_an_account()
    {
        emails.Fail = true;
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();
        await (await BeginRegistrationAsync(client, email)).ReadProblemAsync(HttpStatusCode.ServiceUnavailable, "verification_unavailable");
        await (await SignInAsync(client, email)).ReadProblemAsync(HttpStatusCode.Unauthorized, "invalid_credentials");
        await using var context = db.CreateContext();
        Assert.False(await context.Users.AnyAsync(user => user.NormalizedEmail == email));
        var pending = await context.EmailVerifications.SingleAsync(value => value.NormalizedEmail == email);
        Assert.Null(pending.TicketHash);
        Assert.Null(pending.CodeHash);
        Assert.Null(pending.PasswordHash);
    }

    [PostgresFact]
    public async Task A_cookie_issued_before_email_verification_was_required_cannot_access_the_workspace()
    {
        var host = Host();
        using var client = AuthenticationTests.BrowserClient(host);
        var options = host.Services.GetRequiredService<IOptionsMonitor<CookieAuthenticationOptions>>().Get(AmrAuthentication.CookieScheme);
        var principal = new ClaimsPrincipal(new ClaimsIdentity(
            [new Claim(ClaimTypes.NameIdentifier, Guid.NewGuid().ToString())], AmrAuthentication.CookieScheme));
        var properties = new AuthenticationProperties { IssuedUtc = clock.Now, ExpiresUtc = clock.Now.AddHours(1) };
        var cookie = options.TicketDataFormat.Protect(new AuthenticationTicket(principal, properties, AmrAuthentication.CookieScheme));
        client.DefaultRequestHeaders.Add("Cookie", "amr.session=" + cookie);

        await (await client.GetAsync("/api/v1/simulations/recent")).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
        Assert.False((await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("isAuthenticated").GetBoolean());
    }
}
