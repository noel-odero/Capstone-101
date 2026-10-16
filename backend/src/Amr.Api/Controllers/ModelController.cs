using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Model;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Model)]
public sealed class ModelController(IModelInfoService models) : ApiControllerBase
{
    /// <summary>Identity and verified provenance of the frozen model.</summary>
    [HttpGet]
    [ProducesResponseType<ModelInfoDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ModelInfoDto>> Get(CancellationToken cancellationToken) =>
        await models.GetModelAsync(cancellationToken);
}
