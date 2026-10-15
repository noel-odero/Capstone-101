using System.Text.Json;

namespace Amr.Application.PythonContracts;

public sealed record PythonCompareRequest(IReadOnlyList<int> ResistanceProfile, long? EnvironmentSeed, long? PolicySeed);

public sealed record PythonActionMaskConfiguration(bool Enabled, string Rule);

public sealed record PythonSharedConfiguration(
    IReadOnlyList<int> InitialProfile,
    long EnvironmentSeed,
    string ScenarioId,
    int Horizon,
    string InteractionDataSha256,
    IReadOnlyDictionary<string, JsonElement> RewardSpecification,
    PythonActionMaskConfiguration ActionMaskConfiguration);

public sealed record PythonTransitionSeedSchedule(bool SharedByStepIndex, int StepsCompared, string Meaning);

public sealed record PythonObservedDivergence(
    int StepsCompared,
    int StepsWithSameAction,
    int? FirstDivergentStep,
    bool TrajectoriesIdentical);

public sealed record PythonComparisonContract(
    bool Verified,
    IReadOnlyList<string> ChecksPassed,
    PythonSharedConfiguration Shared,
    PythonTransitionSeedSchedule TransitionSeedSchedule,
    bool TransitionOutcomesGuaranteedIdentical,
    PythonObservedDivergence Observed);

public sealed record PythonComparison(
    string RunId,
    string Kind,
    string CreatedAtUtc,
    PythonProvenance Provenance,
    PythonSeedConfiguration SeedConfiguration,
    string PairingSemantics,
    PythonComparisonContract ComparisonContract,
    PythonStrategyResult Ppo,
    PythonStrategyResult Greedy,
    IReadOnlyDictionary<string, string> MetricDefinitions,
    string SingleRunCaveat,
    string Disclaimer);
