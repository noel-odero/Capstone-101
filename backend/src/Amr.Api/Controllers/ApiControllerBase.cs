using Amr.Api.Errors;
using Amr.Api.Routing;
using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

/// <summary>Common conventions: API behavior, version 1, and a problem body for unexpected failures. Controllers only translate HTTP to application calls.</summary>
[ApiController]
[ApiVersion(ApiRoutes.Version1)]
[ProducesResponseType<ProblemDetails>(StatusCodes.Status500InternalServerError, AmrProblemDetails.ContentType)]
public abstract class ApiControllerBase : ControllerBase
{
    protected ObjectResult NotFoundProblem(string code, string detail) =>
        AmrProblemDetails.ToResult(AmrProblemDetails.Create(HttpContext, StatusCodes.Status404NotFound, code, detail));
}
