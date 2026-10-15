using System.Globalization;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.Application.Mappings;

/// <summary>Translates Python run results to public DTOs. Values pass through unchanged; nothing is recomputed.</summary>
public static class RunMappings
{
    public static SimulationDto ToSimulationDto(this PythonSimulation run) => new(
        ParseRunId(run.RunId),
        RunStatus.Completed,
        IsPersisted: false,
        ParseTimestamp(run.CreatedAtUtc),
        run.Provenance.ToDto(),
        run.SeedConfiguration.ToDto(),
        run.Result.ToDto(),
        Error: null,
        run.Disclaimer);

    public static ModelProvenanceDto ToDto(this PythonProvenance provenance) => new(
        provenance.ModelId,
        provenance.Algorithm,
        provenance.CheckpointSha256,
        provenance.InteractionDataSha256,
        provenance.ScenarioId,
        provenance.Horizon,
        provenance.RewardSpecification,
        provenance.ActionMaskRule,
        provenance.AntibioticOrder,
        provenance.ServiceVersion);

    public static SeedConfigurationDto ToDto(this PythonSeedConfiguration seeds) => new(
        seeds.EnvironmentSeed,
        seeds.EnvironmentSeedSource,
        seeds.PolicySeed,
        seeds.PolicySeedSource,
        seeds.Notes);

    public static StrategyResultDto ToDto(this PythonStrategyResult result) => new(
        StrategyMapping.FromPythonId(result.Strategy),
        result.DisplayLabel,
        result.InitialProfile,
        result.FinalProfile,
        result.EnvironmentSeed,
        result.PolicySeed,
        result.TerminationReason,
        result.States.Select(state => state.ToDto()).ToList(),
        result.Steps.Select(step => step.ToDto()).ToList(),
        result.Metrics.ToDto());

    public static Guid ParseRunId(string runId) =>
        Guid.TryParse(runId, out var id) ? id : throw UpstreamErrors.InvalidResponse();

    public static DateTimeOffset ParseTimestamp(string timestamp) =>
        DateTimeOffset.TryParse(timestamp, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var parsed)
            ? parsed.ToUniversalTime()
            : throw UpstreamErrors.InvalidResponse();

    private static StateSnapshotDto ToDto(this PythonStateSnapshot state) => new(
        state.StateIndex,
        state.TreatmentStep,
        state.ResistanceProfile,
        state.ResistantAntibiotics,
        state.ResistantCount,
        state.SusceptibleCount,
        state.LastActionId,
        state.LastActionAntibiotic,
        state.IsTerminal);

    private static CandidateTransitionDto ToDto(this PythonCandidateTransition candidate) =>
        new(candidate.TargetDrug, candidate.Outcome, candidate.SourceIds, candidate.ScenarioProbability);

    private static StepTraceDto ToDto(this PythonStepTrace step) => new(
        step.StepIndex,
        step.TreatmentStepBefore,
        step.TreatmentStepAfter,
        step.ResistanceProfileBefore,
        step.ActionId,
        step.Antibiotic,
        step.FeasibleActions.Select(action => action.ToDto()).ToList(),
        step.SelectedDrugSusceptible,
        step.TransitionStatus,
        step.HasCandidateTransition,
        step.CandidateTransitions.Select(candidate => candidate.ToDto()).ToList(),
        step.SelectedOutcome,
        step.SelectedTargetDrug,
        step.SourceIds,
        step.SelectedCandidateProbability,
        step.NoTransitionProbability,
        step.TransitionSeed,
        step.Reward,
        step.ResistanceProfileAfter,
        step.NewlyResistantAntibiotics,
        step.NewlySusceptibleAntibiotics,
        step.ResistantCountAfter,
        step.SusceptibleCountAfter,
        step.IsTerminalAfter,
        step.TerminationReason);

    private static StrategyMetricsDto ToDto(this PythonStrategyMetrics metrics) => new(
        metrics.CumulativeResistanceBurden,
        metrics.CumulativeReward,
        metrics.TreatmentSteps,
        metrics.InitialResistantCount,
        metrics.FinalResistantCount,
        metrics.FinalSusceptibleCount,
        metrics.ChangeInSusceptibleCount,
        metrics.ResistanceEmergenceEvents,
        metrics.ResistanceEmergenceRate,
        metrics.SusceptibleActionRate,
        metrics.UnsupportedStepCount,
        metrics.CumulativeAntibioticExposure);
}
