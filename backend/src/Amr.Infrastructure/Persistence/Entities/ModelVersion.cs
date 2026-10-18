namespace Amr.Infrastructure.Persistence.Entities;

/// <summary>
/// The exact model and simulator configuration a run used. Runs that share a fingerprint share this row, so "which
/// checkpoint and which transition data produced this result" is a join, not a guess.
/// </summary>
public sealed class ModelVersion
{
    public Guid Id { get; set; }

    /// <summary>SHA-256 over the canonical form of every identity column below; unique, and the target of the get-or-create upsert.</summary>
    public required string Fingerprint { get; set; }

    public required string ModelId { get; set; }

    public required string Algorithm { get; set; }

    public required string CheckpointSha256 { get; set; }

    public required string InteractionDataSha256 { get; set; }

    public required string ScenarioId { get; set; }

    public int Horizon { get; set; }

    public required string ActionMaskRule { get; set; }

    /// <summary>The simulator's reward specification as a JSON object, passed through verbatim.</summary>
    public required string RewardSpecificationJson { get; set; }

    /// <summary>Canonical antibiotic order; position is the action id.</summary>
    public required string[] AntibioticOrder { get; set; }

    public DateTimeOffset FirstRecordedAtUtc { get; set; }

    public List<ExperimentRun> ExperimentRuns { get; set; } = [];
}
