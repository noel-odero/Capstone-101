using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;

namespace Amr.Application.Interfaces.Services;

public interface IRunHistoryService
{
    /// <summary>
    /// Recent simulations and comparisons together, distinguished by RunSummaryDto.Kind. Ordered by creation time
    /// descending, then id descending, so pages are stable. Page size is capped at PaginationLimits.MaxPageSize.
    /// </summary>
    Task<PagedResultDto<RunSummaryDto>> GetRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken);
}
