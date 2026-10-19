using System.Net;
using System.Text.Json;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Python;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests.Authentication;

/// <summary>
/// Real accounts end to end: registration, cookie sessions, lockout and per-user ownership, on real PostgreSQL with real
/// password hashing. No identity is faked here. Needs AMR_TEST_POSTGRES.
/// </summary>
public class AccountTests(AmrApiFactory factory, PostgresDatabaseFixture db) : IClassFixture<AmrApiFactory>, IClassFixture<PostgresDatabaseFixture>
{
    private const string Password = "a long enough password";
    private const string CompareBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";

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
                services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => new StubHandler(StubbedPythonHost.Route)));
        });

    private static string NewEmail() => $"user-{Guid.NewGuid():N}@example.org";

    private static string Credentials(string email, string password = Password, string? name = null) =>
        name is null ? JsonSerializer.Serialize(new { email, password }) : JsonSerializer.Serialize(new { email, password, displayName = name });

    private static async Task<HttpResponseMessage> RegisterAsync(HttpClient client, string email, string password = Password, string? name = null) =>
        await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/register", Credentials(email, password, name), await AuthenticationTests.CsrfTokenAsync(client)));

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
    public async Task Registering_creates_an_account_signs_the_user_in_and_stores_only_a_password_hash()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var email = NewEmail();

        var response = await RegisterAsync(client, email, Password, "Ada Researcher");

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
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
    }

    [PostgresFact]
    public async Task The_token_returned_at_sign_in_works_and_the_anonymous_one_does_not()
    {
        using var client = AuthenticationTests.BrowserClient(Host());
        var anonymousToken = await AuthenticationTests.CsrfTokenAsync(client);
        var registered = await client.SendAsync(AuthenticationTests.Post("/api/v1/auth/register", Credentials(NewEmail()), anonymousToken));
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
        Assert.Equal(HttpStatusCode.Created, (await RegisterAsync(first, email)).StatusCode);

        var again = await RegisterAsync(second, email.ToUpperInvariant(), "another long password");

        var problem = await again.ReadProblemAsync(HttpStatusCode.Conflict, "email_already_registered");
        Assert.Contains("already exists", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
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
}
