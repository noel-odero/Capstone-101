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
    /// Runs PPO and the Random Susceptible Baseline from one profile and environment seed and stores the verified pair. A
    /// matched seed schedule does not make the stochastic outcomes identical. 201 Created is returned only after the commit
    /// (isPersisted true); an unverified pair or a failed save is an error and nothing is returned or stored.
    /// </summary>
    [HttpPost]
    [ProducesResponseType<ComparisonDto>(StatusCodes.Status201Created)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ComparisonDto>> Create(CreateComparisonRequest request, CancellationToken cancellationToken)
    {
        var comparison = await comparisons.RunAsync(request, cancellationToken);
        return CreatedAtAction(nameof(Get), new { id = comparison.Id, version = ApiRoutes.UrlVersion1 }, comparison);
    }

    /// <summary>A stored comparison. A simulation id is not a comparison id.</summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType<ComparisonDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ComparisonDto>> Get(Guid id, CancellationToken cancellationToken)
    {
        var comparison = await comparisons.GetAsync(id, cancellationToken);
        return comparison is null ? NotFoundProblem(ErrorCodes.NotFound, "No comparison has this id.") : comparison;
    }
}
