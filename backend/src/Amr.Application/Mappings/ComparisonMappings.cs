using Amr.Application.DTOs.Comparisons;
using Amr.Application.Metrics;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.Application.Mappings;

public static class ComparisonMappings
{
    public static ComparisonDto ToComparisonDto(this PythonComparison run) => new(
        RunMappings.ParseRunId(run.RunId),
        RunStatus.Completed,
        IsPersisted: false,
        RunMappings.ParseTimestamp(run.CreatedAtUtc),
        run.Provenance.ToDto(),
        run.SeedConfiguration.ToDto(),
        run.PairingSemantics,
        run.ComparisonContract.ToDto(),
        run.Ppo.ToDto(),
        run.Greedy.ToDto(),
        Error: null,
        MetricCatalogue.Describe(run.MetricDefinitions),
        run.SingleRunCaveat,
        run.Disclaimer) { Dqn = run.Dqn?.ToDto() };

    private static ComparisonContractDto ToDto(this PythonComparisonContract contract) => new(
        contract.Verified,
        contract.ChecksPassed,
        new SharedConfigurationDto(
            contract.Shared.InitialProfile,
            contract.Shared.EnvironmentSeed,
            contract.Shared.ScenarioId,
            contract.Shared.Horizon,
            contract.Shared.InteractionDataSha256,
            contract.Shared.RewardSpecification,
            new ActionMaskConfigurationDto(contract.Shared.ActionMaskConfiguration.Enabled, contract.Shared.ActionMaskConfiguration.Rule)),
        new TransitionSeedScheduleDto(contract.TransitionSeedSchedule.SharedByStepIndex, contract.TransitionSeedSchedule.StepsCompared, contract.TransitionSeedSchedule.Meaning),
        contract.TransitionOutcomesGuaranteedIdentical,
        new ObservedDivergenceDto(contract.Observed.StepsCompared, contract.Observed.StepsWithSameAction, contract.Observed.FirstDivergentStep, contract.Observed.TrajectoriesIdentical));
}
