using Amr.Application.Errors;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.Application.Mappings;

/// <summary>
/// The only place that translates between public strategy identifiers and the Python wire identifiers.
/// The public baseline wraps Python's GreedyPolicy, which samples uniformly among susceptible actions.
/// </summary>
public static class StrategyMapping
{
    public static string ToPythonId(StrategyKind strategy) => strategy switch
    {
        StrategyKind.Ppo => PythonStrategyIds.Ppo,
        StrategyKind.Dqn => PythonStrategyIds.Dqn,
        StrategyKind.RandomSusceptibleBaseline => PythonStrategyIds.Greedy,
        _ => throw new ArgumentOutOfRangeException(nameof(strategy), strategy, "Unmapped strategy."),
    };

    /// <exception cref="AmrException">The Python service returned an identifier this API does not know.</exception>
    public static StrategyKind FromPythonId(string pythonId) => pythonId switch
    {
        PythonStrategyIds.Ppo => StrategyKind.Ppo,
        PythonStrategyIds.Dqn => StrategyKind.Dqn,
        PythonStrategyIds.Greedy => StrategyKind.RandomSusceptibleBaseline,
        _ => throw UpstreamErrors.InvalidResponse(),
    };
}
