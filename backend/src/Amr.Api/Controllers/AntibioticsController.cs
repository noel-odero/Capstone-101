using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Antibiotics;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Antibiotics)]
public sealed class AntibioticsController(IModelInfoService models) : ApiControllerBase
{
    /// <summary>The seven antibiotics in canonical action order.</summary>
    [HttpGet]
    [ProducesResponseType<AntibioticCatalogueDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<AntibioticCatalogueDto>> Get(CancellationToken cancellationToken) =>
        await models.GetAntibioticsAsync(cancellationToken);
}
