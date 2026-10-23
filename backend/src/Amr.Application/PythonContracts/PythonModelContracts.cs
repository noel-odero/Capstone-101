namespace Amr.Application.PythonContracts;

/// <summary>Response of GET /internal/health. A not-ready model is reported with HTTP 503 and this same body.</summary>
public sealed record PythonHealth(
    string Status,
    bool ModelReady,
    string ServiceVersion,
    string? ModelId,
    string? CheckpointSha256,
    string? ErrorCode,
    string Message);

public sealed record PythonObservationLayout(
    IReadOnlyList<int> Shape,
    string Dtype,
    IReadOnlyDictionary<string, IReadOnlyList<int>> Layout,
    IReadOnlyDictionary<string, int> ResistanceEncoding);

public sealed record PythonActionSpace(string Type, int N);

public sealed record PythonActionMasking(string Rule);

public sealed record PythonInference(bool Deterministic, string Device);

public sealed record PythonModelInfo(
    int ManifestVersion,
    string ModelId,
    string Algorithm,
    string CheckpointSha256,
    string ManifestCheckpointSha256,
    string InteractionDataSha256,
    string ScenarioId,
    int Horizon,
    IReadOnlyList<string> AntibioticOrder,
    PythonObservationLayout Observation,
    PythonActionSpace ActionSpace,
    PythonActionMasking ActionMasking,
    PythonInference Inference,
    IReadOnlyDictionary<string, string> ProvenanceFiles,
    IReadOnlyDictionary<string, string> TransitionStatusDefinitions,
    string ServiceVersion,
    string Disclaimer)
{
    public IReadOnlyDictionary<string, PythonPolicyModel>? Policies { get; init; }
}

public sealed record PythonAntibiotic(int ActionId, string Name, string? DrugClass);

public sealed record PythonAntibiotics(
    IReadOnlyList<PythonAntibiotic> Antibiotics,
    IReadOnlyDictionary<string, int> ResistanceEncoding);

public sealed record PythonProfileRequest(IReadOnlyList<int> ResistanceProfile);

public sealed record PythonProfileValidation(
    bool Valid,
    IReadOnlyList<int> ResistanceProfile,
    IReadOnlyList<string> ResistantAntibiotics,
    IReadOnlyList<string> SusceptibleAntibiotics,
    int ResistantCount,
    int SusceptibleOptionCount,
    IReadOnlyList<PythonFeasibleAction> FeasibleActions,
    IReadOnlyList<int> FeasibleActionIds,
    bool IsTerminal,
    string? TerminalReason,
    int Horizon);
