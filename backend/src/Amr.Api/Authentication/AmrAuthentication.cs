using System.Security.Claims;
using System.Threading.RateLimiting;
using Amr.Api.Errors;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Options;

namespace Amr.Api.Authentication;

public static class AmrAuthentication
{
    public const string CookieScheme = CookieAuthenticationDefaults.AuthenticationScheme;
    public const string RateLimitPolicy = "auth-attempts";
    public const string VerifiedEmailClaim = "amr.email_verified";

    /// <summary>
    /// Cookie sessions for email-and-password accounts. Every endpoint requires a signed-in user unless it opts out explicitly,
    /// and every state-changing request needs the antiforgery header (see <see cref="CsrfValidationFilter"/>).
    /// </summary>
    public static IServiceCollection AddAmrAuthentication(this IServiceCollection services, IConfiguration configuration, IHostEnvironment environment)
    {
        // Bound when first used: host configuration (deployment settings, test settings) can arrive after registration.
        services.AddOptions<AuthOptions>().Bind(configuration.GetSection(AuthOptions.SectionName));
        services.AddSingleton(provider => provider.GetRequiredService<IOptions<AuthOptions>>().Value);

        var securePolicy = environment.IsDevelopment() ? CookieSecurePolicy.SameAsRequest : CookieSecurePolicy.Always;

        services.AddAuthentication(scheme =>
            {
                scheme.DefaultScheme = CookieScheme;
                scheme.DefaultChallengeScheme = CookieScheme;
            })
            .AddCookie(CookieScheme, cookie =>
            {
                cookie.Cookie.Name = "amr.session";
                cookie.Cookie.HttpOnly = true;
                cookie.Cookie.SecurePolicy = securePolicy;
                cookie.Cookie.SameSite = SameSiteMode.Lax;
                cookie.SlidingExpiration = false;
                cookie.Events.OnValidatePrincipal = async context =>
                {
                    if (!context.Principal!.HasClaim(VerifiedEmailClaim, "true"))
                    {
                        context.RejectPrincipal();
                        await context.HttpContext.SignOutAsync(CookieScheme);
                    }
                };
                cookie.Events.OnRedirectToLogin = context =>
                    WriteProblemAsync(context.HttpContext, StatusCodes.Status401Unauthorized, ErrorCodes.AuthenticationRequired, "Sign in to continue.");
                cookie.Events.OnRedirectToAccessDenied = context =>
                    WriteProblemAsync(context.HttpContext, StatusCodes.Status403Forbidden, ErrorCodes.AccessDenied, "You do not have access to this resource.");
            });
        services.AddOptions<CookieAuthenticationOptions>(CookieScheme).Configure<IOptions<AuthOptions>>((cookie, auth) =>
            cookie.ExpireTimeSpan = TimeSpan.FromHours(Math.Clamp(auth.Value.SessionHours, 1, 72)));

        services.AddAuthorization(authorization =>
            authorization.FallbackPolicy = new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build());

        services.AddAntiforgery(antiforgery =>
        {
            antiforgery.HeaderName = "X-CSRF-TOKEN";
            antiforgery.Cookie.Name = "amr.csrf";
            antiforgery.Cookie.HttpOnly = true;
            antiforgery.Cookie.SameSite = SameSiteMode.Strict;
            antiforgery.Cookie.SecurePolicy = securePolicy;
        });

        // Per client address, so guessing passwords across many accounts is slowed as well as guessing against one.
        services.AddRateLimiter(limiter =>
        {
            limiter.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
            limiter.AddPolicy(RateLimitPolicy, context => RateLimitPartition.GetFixedWindowLimiter(
                context.Connection.RemoteIpAddress?.ToString() ?? "unknown",
                _ => new FixedWindowRateLimiterOptions
                {
                    PermitLimit = Math.Max(1, context.RequestServices.GetRequiredService<AuthOptions>().AttemptsPerMinute),
                    Window = TimeSpan.FromMinutes(1),
                    QueueLimit = 0,
                }));
            limiter.OnRejected = (context, cancellationToken) =>
            {
                context.HttpContext.Response.Headers.RetryAfter = "60";
                return new ValueTask(WriteProblemAsync(context.HttpContext, StatusCodes.Status429TooManyRequests, ErrorCodes.TooManyAttempts, "Too many attempts. Wait a minute and try again."));
            };
        });

        services.AddSingleton<PasswordService>();
        services.AddScoped<AccountService>();
        services.AddOptions<VerificationEmailOptions>().Bind(configuration.GetSection("VerificationEmail"));
        services.AddScoped<IVerificationEmailSender, AzureVerificationEmailSender>();
        services.AddScoped<EmailVerificationService>();
        services.AddHttpContextAccessor();
        services.AddScoped<ICurrentUser, HttpContextCurrentUser>();
        return services;
    }

    /// <summary>The cookie carries the user id (the owner key for stored runs), the display name and the email; nothing else.</summary>
    public static ClaimsPrincipal CreatePrincipal(UserAccount user)
    {
        if (user.EmailVerifiedAtUtc is null)
        {
            throw new InvalidOperationException("Email ownership must be verified before starting a session.");
        }
        var identity = new ClaimsIdentity(CookieScheme, ClaimTypes.Name, ClaimTypes.Role);
        identity.AddClaim(new Claim(ClaimTypes.NameIdentifier, user.Id.ToString("D")));
        identity.AddClaim(new Claim(ClaimTypes.Name, user.DisplayName));
        identity.AddClaim(new Claim(ClaimTypes.Email, user.Email));
        identity.AddClaim(new Claim(VerifiedEmailClaim, "true"));
        return new ClaimsPrincipal(identity);
    }

    private static Task WriteProblemAsync(HttpContext context, int status, string code, string detail)
    {
        context.Response.StatusCode = status;
        return context.Response.WriteAsJsonAsync(
            AmrProblemDetails.Create(context, status, code, detail),
            options: null,
            contentType: AmrProblemDetails.ContentType,
            context.RequestAborted);
    }
}
