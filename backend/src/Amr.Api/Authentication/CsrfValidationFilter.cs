using Amr.Api.Errors;
using Amr.Application.Errors;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Mvc.Filters;

namespace Amr.Api.Authentication;

/// <summary>
/// Cookie sessions are sent automatically by the browser, so every state-changing request must also carry the antiforgery
/// header obtained from GET /auth/session, including sign-in and registration (an anonymous token), which guards against login CSRF.
/// </summary>
public sealed class CsrfValidationFilter(IAntiforgery antiforgery) : IAsyncAuthorizationFilter
{
    public async Task OnAuthorizationAsync(AuthorizationFilterContext context)
    {
        var method = context.HttpContext.Request.Method;
        if (HttpMethods.IsGet(method) || HttpMethods.IsHead(method) || HttpMethods.IsOptions(method) || HttpMethods.IsTrace(method))
        {
            return;
        }

        try
        {
            await antiforgery.ValidateRequestAsync(context.HttpContext);
        }
        catch (AntiforgeryValidationException)
        {
            context.Result = AmrProblemDetails.ToResult(
                AmrProblemDetails.Create(context.HttpContext, StatusCodes.Status403Forbidden, ErrorCodes.CsrfValidationFailed, CsrfMessage));
        }
    }

    public const string CsrfMessage = "The request could not be verified. Reload the page and try again.";
}
