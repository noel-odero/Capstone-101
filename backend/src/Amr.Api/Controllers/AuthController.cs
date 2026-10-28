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
public sealed class AuthController(AccountService accounts, EmailVerificationService verification, IAntiforgery antiforgery) : ApiControllerBase
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
    [ProducesResponseType<VerificationRequiredDto>(StatusCodes.Status202Accepted)]
    public Task<IActionResult> Register(RegisterRequest request, CancellationToken cancellationToken) =>
        BeginVerificationAsync(() => verification.RegisterAsync(request, cancellationToken));

    [HttpPost("verify-email")]
    [EnableRateLimiting(AmrAuthentication.RateLimitPolicy)]
    [ProducesResponseType<SessionDto>(StatusCodes.Status200OK)]
    public async Task<IActionResult> VerifyEmail(VerifyEmailRequest request, CancellationToken cancellationToken)
    {
        Response.Headers.CacheControl = "no-store";
        var user = await verification.VerifyAsync(request.ChallengeToken!, request.Code!, cancellationToken);
        return Ok(await StartSessionAsync(user));
    }

    [HttpPost("resend-verification")]
    [EnableRateLimiting(AmrAuthentication.RateLimitPolicy)]
    [ProducesResponseType<VerificationRequiredDto>(StatusCodes.Status202Accepted)]
    public Task<IActionResult> ResendVerification(ResendVerificationRequest request, CancellationToken cancellationToken) =>
        BeginVerificationAsync(() => verification.ResendAsync(request.ChallengeToken!, cancellationToken));

    [HttpPost("sign-in")]
    [EnableRateLimiting(AmrAuthentication.RateLimitPolicy)]
    [ProducesResponseType<SessionDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<VerificationRequiredDto>(StatusCodes.Status202Accepted)]
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

        if (outcome.Status == AccountStatus.EmailUnverified)
        {
            return await BeginVerificationAsync(() => verification.ForExistingAccountAsync(outcome.User, cancellationToken));
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

    private async Task<IActionResult> BeginVerificationAsync(Func<Task<VerificationRequiredDto>> begin)
    {
        Response.Headers.CacheControl = "no-store";
        try
        {
            return Accepted(await begin());
        }
        catch (AmrException exception) when (exception.Code == ErrorCodes.VerificationRateLimited)
        {
            Response.Headers.RetryAfter = "60";
            return Problem(StatusCodes.Status429TooManyRequests, exception.Code, exception.Message);
        }
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
