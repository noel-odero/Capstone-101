using System.Text.Json;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;
using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence.Entities;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Converts between public run DTOs and persistence entities. Values are copied, never recomputed, so a retrieved run is
/// the run Python produced. Entities never leave Infrastructure.
/// </summary>
internal static class RunEntityMapper
{
    public static ExperimentRun ToEntity(SimulationDto simulation, Guid modelVersionId, DateTimeOffset recordedAtUtc, string ownerId)
    {
        var result = simulation.Result ?? throw new InvalidOperationException("Only completed simulations are stored.");
        var run = NewRun(simulation.Id, ownerId, ExperimentKind.Simulation, simulation.Status, simulation.CreatedAtUtc, modelVersionId, recordedAtUtc,
            result.InitialProfile, simulation.Provenance, simulation.SeedConfiguration, simulation.MetricDefinitions, simulation.Disclaimer);
        run.StrategyRuns.Add(ToEntity(result, run.Id));
        return run;
    }

    public static ExperimentRun ToEntity(ComparisonDto comparison, Guid modelVersionId, DateTimeOffset recordedAtUtc, string ownerId)
    {
        var (ppo, baseline, contract) = (comparison.Ppo, comparison.Baseline, comparison.Contract);
        if (ppo is null || baseline is null || contract is null)
        {
            throw new InvalidOperationException("Only completed comparisons are stored.");
        }

        var run = NewRun(comparison.Id, ownerId, ExperimentKind.Comparison, comparison.Status, comparison.CreatedAtUtc, modelVersionId, recordedAtUtc,
            contract.Shared.InitialProfile, comparison.Provenance, comparison.SeedConfiguration, comparison.MetricDefinitions, comparison.Disclaimer);
        run.PairingSemantics = comparison.PairingSemantics;
        run.SingleRunCaveat = comparison.SingleRunCaveat;
        run.ComparisonContractJson = PersistenceJson.Serialize(contract);
        run.StrategyRuns.Add(ToEntity(ppo, run.Id));
        run.StrategyRuns.Add(ToEntity(baseline, run.Id));
        return run;
    }

    public static SimulationDto ToSimulationDto(ExperimentRun run) => new(
        run.Id,
        run.Status,
        IsPersisted: true,
        run.CreatedAtUtc,
        ToProvenance(run),
        ToSeedConfiguration(run),
        ToResult(run.StrategyRuns.Single()),
        Error: null,
        PersistenceJson.Deserialize<Dictionary<string, MetricDefinitionDto>>(run.MetricDefinitionsJson),
        run.Disclaimer);

    public static ComparisonDto ToComparisonDto(ExperimentRun run) => new(
        run.Id,
        run.Status,
        IsPersisted: true,
        run.CreatedAtUtc,
        ToProvenance(run),
        ToSeedConfiguration(run),
        run.PairingSemantics!,
        PersistenceJson.Deserialize<ComparisonContractDto>(run.ComparisonContractJson!),
        ToResult(run.StrategyRuns.Single(strategy => strategy.Strategy == StrategyKind.Ppo)),
        ToResult(run.StrategyRuns.Single(strategy => strategy.Strategy == StrategyKind.RandomSusceptibleBaseline)),
        Error: null,
        PersistenceJson.Deserialize<Dictionary<string, MetricDefinitionDto>>(run.MetricDefinitionsJson),
        run.SingleRunCaveat!,
        run.Disclaimer);

    private static ExperimentRun NewRun(
        Guid id,
        string ownerId,
        ExperimentKind kind,
        RunStatus status,
        DateTimeOffset createdAtUtc,
        Guid modelVersionId,
        DateTimeOffset recordedAtUtc,
        IReadOnlyList<int> initialProfile,
        ModelProvenanceDto provenance,
        SeedConfigurationDto seeds,
        IReadOnlyDictionary<string, MetricDefinitionDto> metricDefinitions,
        string disclaimer) => new()
        {
            Id = id,
            OwnerId = ownerId,
            Kind = kind,
            Status = status,
            ModelVersionId = modelVersionId,
            ServiceVersion = provenance.ServiceVersion,
            CreatedAtUtc = createdAtUtc,
            RecordedAtUtc = recordedAtUtc,
            InitialProfile = [.. initialProfile],
            EnvironmentSeed = seeds.EnvironmentSeed,
            EnvironmentSeedSource = seeds.EnvironmentSeedSource,
            PolicySeed = seeds.PolicySeed,
            PolicySeedSource = seeds.PolicySeedSource,
            SeedNotes = [.. seeds.Notes],
            Disclaimer = disclaimer,
            MetricDefinitionsJson = PersistenceJson.Serialize(metricDefinitions),
        };

    public static ModelVersion ToEntity(ModelProvenanceDto provenance, DateTimeOffset recordedAtUtc) => new()
    {
        Id = Guid.NewGuid(),
        Fingerprint = ModelVersionFingerprint.Compute(provenance),
        ModelId = provenance.ModelId,
        Algorithm = provenance.Algorithm,
        CheckpointSha256 = provenance.CheckpointSha256,
        InteractionDataSha256 = provenance.InteractionDataSha256,
        ScenarioId = provenance.ScenarioId,
        Horizon = provenance.Horizon,
        ActionMaskRule = provenance.ActionMaskRule,
        RewardSpecificationJson = PersistenceJson.Serialize(provenance.RewardSpecification),
        AntibioticOrder = [.. provenance.AntibioticOrder],
        FirstRecordedAtUtc = recordedAtUtc,
    };

