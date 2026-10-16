using Amr.Domain.Enums;

namespace Amr.Infrastructure.Persistence.Entities;

/// <summary>
/// One executed simulation (one strategy run) or comparison (two). The id is the Python run id and the public resource id.
/// Only completed runs exist: the status check constraint makes a partial or failed row impossible.
/// </summary>
public sealed class ExperimentRun
{
    public Guid Id { get; set; }

    public ExperimentKind Kind { get; set; }

    public RunStatus Status { get; set; }

    public Guid ModelVersionId { get; set; }

    public ModelVersion ModelVersion { get; set; } = null!;

    /// <summary>The scientific service build that executed the run; part of provenance but not of the model identity.</summary>
    public required string ServiceVersion { get; set; }

    /// <summary>When Python executed the run.</summary>
    public DateTimeOffset CreatedAtUtc { get; set; }

    /// <summary>When the API committed the record.</summary>
    public DateTimeOffset RecordedAtUtc { get; set; }

    public required int[] InitialProfile { get; set; }

    public long EnvironmentSeed { get; set; }

    public required string EnvironmentSeedSource { get; set; }

    public long? PolicySeed { get; set; }

    public required string PolicySeedSource { get; set; }

    public required string[] SeedNotes { get; set; }

    public required string Disclaimer { get; set; }

    /// <summary>Metric names to their public definitions (verbatim Python text, kind, unit, aggregation) as served with the run.</summary>
    public required string MetricDefinitionsJson { get; set; }

    /// <summary>Comparison only.</summary>
    public string? PairingSemantics { get; set; }

    /// <summary>Comparison only.</summary>
    public string? SingleRunCaveat { get; set; }

    /// <summary>Comparison only: the verified comparison contract.</summary>
    public string? ComparisonContractJson { get; set; }

    public List<StrategyRun> StrategyRuns { get; set; } = [];
}
