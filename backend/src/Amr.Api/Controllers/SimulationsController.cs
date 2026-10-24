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
    /// Runs one strategy from a profile and stores the result. 201 Created is returned only after the run was committed
    /// (isPersisted true); the Location header and id retrieve exactly this run. If the run executed but could not be
    /// saved the response is an error (503 database_unavailable or 500 persistence_failed) and no id is issued.
    /// </summary>
    [HttpPost]
    [ProducesResponseType<SimulationDto>(StatusCodes.Status201Created)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<SimulationDto>> Create(CreateSimulationRequest request, CancellationToken cancellationToken)
    {
        var simulation = await simulations.RunAsync(request, cancellationToken);
        return CreatedAtAction(nameof(Get), new { id = simulation.Id, version = ApiRoutes.UrlVersion1 }, simulation);
    }

    /// <summary>Recent simulations and comparisons, newest first.</summary>
    [HttpGet("recent")]
    [ProducesResponseType<PagedResultDto<RunSummaryDto>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<PagedResultDto<RunSummaryDto>>> GetRecent([FromQuery] RecentRunsQuery query, CancellationToken cancellationToken) =>
        await history.GetRecentAsync(query, cancellationToken);

    /// <summary>A stored simulation. A comparison id is not a simulation id.</summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType<SimulationDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<SimulationDto>> Get(Guid id, CancellationToken cancellationToken)
    {
        var simulation = await simulations.GetAsync(id, cancellationToken);
        return simulation is null ? NotFoundProblem(ErrorCodes.NotFound, "No analysis has this id.") : simulation;
    }
}
