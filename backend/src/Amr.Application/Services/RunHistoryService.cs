using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

/// <summary>Lists stored runs, so it cannot work until persistence exists. Stage D replaces this class.</summary>
public sealed class RunHistoryService : IRunHistoryService
{
    public Task<PagedResultDto<RunSummaryDto>> GetRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken) =>
        Task.FromException<PagedResultDto<RunSummaryDto>>(PersistenceNotAvailable.Error());
}
