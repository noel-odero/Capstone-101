using System.Text.Json;
using Amr.Application.DTOs.Common;
using Amr.Application.Errors;
using Amr.Domain.Enums;

namespace Amr.Application.Metrics;

/// <summary>
/// Canonical metadata for every metric in <see cref="StrategyMetricsDto"/>. Kind, unit and aggregation were verified
/// against service/rollout.py (METRIC_DEFINITIONS and _strategy_result), ml/src/metrics.py, ml/src/evaluation_runner.py
/// (the terminal adjustment) and simulation/reward.py;
/// the definition text itself always comes from the Python response. A response whose metric names differ from this
/// catalogue is rejected rather than guessed at, so a new or renamed metric is flagged for resolution.
/// </summary>
public static class MetricCatalogue
{
    public sealed record Entry(string PythonKey, string PublicName, MetricKind Kind, string Unit, string Aggregation);

    private const string CountOfAntibiotics = "antibiotics, from 0 to 7";
    private const string ProportionOfSteps = "proportion of steps in [0, 1]; not a percentage";

    public static IReadOnlyList<Entry> Entries { get; } =
    [
        new("cumulative_resistance_burden", nameof(StrategyMetricsDto.CumulativeResistanceBurden), MetricKind.Cumulative,
            "resistant-antibiotic burden normalized by 7 antibiotics; simulated, lower is less burden",
            "Negated cumulative reward: the negated sum of step rewards plus the negated terminal adjustment, which is -horizon when the episode starts in the all-resistant terminal state and 0 otherwise (so a zero-step episode that starts all-resistant has burden equal to the horizon)"),
        new("cumulative_reward", nameof(StrategyMetricsDto.CumulativeReward), MetricKind.Cumulative,
            "simulator reward units",
            "Sum of step rewards plus the terminal adjustment, which is -horizon when the episode starts in the all-resistant terminal state and 0 otherwise"),
        new("treatment_steps", nameof(StrategyMetricsDto.TreatmentSteps), MetricKind.Count,
            "steps",
            "Number of actions taken before the episode ended"),
        new("initial_resistant_count", nameof(StrategyMetricsDto.InitialResistantCount), MetricKind.Count,
            CountOfAntibiotics,
            "Value at the start of the episode; not accumulated"),
        new("final_resistant_count", nameof(StrategyMetricsDto.FinalResistantCount), MetricKind.Count,
            CountOfAntibiotics,
            "Value at the end of the episode; not accumulated"),
        new("final_susceptible_count", nameof(StrategyMetricsDto.FinalSusceptibleCount), MetricKind.Count,
            CountOfAntibiotics,
            "Value at the end of the episode; not accumulated"),
        new("change_in_susceptible_count", nameof(StrategyMetricsDto.ChangeInSusceptibleCount), MetricKind.Difference,
            "antibiotics, signed",
            "Final susceptible count minus initial susceptible count"),
        new("resistance_emergence_events", nameof(StrategyMetricsDto.ResistanceEmergenceEvents), MetricKind.Count,
            "steps",
            "Number of steps after which the resistant count increased"),
        new("resistance_emergence_rate", nameof(StrategyMetricsDto.ResistanceEmergenceRate), MetricKind.Rate,
            ProportionOfSteps,
            "resistance_emergence_events divided by treatment_steps; null when there are no steps"),
        new("susceptible_action_rate", nameof(StrategyMetricsDto.SusceptibleActionRate), MetricKind.Rate,
            ProportionOfSteps,
            "Steps whose selected drug was susceptible in the simulator divided by treatment_steps; null when there are no steps"),
        new("unsupported_step_count", nameof(StrategyMetricsDto.UnsupportedStepCount), MetricKind.Count,
            "steps",
            "Number of steps with transition_status unsupported_no_candidate"),
        new("cumulative_antibiotic_exposure", nameof(StrategyMetricsDto.CumulativeAntibioticExposure), MetricKind.Cumulative,
            "antibiotic administrations",
            "One per step, so it equals treatment_steps"),
    ];

    /// <summary>Public definitions keyed by the camelCase metric property name, with each Python definition kept verbatim.</summary>
    /// <exception cref="AmrException">The Python metric names differ from the catalogue, or a definition is empty.</exception>
    public static IReadOnlyDictionary<string, MetricDefinitionDto> Describe(IReadOnlyDictionary<string, string> pythonDefinitions)
    {
        var expected = Entries.Select(entry => entry.PythonKey).ToHashSet(StringComparer.Ordinal);
        if (!expected.SetEquals(pythonDefinitions.Keys) || pythonDefinitions.Values.Any(string.IsNullOrWhiteSpace))
        {
            throw UpstreamErrors.InvalidResponse();
        }

        return Entries.ToDictionary(
            entry => JsonNamingPolicy.CamelCase.ConvertName(entry.PublicName),
            entry => new MetricDefinitionDto(pythonDefinitions[entry.PythonKey], entry.Kind, entry.Unit, entry.Aggregation),
            StringComparer.Ordinal);
    }
}
