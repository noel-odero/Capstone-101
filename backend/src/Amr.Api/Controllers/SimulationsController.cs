using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Simulations)]
public sealed class SimulationsController(ISimulationService simulations, IRunHistoryService history) : ApiControllerBase
{
    /// <summary>
    /// Runs one strategy from a profile. The result is not stored yet (isPersisted false), so its id cannot be retrieved.
    /// </summary>
    [HttpPost]
    [ProducesResponseType<SimulationDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<SimulationDto>> Create(CreateSimulationRequest request, CancellationToken cancellationToken) =>
        await simulations.RunAsync(request, cancellationToken);

    /// <summary>Recent simulations and comparisons. Needs stored runs: 501 until persistence is implemented.</summary>
    [HttpGet("recent")]
    [ProducesResponseType<PagedResultDto<RunSummaryDto>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status501NotImplemented, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<PagedResultDto<RunSummaryDto>>> GetRecent([FromQuery] RecentRunsQuery query, CancellationToken cancellationToken) =>
        await history.GetRecentAsync(query, cancellationToken);

    /// <summary>A stored simulation. Needs stored runs: 501 until persistence is implemented.</summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType<SimulationDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status501NotImplemented, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<SimulationDto>> Get(Guid id, CancellationToken cancellationToken)
    {
        var simulation = await simulations.GetAsync(id, cancellationToken);
        return simulation is null ? NotFoundProblem(ErrorCodes.NotFound, "No simulation has this id.") : simulation;
    }
}
