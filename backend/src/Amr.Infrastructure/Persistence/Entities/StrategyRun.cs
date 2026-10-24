using Amr.Domain.Enums;

namespace Amr.Infrastructure.Persistence.Entities;

/// <summary>One strategy's trajectory within an experiment run, with its metrics. At most one row per strategy per run.</summary>
public sealed class StrategyRun
{
    public Guid Id { get; set; }

    public Guid ExperimentRunId { get; set; }

    public ExperimentRun ExperimentRun { get; set; } = null!;

    public StrategyKind Strategy { get; set; }

    public required string DisplayLabel { get; set; }
    public string? ModelJson { get; set; }

    public required int[] InitialProfile { get; set; }

    public required int[] FinalProfile { get; set; }

    public long EnvironmentSeed { get; set; }

    public long? PolicySeed { get; set; }

    public required string TerminationReason { get; set; }

    /// <summary>State snapshots (state 0 is the initial profile) as a JSON array; they are fully determined by the steps but returned as the service produced them.</summary>
    public required string StatesJson { get; set; }

    public double CumulativeResistanceBurden { get; set; }

    public double CumulativeReward { get; set; }

    public int TreatmentSteps { get; set; }

    public int InitialResistantCount { get; set; }

    public int FinalResistantCount { get; set; }

    public int FinalSusceptibleCount { get; set; }

    public int ChangeInSusceptibleCount { get; set; }

    public int ResistanceEmergenceEvents { get; set; }

    public double? ResistanceEmergenceRate { get; set; }

    public double? SusceptibleActionRate { get; set; }

    public int UnsupportedStepCount { get; set; }

    public int CumulativeAntibioticExposure { get; set; }

    public List<StepTrace> StepTraces { get; set; } = [];
}
