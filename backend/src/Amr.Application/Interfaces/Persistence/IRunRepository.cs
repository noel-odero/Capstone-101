using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;

namespace Amr.Application.Interfaces.Persistence;

/// <summary>
/// Durable storage of completed runs. Each Save is one atomic commit: the run, its strategy runs and every step trace are
/// stored together or not at all. Implementations throw <see cref="Errors.AmrException"/> with a safe message and never
/// return before the commit succeeded. Incomplete or failed runs are never stored.
/// </summary>
public interface IRunRepository
{
    /// <summary>Stores a completed simulation. A duplicate run id is a failure, not an overwrite.</summary>
    Task SaveSimulationAsync(SimulationDto simulation, CancellationToken cancellationToken);

    /// <summary>Stores a completed, contract-verified comparison. A duplicate run id is a failure, not an overwrite.</summary>
    Task SaveComparisonAsync(ComparisonDto comparison, CancellationToken cancellationToken);

    /// <returns>The stored simulation with IsPersisted true, or null when no simulation has the id (a comparison id is not a simulation id).</returns>
    Task<SimulationDto?> FindSimulationAsync(Guid id, CancellationToken cancellationToken);

    /// <returns>The stored comparison with IsPersisted true, or null when no comparison has the id.</returns>
    Task<ComparisonDto?> FindComparisonAsync(Guid id, CancellationToken cancellationToken);

    /// <summary>Simulations and comparisons together, newest first (created time, then id, both descending).</summary>
    Task<PagedResultDto<RunSummaryDto>> ListRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken);
}
