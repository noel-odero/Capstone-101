using System.Text.Json;

namespace Amr.Application.DTOs.Common;

/// <summary>Model and simulator identity attached to every run. Hashes come from the verified Python service.</summary>
/// <param name="RewardSpecification">
/// The simulator's RewardSpecification passed through verbatim. Today it holds objective, normalization and
/// terminal_convention; keys keep their Python spelling and the API never interprets them.
/// </param>
public sealed record ModelProvenanceDto(
    string ModelId,
    string Algorithm,
    string CheckpointSha256,
    string InteractionDataSha256,
    string ScenarioId,
    int Horizon,
    IReadOnlyDictionary<string, JsonElement> RewardSpecification,
    string ActionMaskRule,
    IReadOnlyList<string> AntibioticOrder,
    string ServiceVersion);

public sealed record SeedConfigurationDto(
    long EnvironmentSeed,
    string EnvironmentSeedSource,
    long? PolicySeed,
    string PolicySeedSource,
    IReadOnlyList<string> Notes);

/// <summary>Why a persisted run did not complete. The message is safe for clients.</summary>
public sealed record RunErrorDto(string Code, string Message);
