using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Recommendations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Recommendations)]
public sealed class RecommendationsController(IRecommendationService recommendations) : ApiControllerBase
{
    /// <summary>
    /// PPO-selected actions of a stored simulation, with their feasibility and transition support. Simulation output, not
    /// clinical advice. 404 recommendation_not_found for an unknown id and for any run without PPO steps (a baseline
    /// simulation or a comparison id); the cases are deliberately indistinguishable.
    /// </summary>
    [HttpGet("{simulationId:guid}")]
    [ProducesResponseType<RecommendationDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<RecommendationDto>> Get(Guid simulationId, CancellationToken cancellationToken)
    {
        var recommendation = await recommendations.GetBySimulationAsync(simulationId, cancellationToken);
        return recommendation is null
            ? NotFoundProblem(ErrorCodes.RecommendationNotFound, "No PPO recommendations exist for this simulation.")
            : recommendation;
    }
}
