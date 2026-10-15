using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Comparisons)]
public sealed class ComparisonsController(IComparisonService comparisons) : ApiControllerBase
{
    /// <summary>
    /// Runs PPO and the Random Susceptible Baseline from one profile and environment seed. A matched seed schedule does not
    /// make the stochastic outcomes identical. The result is not stored yet (isPersisted false).
    /// </summary>
    [HttpPost]
    [ProducesResponseType<ComparisonDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ComparisonDto>> Create(CreateComparisonRequest request, CancellationToken cancellationToken) =>
        await comparisons.RunAsync(request, cancellationToken);

    /// <summary>A stored comparison. Needs stored runs: 501 until persistence is implemented.</summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType<ComparisonDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status501NotImplemented, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ComparisonDto>> Get(Guid id, CancellationToken cancellationToken)
    {
        var comparison = await comparisons.GetAsync(id, cancellationToken);
        return comparison is null ? NotFoundProblem(ErrorCodes.NotFound, "No comparison has this id.") : comparison;
    }
}
