namespace Amr.Infrastructure.Persistence.Entities;

/// <summary>
/// One step of a strategy run. The key (strategy run, step index) fixes the order and forbids duplicates.
/// SelectedDrugSusceptible is the profile flag; HasCandidateTransition and TransitionStatus say whether the simulator had
/// transition data. The two are stored separately and never merged: a susceptible drug without candidate data is unsupported.
/// </summary>
public sealed class StepTrace
{
    public Guid StrategyRunId { get; set; }

    public StrategyRun StrategyRun { get; set; } = null!;

    public int StepIndex { get; set; }

    public int TreatmentStepBefore { get; set; }

    public int TreatmentStepAfter { get; set; }

    public required int[] ResistanceProfileBefore { get; set; }

    public int ActionId { get; set; }

    public required string Antibiotic { get; set; }

    /// <summary>The feasible actions at this step with their transition support, as a JSON array.</summary>
    public required string FeasibleActionsJson { get; set; }

    public bool SelectedDrugSusceptible { get; set; }

    /// <summary>The simulator's status: a transition outcome, or unsupported_no_candidate when it had no candidate transition and left the profile unchanged.</summary>
    public required string TransitionStatus { get; set; }

    public bool HasCandidateTransition { get; set; }

    /// <summary>The candidate transitions the simulator considered, as a JSON array; empty when unsupported.</summary>
    public required string CandidateTransitionsJson { get; set; }

    public string? SelectedOutcome { get; set; }

    public string? SelectedTargetDrug { get; set; }

    public required string[] SourceIds { get; set; }

    public double? SelectedCandidateProbability { get; set; }

    public double? NoTransitionProbability { get; set; }

    public long? TransitionSeed { get; set; }

    public double Reward { get; set; }

    public required int[] ResistanceProfileAfter { get; set; }

    public required string[] NewlyResistantAntibiotics { get; set; }

    public required string[] NewlySusceptibleAntibiotics { get; set; }

    public int ResistantCountAfter { get; set; }

    public int SusceptibleCountAfter { get; set; }

    public bool IsTerminalAfter { get; set; }

    public string? TerminationReason { get; set; }
}
