using Amr.Application.DTOs.Common;

namespace Amr.Application.DTOs.Model;

public sealed record ObservationLayoutDto(
    IReadOnlyList<int> Shape,
    string Dtype,
    IReadOnlyDictionary<string, IReadOnlyList<int>> Layout,
    IReadOnlyDictionary<string, int> ResistanceEncoding);

public sealed record ActionSpaceDto(string Type, int Count);

/// <param name="CheckpointSha256">Verified by the Python service at load; the loaded bytes are the hashed bytes.</param>
/// <param name="InteractionDataSha256">Pinned in the frozen manifest and checked against the live simulator data.</param>
public sealed record ModelInfoDto(
    int ManifestVersion,
    string ModelId,
    string Algorithm,
    string CheckpointSha256,
    string InteractionDataSha256,
    string ScenarioId,
    int Horizon,
    IReadOnlyList<string> AntibioticOrder,
    ObservationLayoutDto Observation,
    ActionSpaceDto ActionSpace,
    string ActionMaskRule,
    bool DeterministicInference,
    IReadOnlyDictionary<string, string> TransitionStatusDefinitions,
    string ServiceVersion,
    string Disclaimer)
{
    public IReadOnlyDictionary<string, PolicyModelDto>? Policies { get; init; }
}
