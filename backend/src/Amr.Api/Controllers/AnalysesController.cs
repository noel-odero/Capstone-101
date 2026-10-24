using Amr.Api.Routing;
using Amr.Application.DTOs.Analyses;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Analyses)]
public sealed class AnalysesController(IRunHistoryService history, IAnalysisComparisonService comparisons) : ApiControllerBase
{
    [HttpGet]
    [ProducesResponseType<PagedResultDto<RunSummaryDto>>(StatusCodes.Status200OK)]
    public Task<PagedResultDto<RunSummaryDto>> List([FromQuery] RecentRunsQuery query, CancellationToken cancellationToken) =>
        history.GetRecentAsync(query, cancellationToken);

    /// <summary>Compares owned, persisted analyses without invoking the scientific service.</summary>
    [HttpPost("compare")]
    [ProducesResponseType<AnalysisComparisonDto>(StatusCodes.Status200OK)]
    public Task<AnalysisComparisonDto> Compare(CompareAnalysesRequest request, CancellationToken cancellationToken) =>
        comparisons.CompareAsync(request, cancellationToken);
}
