using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Interfaces.Persistence;

namespace Amr.TestSupport;

/// <summary>Test double that records calls and can fail on demand. It is not a persistence implementation and is never used by the API.</summary>
internal sealed class FakeRunRepository : IRunRepository
{
    public List<SimulationDto> SavedSimulations { get; } = [];

    public List<ComparisonDto> SavedComparisons { get; } = [];

    /// <summary>Log of calls in order, for asserting that saving happens after verification and before the response is built.</summary>
    public List<string> Calls { get; } = [];

    public Exception? SaveFailure { get; set; }

    public Func<Guid, SimulationDto?> Simulation { get; set; } = _ => null;

    public Func<Guid, ComparisonDto?> Comparison { get; set; } = _ => null;

    public Task SaveSimulationAsync(SimulationDto simulation, CancellationToken cancellationToken)
    {
        Calls.Add("save-simulation");
        if (SaveFailure is not null)
        {
            return Task.FromException(SaveFailure);
        }

        SavedSimulations.Add(simulation);
        return Task.CompletedTask;
    }

    public Task SaveComparisonAsync(ComparisonDto comparison, CancellationToken cancellationToken)
    {
        Calls.Add("save-comparison");
        if (SaveFailure is not null)
        {
            return Task.FromException(SaveFailure);
        }

        SavedComparisons.Add(comparison);
        return Task.CompletedTask;
    }

    public Task<SimulationDto?> FindSimulationAsync(Guid id, CancellationToken cancellationToken)
    {
        Calls.Add("find-simulation");
        return Task.FromResult(Simulation(id));
    }

    public Task<ComparisonDto?> FindComparisonAsync(Guid id, CancellationToken cancellationToken)
    {
        Calls.Add("find-comparison");
        return Task.FromResult(Comparison(id));
    }

    public Task<PagedResultDto<RunSummaryDto>> ListRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken)
    {
        Calls.Add("list-recent");
        return Task.FromResult(new PagedResultDto<RunSummaryDto>([], query.Page, query.PageSize, 0));
    }
}
