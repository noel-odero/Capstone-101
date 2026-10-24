using System.Text.Json;

namespace Amr.Application.PythonContracts;

/// <summary>Strategy identifiers on the Python wire. "greedy" is the internal name of the Random Susceptible Baseline.</summary>
public static class PythonStrategyIds
{
    public const string Ppo = "ppo";
    public const string Dqn = "dqn";
    public const string Greedy = "greedy";
}

public sealed record PythonFeasibleAction(int ActionId, string Antibiotic, bool HasCandidateTransition);

public sealed record PythonStateSnapshot(
    int StateIndex,
    int TreatmentStep,
    IReadOnlyList<int> ResistanceProfile,
    IReadOnlyList<string> ResistantAntibiotics,
    int ResistantCount,
    int SusceptibleCount,
    int? LastActionId,
    string? LastActionAntibiotic,
    bool IsTerminal);

public sealed record PythonCandidateTransition(
    string TargetDrug,
    string Outcome,
    IReadOnlyList<string> SourceIds,
    double ScenarioProbability);

public sealed record PythonStepTrace(
    int StepIndex,
    int TreatmentStepBefore,
    int TreatmentStepAfter,
    IReadOnlyList<int> ResistanceProfileBefore,
    int ActionId,
    string Antibiotic,
    IReadOnlyList<PythonFeasibleAction> FeasibleActions,
    bool SelectedDrugSusceptible,
    string TransitionStatus,
    bool HasCandidateTransition,
    IReadOnlyList<PythonCandidateTransition> CandidateTransitions,
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

public sealed record PythonStrategyMetrics(
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

public sealed record PythonStrategyResult(
    string Strategy,
    string DisplayLabel,
    string Implementation,
    IReadOnlyList<int> InitialProfile,
    IReadOnlyList<int> FinalProfile,
    long EnvironmentSeed,
    long? PolicySeed,
    string TerminationReason,
    IReadOnlyList<PythonStateSnapshot> States,
    IReadOnlyList<PythonStepTrace> Steps,
    PythonStrategyMetrics Metrics)
{
    public PythonPolicyModel? Model { get; init; }
}

public sealed record PythonPolicyModel(string ModelId, string Algorithm, string CheckpointSha256);

/// <param name="RewardSpecification">Declared dict[str, Any] in service/schemas.py; kept as an open map so no key is dropped.</param>
public sealed record PythonProvenance(
    string ServiceVersion,
    string ModelId,
    string Algorithm,
    string CheckpointSha256,
    string InteractionDataSha256,
    string ScenarioId,
    int Horizon,
    IReadOnlyDictionary<string, JsonElement> RewardSpecification,
    string ActionMaskRule,
    IReadOnlyList<string> AntibioticOrder,
    string EvaluationUtility);

public sealed record PythonSeedConfiguration(
    long EnvironmentSeed,
    string EnvironmentSeedSource,
    long? PolicySeed,
    string PolicySeedSource,
    IReadOnlyList<string> Notes);
