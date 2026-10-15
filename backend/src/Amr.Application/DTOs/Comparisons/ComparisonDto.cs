using System.Text.Json;
using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Comparisons;

public sealed record ActionMaskConfigurationDto(bool Enabled, string Rule);

public sealed record SharedConfigurationDto(
    IReadOnlyList<int> InitialProfile,
    long EnvironmentSeed,
    string ScenarioId,
    int Horizon,
    string InteractionDataSha256,
    IReadOnlyDictionary<string, JsonElement> RewardSpecification,
    ActionMaskConfigurationDto ActionMaskConfiguration);

public sealed record TransitionSeedScheduleDto(bool SharedByStepIndex, int StepsCompared, string Meaning);

public sealed record ObservedDivergenceDto(
    int StepsCompared,
    int StepsWithSameAction,
    int? FirstDivergentStep,
    bool TrajectoriesIdentical);

/// <summary>
/// Checks the Python service verified before returning a pair. A shared transition-seed schedule does not make
/// transition outcomes identical: candidate sets depend on the selected action and state.
/// </summary>
public sealed record ComparisonContractDto(
    bool Verified,
    IReadOnlyList<string> ChecksPassed,
    SharedConfigurationDto Shared,
    TransitionSeedScheduleDto TransitionSeedSchedule,
    bool TransitionOutcomesGuaranteedIdentical,
    ObservedDivergenceDto Observed);

/// <param name="Id">The scientific service's run id. Until persistence exists it identifies this execution only and cannot be retrieved.</param>
/// <param name="IsPersisted">False when the run is not stored, so GET by id does not work for it.</param>
/// <param name="Ppo">Null when the comparison failed.</param>
/// <param name="Baseline">The Random Susceptible Baseline; null when the comparison failed.</param>
public sealed record ComparisonDto(
    Guid Id,
    RunStatus Status,
    bool IsPersisted,
    DateTimeOffset CreatedAtUtc,
    ModelProvenanceDto Provenance,
    SeedConfigurationDto SeedConfiguration,
    string PairingSemantics,
    ComparisonContractDto? Contract,
    StrategyResultDto? Ppo,
    StrategyResultDto? Baseline,
    RunErrorDto? Error,
    string SingleRunCaveat,
    string Disclaimer);
