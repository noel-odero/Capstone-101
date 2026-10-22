using System.Security.Claims;
using Amr.Api.Authentication;
using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.Errors;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace Amr.Api.Controllers;

/// <summary>Email-and-password accounts and the cookie session. These routes are public on purpose; everything else requires a signed-in user.</summary>
[Route(ApiRoutes.Auth)]
[AllowAnonymous]
public sealed class AuthController(AccountService accounts, IAntiforgery antiforgery) : ApiControllerBase
{
    [HttpGet("session")]
    [ProducesResponseType<SessionDto>(StatusCodes.Status200OK)]
    public SessionDto GetSession()
    {
        Response.Headers.CacheControl = "no-store";
        return BuildSession(User);
    }

    [HttpPost("register")]
    [EnableRateLimiting(AmrAuthentication.RateLimitPolicy)]
    [ProducesResponseType<SessionDto>(StatusCodes.Status201Created)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status409Conflict, AmrProblemDetails.ContentType)]
    public async Task<IActionResult> Register(RegisterRequest request, CancellationToken cancellationToken)
    {
        var outcome = await accounts.RegisterAsync(request.Email!, request.Password!, request.DisplayName, cancellationToken);
        if (outcome.User is null)
        {
            return Problem(StatusCodes.Status409Conflict, ErrorCodes.EmailAlreadyRegistered, "An account with this email already exists. Sign in instead.");
        }

        Response.Headers.CacheControl = "no-store";
        return StatusCode(StatusCodes.Status201Created, await StartSessionAsync(outcome.User));
    }

    [HttpPost("sign-in")]
    [EnableRateLimiting(AmrAuthentication.RateLimitPolicy)]
    [ProducesResponseType<SessionDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status401Unauthorized, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status429TooManyRequests, AmrProblemDetails.ContentType)]
    public async Task<IActionResult> SignIn(SignInRequest request, CancellationToken cancellationToken)
    {
        var outcome = await accounts.SignInAsync(request.Email!, request.Password!, cancellationToken);
        Response.Headers.CacheControl = "no-store";

        if (outcome.Status == AccountStatus.LockedOut)
        {
            var minutes = Math.Max(1, (int)Math.Ceiling(outcome.RetryAfter!.Value.TotalMinutes));
            Response.Headers.RetryAfter = ((int)Math.Ceiling(outcome.RetryAfter.Value.TotalSeconds)).ToString(System.Globalization.CultureInfo.InvariantCulture);
            return Problem(StatusCodes.Status429TooManyRequests, ErrorCodes.TooManyAttempts, $"Too many failed attempts. Try again in {minutes} minute{(minutes == 1 ? string.Empty : "s")}.");
        }

        if (outcome.User is null)
        {
            return Problem(StatusCodes.Status401Unauthorized, ErrorCodes.InvalidCredentials, "The email or password is incorrect.");
        }

        return Ok(await StartSessionAsync(outcome.User));
    }

    [HttpPost("sign-out")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<IActionResult> SignOutSession(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        await HttpContext.SignOutAsync(AmrAuthentication.CookieScheme);
        return NoContent();
    }

    private async Task<SessionDto> StartSessionAsync(Application.Interfaces.Identity.UserAccount user)
    {
        var principal = AmrAuthentication.CreatePrincipal(user);
        await HttpContext.SignInAsync(AmrAuthentication.CookieScheme, principal);
        HttpContext.User = principal; // so the CSRF token issued below is bound to the new identity
        return BuildSession(principal);
    }

    private SessionDto BuildSession(ClaimsPrincipal principal)
    {
        var authenticated = principal.Identity?.IsAuthenticated == true;
        var token = antiforgery.GetAndStoreTokens(HttpContext).RequestToken ?? string.Empty;
        return new SessionDto(
            authenticated,
            authenticated ? new SessionUserDto(principal.FindFirstValue(ClaimTypes.Name) ?? "Signed-in user", principal.FindFirstValue(ClaimTypes.Email) ?? string.Empty) : null,
            token);
    }

    private ObjectResult Problem(int status, string code, string detail) =>
        AmrProblemDetails.ToResult(AmrProblemDetails.Create(HttpContext, status, code, detail));
}
