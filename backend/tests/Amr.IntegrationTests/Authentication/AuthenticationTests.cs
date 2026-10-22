using System.Net;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Python;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests.Authentication;

/// <summary>
/// Who may call what, and what the public sign-in endpoints refuse before they reach the database. Identities are deterministic
/// test users (X-Test-User) or the real cookie session. The account flows that need PostgreSQL are in AccountTests.
/// </summary>
public class AuthenticationTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string AnyId = "11111111-1111-1111-1111-111111111111";
    private const string ProfileBody = """{"resistanceProfile":[0,1,0,0,0,0,0]}""";

    internal static HttpClient BrowserClient(AmrApiFactory factory, string? testUser = null, Action<IWebHostBuilder>? configure = null)
    {
        var python = new StubHandler(StubbedPythonHost.Route);
        var host = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureTestServices(services =>
                services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => python));
            configure?.Invoke(builder);
        });
        return BrowserClient(host, testUser);
    }

    internal static HttpClient BrowserClient(WebApplicationFactory<Program> host, string? testUser = null)
    {
        var client = AmrApiFactory.CreateBrowserClient(host);
        if (testUser is not null)
        {
            client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, testUser);
        }

        return client;
    }

    internal static async Task<string> CsrfTokenAsync(HttpClient client) =>
        (await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync()).GetProperty("csrfToken").GetString()!;

    internal static HttpRequestMessage Post(string path, string json, string? csrf = null)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, path) { Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json") };
        if (csrf is not null)
        {
            request.Headers.Add("X-CSRF-TOKEN", csrf);
        }

        return request;
    }

    [Theory]
    [InlineData("GET", "/api/v1/simulations/recent")]
    [InlineData("GET", $"/api/v1/simulations/{AnyId}")]
    [InlineData("GET", $"/api/v1/comparisons/{AnyId}")]
    [InlineData("GET", $"/api/v1/recommendations/{AnyId}")]
    [InlineData("POST", "/api/v1/simulations")]
    [InlineData("POST", "/api/v1/comparisons")]
    [InlineData("POST", "/api/v1/profiles/validate")]
    public async Task Anonymous_requests_to_protected_endpoints_are_401_problems(string method, string path)
    {
        using var client = BrowserClient(factory);
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method == "POST")
        {
            request.Content = new StringContent(ProfileBody, System.Text.Encoding.UTF8, "application/json");
        }

        var response = await client.SendAsync(request);

        var problem = await response.ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
        Assert.Equal("Sign in to continue.", problem.GetProperty("detail").GetString());
        Assert.False(response.Headers.Contains("Location"));
    }

    [Fact]
    public async Task Health_liveness_is_public()
    {
        using var client = BrowserClient(factory);

        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/v1/health/live")).StatusCode);
    }

    [Fact]
    public async Task A_signed_in_user_can_use_protected_endpoints()
    {
        using var client = BrowserClient(factory, "researcher-a");
        var token = await CsrfTokenAsync(client);

        var response = await client.SendAsync(Post("/api/v1/profiles/validate", ProfileBody, token));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task The_session_endpoint_reports_anonymous_visitors_without_an_error()
    {
        using var client = BrowserClient(factory);

        var response = await client.GetAsync("/api/v1/auth/session");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("no-store", response.Headers.CacheControl?.ToString(), StringComparison.Ordinal);
        var session = await response.ReadJsonAsync();
        Assert.False(session.GetProperty("isAuthenticated").GetBoolean());
        Assert.Equal(System.Text.Json.JsonValueKind.Null, session.GetProperty("user").ValueKind);
        Assert.False(string.IsNullOrEmpty(session.GetProperty("csrfToken").GetString()));
    }

    [Fact]
    public async Task The_session_endpoint_reports_the_signed_in_user_and_exposes_no_secrets()
    {
        using var client = BrowserClient(factory, "researcher-a");

        var body = await (await client.GetAsync("/api/v1/auth/session")).Content.ReadAsStringAsync();
        var session = System.Text.Json.JsonDocument.Parse(body).RootElement;

        Assert.True(session.GetProperty("isAuthenticated").GetBoolean());
        Assert.Equal("researcher-a", session.GetProperty("user").GetProperty("displayName").GetString());
        Assert.DoesNotContain("test:researcher-a", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_tampered_or_expired_session_cookie_is_treated_as_signed_out()
    {
        using var client = BrowserClient(factory);
        client.DefaultRequestHeaders.Add("Cookie", "amr.session=CfDJ8-not-a-valid-protected-ticket");

        var session = await (await client.GetAsync("/api/v1/auth/session")).ReadJsonAsync();
        var protectedCall = await client.GetAsync("/api/v1/simulations/recent");

        Assert.False(session.GetProperty("isAuthenticated").GetBoolean());
        await protectedCall.ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
    }

    [Fact]
    public async Task A_state_changing_request_without_the_csrf_token_is_403_even_when_signed_in()
    {
        using var client = BrowserClient(factory, "researcher-a");

        var response = await client.SendAsync(Post("/api/v1/profiles/validate", ProfileBody));

        await response.ReadProblemAsync(HttpStatusCode.Forbidden, "csrf_validation_failed");
    }

    [Fact]
    public async Task A_csrf_token_issued_to_one_user_is_rejected_for_another()
    {
        using var client = BrowserClient(factory, "researcher-a");
        var tokenForA = await CsrfTokenAsync(client);
        client.DefaultRequestHeaders.Remove(TestAuthHandler.UserHeader);
        client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, "researcher-b");

        var response = await client.SendAsync(Post("/api/v1/profiles/validate", ProfileBody, tokenForA));

        await response.ReadProblemAsync(HttpStatusCode.Forbidden, "csrf_validation_failed");
    }

    [Fact]
    public async Task Reads_do_not_need_a_csrf_token()
    {
        using var client = BrowserClient(factory, "researcher-a");

        var response = await client.GetAsync("/api/v1/simulations/recent");

        Assert.NotEqual(HttpStatusCode.Forbidden, response.StatusCode);
        Assert.NotEqual(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/v1/auth/register")]
    [InlineData("/api/v1/auth/sign-in")]
    [InlineData("/api/v1/auth/sign-out")]
    public async Task Sign_in_register_and_sign_out_need_the_csrf_token_too(string path)
    {
        using var client = BrowserClient(factory);

        var response = await client.SendAsync(Post(path, """{"email":"ada@example.org","password":"a long enough password"}"""));

        await response.ReadProblemAsync(HttpStatusCode.Forbidden, "csrf_validation_failed");
    }

    [Theory]
    [InlineData("""{"password":"a long enough password"}""", "email")]
    [InlineData("""{"email":"not-an-email","password":"a long enough password"}""", "email")]
    [InlineData("""{"email":"ada@example","password":"a long enough password"}""", "email")]
    [InlineData("""{"email":" ada@example.org","password":"a long enough password"}""", "email")]
    [InlineData("""{"email":"ada@example.org"}""", "password")]
    [InlineData("""{"email":"ada@example.org","password":"short"}""", "password")]
    [InlineData("""{"email":"ada@example.org","password":"          "}""", "password")]
    public async Task Registration_that_is_not_valid_is_a_422_that_names_the_field_and_never_touches_the_database(string body, string field)
    {
        using var client = BrowserClient(factory);
        var token = await CsrfTokenAsync(client);

        var response = await client.SendAsync(Post("/api/v1/auth/register", body, token));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "validation_failed");
        Assert.True(problem.GetProperty("errors").TryGetProperty(field, out _), problem.ToString());
        Assert.DoesNotContain("a long enough password", problem.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Sign_in_without_an_email_or_password_is_a_422()
    {
        using var client = BrowserClient(factory);
        var token = await CsrfTokenAsync(client);

        var response = await client.SendAsync(Post("/api/v1/auth/sign-in", """{"email":""}""", token));

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, "validation_failed");
    }

    [Fact]
    public async Task Too_many_attempts_from_one_address_are_429_before_any_password_is_checked()
    {
        using var client = BrowserClient(factory, configure: builder =>
            builder.ConfigureAppConfiguration((_, configuration) =>
                configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["Auth:AttemptsPerMinute"] = "2" })));
        var token = await CsrfTokenAsync(client);

        for (var attempt = 0; attempt < 2; attempt++)
        {
            var allowed = await client.SendAsync(Post("/api/v1/auth/sign-in", """{"email":""}""", token));
            Assert.Equal(HttpStatusCode.UnprocessableEntity, allowed.StatusCode);
        }

        var limited = await client.SendAsync(Post("/api/v1/auth/sign-in", """{"email":"ada@example.org","password":"a long enough password"}""", token));

        await limited.ReadProblemAsync(HttpStatusCode.TooManyRequests, "too_many_attempts");
        Assert.True(limited.Headers.Contains("Retry-After"));
    }

    [Fact]
    public async Task The_old_redirect_based_sign_in_routes_no_longer_exist()
    {
        using var client = BrowserClient(factory);

        foreach (var path in new[] { "/api/v1/auth/google/callback", "/api/v1/auth/dev-sign-in" })
        {
            var response = await client.GetAsync(path);
            Assert.True(response.StatusCode is HttpStatusCode.NotFound or HttpStatusCode.Unauthorized, response.StatusCode.ToString());
            Assert.False(response.Headers.Contains("Set-Cookie"));
        }
    }
}
