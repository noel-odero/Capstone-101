using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Common;

/// <summary>State k is the profile after the k-th action; state 0 is the initial profile.</summary>
public sealed record StateSnapshotDto(
    int StateIndex,
    int TreatmentStep,
    IReadOnlyList<int> ResistanceProfile,
    IReadOnlyList<string> ResistantAntibiotics,
    int ResistantCount,
    int SusceptibleCount,
    int? LastActionId,
    string? LastActionAntibiotic,
    bool IsTerminal);

/// <param name="ScenarioProbability">Probability under the simulator's scenario assumption, not an empirical estimate.</param>
public sealed record CandidateTransitionDto(
    string TargetDrug,
    string Outcome,
    IReadOnlyList<string> SourceIds,
    double ScenarioProbability);

/// <param name="SelectedDrugSusceptible">Simulator flag: the drug was susceptible before the action. It is not clinical efficacy.</param>
/// <param name="TransitionStatus">unsupported_no_candidate marks an action with no modeled outcome; the profile is unchanged.</param>
public sealed record StepTraceDto(
    int StepIndex,
    int TreatmentStepBefore,
    int TreatmentStepAfter,
    IReadOnlyList<int> ResistanceProfileBefore,
    int ActionId,
    string Antibiotic,
    IReadOnlyList<FeasibleActionDto> FeasibleActions,
    bool SelectedDrugSusceptible,
    string TransitionStatus,
    bool HasCandidateTransition,
    IReadOnlyList<CandidateTransitionDto> CandidateTransitions,
    string? SelectedOutcome,
    string? SelectedTargetDrug,
    IReadOnlyList<string> SourceIds,
    double? SelectedCandidateProbability,
    double? NoTransitionProbability,
    long? TransitionSeed,
    double Reward,
    IReadOnlyList<int> ResistanceProfileAfter,
    IReadOnlyList<string> NewlyResistantAntibiotics,
    IReadOnlyList<string> NewlySusceptibleAntibiotics,
    int ResistantCountAfter,
    int SusceptibleCountAfter,
    bool IsTerminalAfter,
    string? TerminationReason);

/// <param name="CumulativeResistanceBurden">Negative of the simulator's cumulative reward. A simulated quantity, not a clinical outcome.</param>
/// <param name="SusceptibleActionRate">Share of steps whose drug was susceptible in the simulator. Not clinical efficacy.</param>
public sealed record StrategyMetricsDto(
    double CumulativeResistanceBurden,
    double CumulativeReward,
    int TreatmentSteps,
    int InitialResistantCount,
    int FinalResistantCount,
    int FinalSusceptibleCount,
    int ChangeInSusceptibleCount,
    int ResistanceEmergenceEvents,
    double? ResistanceEmergenceRate,
    double? SusceptibleActionRate,
    int UnsupportedStepCount,
    int CumulativeAntibioticExposure);

/// <param name="DisplayLabel">User-facing name; the baseline is shown as "Random Susceptible Baseline".</param>
public sealed record StrategyResultDto(
    StrategyKind Strategy,
    string DisplayLabel,
    IReadOnlyList<int> InitialProfile,
    IReadOnlyList<int> FinalProfile,
    long EnvironmentSeed,
    long? PolicySeed,
    string TerminationReason,
    IReadOnlyList<StateSnapshotDto> States,
    IReadOnlyList<StepTraceDto> Steps,
    StrategyMetricsDto Metrics)
{
    public PolicyModelDto? Model { get; init; }
}

public sealed record PolicyModelDto(string ModelId, string Algorithm, string CheckpointSha256);
