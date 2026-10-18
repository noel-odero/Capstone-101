using Amr.Application.DTOs.Recommendations;
using Amr.Application.DTOs.Simulations;
using Amr.Domain.Enums;

namespace Amr.Application.Mappings;

public static class RecommendationMappings
{
    public const string Interpretation =
        "These are the actions the frozen PPO policy selected in this simulated run, each chosen among drugs that were " +
        "susceptible in the simulator. A step marked unsupported_no_candidate has no modeled transition, so the simulator " +
        "left the profile unchanged. This is simulation output, not clinical advice or evidence of efficacy.";

    /// <returns>Null unless the run is a completed PPO simulation; baseline runs, failed runs and comparisons have no recommendation.</returns>
    public static RecommendationDto? ToRecommendationDto(this SimulationDto simulation) =>
        simulation is { Status: RunStatus.Completed, Result: { Strategy: StrategyKind.Ppo } result }
            ? new RecommendationDto(
                simulation.Id,
                result.Strategy,
                result.DisplayLabel,
                simulation.Provenance,
                result.InitialProfile,
                result.States[0].IsTerminal,
                result.TerminationReason,
                result.Steps,
                Interpretation)
            : null;
}
