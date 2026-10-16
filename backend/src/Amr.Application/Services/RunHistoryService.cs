using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

public sealed class RunHistoryService(IRunRepository runs) : IRunHistoryService
{
    public Task<PagedResultDto<RunSummaryDto>> GetRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken) =>
        runs.ListRecentAsync(query, cancellationToken);
}
