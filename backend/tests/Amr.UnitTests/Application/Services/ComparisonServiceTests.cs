using System.Net;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.Errors;
using Amr.Application.Services;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application.Services;

public class ComparisonServiceTests
{
    private static readonly int[] Profile = [0, 1, 0, 0, 0, 0, 0];

    private static CreateComparisonRequest Request(long? environmentSeed = 100001, long? policySeed = 900001, int[]? profile = null) =>
        new() { ResistanceProfile = profile ?? Profile, EnvironmentSeed = environmentSeed, PolicySeed = policySeed };

    private static (ComparisonService Service, StubHandler Handler) Serving(string? body = null, string fixture = "compare_200", HttpStatusCode status = HttpStatusCode.OK)
    {
        var handler = StubHandler.Returning(() => body is null ? PythonFixtures.Fixture(fixture, status) : PythonFixtures.Respond(status, body));
        return (new ComparisonService(ClientFactory.Create(handler), new FakeRunRepository()), handler);
    }

    [Fact]
    public async Task The_request_goes_to_python_unchanged_without_horizon_or_scenario_options()
    {
        var (service, handler) = Serving();

        await service.RunAsync(Request(), CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[0,1,0,0,0,0,0],"environment_seed":100001,"policy_seed":900001}""", handler.Requests.Single().Body);
    }

    [Fact]
    public async Task All_three_strategy_results_are_returned_with_public_identifiers_and_labels()
    {
        var (service, _) = Serving();

        var comparison = await service.RunAsync(Request(), CancellationToken.None);

        Assert.Equal((StrategyKind.Ppo, "PPO"), (comparison.Ppo!.Strategy, comparison.Ppo.DisplayLabel));
        Assert.Equal((StrategyKind.Dqn, "DQN"), (comparison.Dqn!.Strategy, comparison.Dqn.DisplayLabel));
        Assert.Equal("dqn_public_v2_seed_15000", comparison.Dqn.Model!.ModelId);
        Assert.Equal((StrategyKind.RandomSusceptibleBaseline, "Random Susceptible Baseline"), (comparison.Baseline!.Strategy, comparison.Baseline.DisplayLabel));
        Assert.Equal((8, 8), (comparison.Ppo.Steps.Count, comparison.Baseline.Steps.Count));
        Assert.Null(comparison.Ppo.PolicySeed);
        Assert.Equal(900001, comparison.Baseline.PolicySeed);
    }

    [Fact]
    public async Task The_verified_contract_and_its_honest_limits_are_preserved()
    {
        var (service, _) = Serving();

        var comparison = await service.RunAsync(Request(), CancellationToken.None);

        var contract = comparison.Contract!;
        Assert.True(contract.Verified);
        Assert.False(contract.TransitionOutcomesGuaranteedIdentical);
        Assert.True(contract.TransitionSeedSchedule.SharedByStepIndex);
        Assert.Equal(8, contract.TransitionSeedSchedule.StepsCompared);
        Assert.Equal(
            new[] { "initial_profile", "environment_seed", "scenario_id", "horizon", "interaction_data_sha256", "reward_specification", "action_mask_configuration", "transition_seed_schedule" },
            contract.ChecksPassed);
        Assert.Equal(100001, contract.Shared.EnvironmentSeed);
        Assert.Equal(("susceptible_actions_only", true), (contract.Shared.ActionMaskConfiguration.Rule, contract.Shared.ActionMaskConfiguration.Enabled));
        Assert.Contains("do not guarantee identical transition outcomes", comparison.PairingSemantics, StringComparison.Ordinal);
        Assert.Contains("does not establish a superior strategy", comparison.SingleRunCaveat, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Provenance_seed_configuration_and_the_reward_map_are_propagated()
    {
        var body = PythonFixtures.Mutate("compare_200", node =>
        {
            node["provenance"]!["reward_specification"]!["future_key"] = 1;
            node["comparison_contract"]!["shared"]!["reward_specification"]!["future_key"] = 1;
        });
        var (service, _) = Serving(body);

        var comparison = await service.RunAsync(Request(), CancellationToken.None);

        Assert.Equal("1747b68cb572cc320c7c53ae105dfa9dd6827f689839b35c4f2bcf9520384001", comparison.Provenance.CheckpointSha256);
        Assert.Equal("af62f389fe92b4ecddfbc1df6c967c5da9992ed928c09dd3a68673819f42591c", comparison.Contract!.Shared.InteractionDataSha256);
        Assert.Equal(("REF_UNIFORM_SUPPORTED", 8), (comparison.Contract.Shared.ScenarioId, comparison.Contract.Shared.Horizon));
        Assert.Contains("future_key", comparison.Provenance.RewardSpecification.Keys);
        Assert.Contains("future_key", comparison.Contract.Shared.RewardSpecification.Keys);
        Assert.Equal((100001, 900001), (comparison.SeedConfiguration.EnvironmentSeed, comparison.SeedConfiguration.PolicySeed));
        Assert.True(comparison.IsPersisted);
        Assert.Equal(RunStatus.Completed, comparison.Status);
    }

    [Fact]
    public async Task Unsupported_transitions_are_preserved_for_both_strategies()
    {
        var (service, _) = Serving();

        var comparison = await service.RunAsync(Request(), CancellationToken.None);

        foreach (var strategy in new[] { comparison.Ppo!, comparison.Baseline! })
        {
            var unsupported = strategy.Steps.Where(step => step.TransitionStatus == "unsupported_no_candidate").ToList();
            Assert.Equal(strategy.Metrics.UnsupportedStepCount, unsupported.Count);
            Assert.All(unsupported, step => Assert.False(step.HasCandidateTransition));
        }
    }

    [Fact]
    public async Task Pythons_contract_violation_is_preserved_as_a_500_class_error_with_no_result()
    {
        var (service, _) = Serving(fixture: "compare_500_contract_violation", status: HttpStatusCode.InternalServerError);

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(), CancellationToken.None));

        Assert.Equal((ErrorCategory.Internal, ErrorCodes.ComparisonContractViolation), (error.Category, error.Code));
        Assert.DoesNotContain("existing_matched_run_validation", error.Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("verified", false)]
    [InlineData("transition_outcomes_guaranteed_identical", true)]
    public async Task A_success_body_that_contradicts_the_contract_is_rejected_like_a_violation(string field, bool value)
    {
        var body = PythonFixtures.Mutate("compare_200", node => node["comparison_contract"]![field] = value);
        var (service, _) = Serving(body);

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(), CancellationToken.None));

        Assert.Equal(ErrorCodes.ComparisonContractViolation, error.Code);
    }

    [Fact]
    public async Task Strategies_in_the_wrong_slots_are_an_invalid_response()
    {
        var body = PythonFixtures.Mutate("compare_200", node =>
        {
            node["ppo"]!["strategy"] = "greedy";
            node["greedy"]!["strategy"] = "ppo";
        });
        var (service, _) = Serving(body);

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(), CancellationToken.None));

        Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
    }

    [Fact]
    public async Task A_new_comparison_cannot_silently_omit_dqn()
    {
        var body = PythonFixtures.Mutate("compare_200", node => node["dqn"] = null);
        var (service, _) = Serving(body);
        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(), CancellationToken.None));
        Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
    }

    [Theory]
    [InlineData(new int[] { 1, 1, 0, 0, 0, 0, 0 }, 100001L)]
    [InlineData(new int[] { 0, 1, 0, 0, 0, 0, 0 }, 7L)]
    public async Task A_pair_that_answers_a_different_profile_or_seed_than_requested_breaks_the_contract(int[] profile, long seed)
    {
        var (service, _) = Serving();

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(seed, 900001, profile), CancellationToken.None));

        Assert.Equal(ErrorCodes.ComparisonContractViolation, error.Code);
    }

    [Fact]
    public async Task The_cancellation_token_reaches_the_python_request()
    {
        var handler = StubHandler.Hanging();
        var service = new ComparisonService(ClientFactory.Create(handler), new FakeRunRepository());
        using var cancellation = new CancellationTokenSource();

        var pending = service.RunAsync(Request(), cancellation.Token);
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        Assert.True(handler.Requests.Single().Token.IsCancellationRequested);
    }
}
