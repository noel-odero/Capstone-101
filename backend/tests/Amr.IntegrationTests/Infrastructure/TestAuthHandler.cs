using System.Security.Claims;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>
/// Deterministic identities for tests that are not about accounts. A request carrying X-Test-User is authenticated as
/// "test:{value}"; without it the real cookie session applies. AccountTests use real registration and sign-in instead.
/// </summary>
public sealed class TestAuthHandler(IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger, UrlEncoder encoder)
    : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string SchemeName = "Test";
    public const string PolicyScheme = "TestOrCookie";
    public const string UserHeader = "X-Test-User";
    public const string BypassCsrfHeader = "X-Test-Bypass-Csrf";

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue(UserHeader, out var user) || string.IsNullOrWhiteSpace(user))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.NameIdentifier, $"test:{user}"), new Claim(ClaimTypes.Name, user.ToString())],
            SchemeName);
        return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), SchemeName)));
    }
}

/// <summary>The real antiforgery service, except that requests marked as ordinary-test traffic skip validation; CSRF tests omit the marker.</summary>
internal sealed class BypassableAntiforgery(IAntiforgery inner) : IAntiforgery
{
    private static bool Bypass(HttpContext context) => context.Request.Headers.ContainsKey(TestAuthHandler.BypassCsrfHeader);

    public AntiforgeryTokenSet GetAndStoreTokens(HttpContext httpContext) => inner.GetAndStoreTokens(httpContext);

    public AntiforgeryTokenSet GetTokens(HttpContext httpContext) => inner.GetTokens(httpContext);

    public Task<bool> IsRequestValidAsync(HttpContext httpContext) => Bypass(httpContext) ? Task.FromResult(true) : inner.IsRequestValidAsync(httpContext);

    public Task ValidateRequestAsync(HttpContext httpContext) => Bypass(httpContext) ? Task.CompletedTask : inner.ValidateRequestAsync(httpContext);

    public void SetCookieTokenAndHeader(HttpContext httpContext) => inner.SetCookieTokenAndHeader(httpContext);
}