    private static StrategyRun ToEntity(StrategyResultDto result, Guid experimentRunId)
    {
        var strategyRunId = Guid.NewGuid();
        var metrics = result.Metrics;
        return new StrategyRun
        {
            Id = strategyRunId,
            ExperimentRunId = experimentRunId,
            Strategy = result.Strategy,
            DisplayLabel = result.DisplayLabel,
            InitialProfile = [.. result.InitialProfile],
            FinalProfile = [.. result.FinalProfile],
            EnvironmentSeed = result.EnvironmentSeed,
            PolicySeed = result.PolicySeed,
            TerminationReason = result.TerminationReason,
            StatesJson = PersistenceJson.Serialize(result.States),
            CumulativeResistanceBurden = metrics.CumulativeResistanceBurden,
            CumulativeReward = metrics.CumulativeReward,
            TreatmentSteps = metrics.TreatmentSteps,
            InitialResistantCount = metrics.InitialResistantCount,
            FinalResistantCount = metrics.FinalResistantCount,
            FinalSusceptibleCount = metrics.FinalSusceptibleCount,
            ChangeInSusceptibleCount = metrics.ChangeInSusceptibleCount,
            ResistanceEmergenceEvents = metrics.ResistanceEmergenceEvents,
            ResistanceEmergenceRate = metrics.ResistanceEmergenceRate,
            SusceptibleActionRate = metrics.SusceptibleActionRate,
            UnsupportedStepCount = metrics.UnsupportedStepCount,
            CumulativeAntibioticExposure = metrics.CumulativeAntibioticExposure,
            StepTraces = [.. result.Steps.Select(step => ToEntity(step, strategyRunId))],
        };
    }

    private static StepTrace ToEntity(StepTraceDto step, Guid strategyRunId) => new()
    {
        StrategyRunId = strategyRunId,
        StepIndex = step.StepIndex,
        TreatmentStepBefore = step.TreatmentStepBefore,
        TreatmentStepAfter = step.TreatmentStepAfter,
        ResistanceProfileBefore = [.. step.ResistanceProfileBefore],
        ActionId = step.ActionId,
        Antibiotic = step.Antibiotic,
        FeasibleActionsJson = PersistenceJson.Serialize(step.FeasibleActions),
        SelectedDrugSusceptible = step.SelectedDrugSusceptible,
        TransitionStatus = step.TransitionStatus,
        HasCandidateTransition = step.HasCandidateTransition,
        CandidateTransitionsJson = PersistenceJson.Serialize(step.CandidateTransitions),
        SelectedOutcome = step.SelectedOutcome,
        SelectedTargetDrug = step.SelectedTargetDrug,
        SourceIds = [.. step.SourceIds],
        SelectedCandidateProbability = step.SelectedCandidateProbability,
        NoTransitionProbability = step.NoTransitionProbability,
        TransitionSeed = step.TransitionSeed,
        Reward = step.Reward,
        ResistanceProfileAfter = [.. step.ResistanceProfileAfter],
        NewlyResistantAntibiotics = [.. step.NewlyResistantAntibiotics],
        NewlySusceptibleAntibiotics = [.. step.NewlySusceptibleAntibiotics],
        ResistantCountAfter = step.ResistantCountAfter,
        SusceptibleCountAfter = step.SusceptibleCountAfter,
        IsTerminalAfter = step.IsTerminalAfter,
        TerminationReason = step.TerminationReason,
    };

    private static ModelProvenanceDto ToProvenance(ExperimentRun run)
    {
        var model = run.ModelVersion;
        return new ModelProvenanceDto(
            model.ModelId,
            model.Algorithm,
            model.CheckpointSha256,
            model.InteractionDataSha256,
            model.ScenarioId,
            model.Horizon,
            PersistenceJson.Deserialize<Dictionary<string, JsonElement>>(model.RewardSpecificationJson),
            model.ActionMaskRule,
            model.AntibioticOrder,
            run.ServiceVersion);
    }

    private static SeedConfigurationDto ToSeedConfiguration(ExperimentRun run) =>
        new(run.EnvironmentSeed, run.EnvironmentSeedSource, run.PolicySeed, run.PolicySeedSource, run.SeedNotes);

    private static StrategyResultDto ToResult(StrategyRun strategy) => new(
        strategy.Strategy,
        strategy.DisplayLabel,
        strategy.InitialProfile,
        strategy.FinalProfile,
        strategy.EnvironmentSeed,
        strategy.PolicySeed,
        strategy.TerminationReason,
        PersistenceJson.Deserialize<List<StateSnapshotDto>>(strategy.StatesJson),
        strategy.StepTraces.OrderBy(step => step.StepIndex).Select(ToStepDto).ToList(),
        new StrategyMetricsDto(
            strategy.CumulativeResistanceBurden,
            strategy.CumulativeReward,
            strategy.TreatmentSteps,
            strategy.InitialResistantCount,
            strategy.FinalResistantCount,
            strategy.FinalSusceptibleCount,
            strategy.ChangeInSusceptibleCount,
            strategy.ResistanceEmergenceEvents,
            strategy.ResistanceEmergenceRate,
            strategy.SusceptibleActionRate,
            strategy.UnsupportedStepCount,
            strategy.CumulativeAntibioticExposure));

    private static StepTraceDto ToStepDto(StepTrace step) => new(
        step.StepIndex,
        step.TreatmentStepBefore,
        step.TreatmentStepAfter,
        step.ResistanceProfileBefore,
        step.ActionId,
        step.Antibiotic,
        PersistenceJson.Deserialize<List<FeasibleActionDto>>(step.FeasibleActionsJson),
        step.SelectedDrugSusceptible,
        step.TransitionStatus,
        step.HasCandidateTransition,
        PersistenceJson.Deserialize<List<CandidateTransitionDto>>(step.CandidateTransitionsJson),
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
}
