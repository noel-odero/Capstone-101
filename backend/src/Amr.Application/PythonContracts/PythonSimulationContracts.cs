namespace Amr.Application.PythonContracts;

public sealed record PythonSimulateRequest(
    IReadOnlyList<int> ResistanceProfile,
    string Strategy,
    long? EnvironmentSeed,
    long? PolicySeed);

public sealed record PythonSimulation(
    string RunId,
    string Kind,
    string CreatedAtUtc,
    PythonProvenance Provenance,
    PythonSeedConfiguration SeedConfiguration,
    PythonStrategyResult Result,
    IReadOnlyDictionary<string, string> MetricDefinitions,
    string Disclaimer);
