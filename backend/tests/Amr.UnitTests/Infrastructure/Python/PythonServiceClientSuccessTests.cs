using System.Net;
using System.Text.Json;
using Amr.Application.PythonContracts;

namespace Amr.UnitTests.Infrastructure.Python;

public class PythonServiceClientSuccessTests
{
    private static StubHandler Serving(string fixture, HttpStatusCode status = HttpStatusCode.OK) =>
        StubHandler.Returning(() => PythonFixtures.Fixture(fixture, status));

    [Fact]
    public async Task Health_of_a_ready_service_is_returned()
    {
        var handler = Serving("health_200");

        var health = await ClientFactory.Create(handler).GetHealthAsync(CancellationToken.None);

        Assert.True(health.ModelReady);
        Assert.Equal("ok", health.Status);
        Assert.Equal("ppo_seed_12000", health.ModelId);
        Assert.Equal(new Uri("http://python.test/internal/health"), handler.Requests.Single().Uri);
        Assert.Equal(HttpMethod.Get, handler.Requests.Single().Method);
    }

    [Fact]
    public async Task Health_of_a_service_whose_model_failed_verification_is_returned_not_thrown()
    {
        var health = await ClientFactory.Create(Serving("health_503_model_unavailable", HttpStatusCode.ServiceUnavailable)).GetHealthAsync(CancellationToken.None);

        Assert.False(health.ModelReady);
        Assert.Equal("unavailable", health.Status);
        Assert.Equal("checkpoint_integrity_failure", health.ErrorCode);
        Assert.Null(health.CheckpointSha256);
    }

    [Fact]
    public async Task Model_metadata_carries_the_verified_provenance()
    {
        var model = await ClientFactory.Create(Serving("model_200")).GetModelAsync(CancellationToken.None);

        Assert.Equal("ppo_seed_12000", model.ModelId);
        Assert.Equal("d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093", model.CheckpointSha256);
        Assert.Equal("7a5e3e1fe730676a0793674e4ff4aaf3c6ce1177ad5588eed4bb2e5d627edb44", model.InteractionDataSha256);
        Assert.Equal(("REF_UNIFORM_SUPPORTED", 8), (model.ScenarioId, model.Horizon));
        Assert.Equal(7, model.AntibioticOrder.Count);
        Assert.Equal("susceptible_actions_only", model.ActionMasking.Rule);
        Assert.Equal(new[] { 15 }, model.Observation.Shape);
        Assert.Equal(new[] { 0, 7 }, model.Observation.Layout["resistance_indicators"]);
        Assert.Contains("unsupported_no_candidate", model.TransitionStatusDefinitions.Keys);
    }

    [Fact]
    public async Task Antibiotics_keep_the_canonical_order()
    {
        var catalogue = await ClientFactory.Create(Serving("antibiotics_200")).GetAntibioticsAsync(CancellationToken.None);

        Assert.Equal(Enumerable.Range(0, 7), catalogue.Antibiotics.Select(item => item.ActionId));
        Assert.Equal("CIPROFLOXACIN", catalogue.Antibiotics[0].Name);
        Assert.Equal("CEFTAZIDIME", catalogue.Antibiotics[^1].Name);
        Assert.Equal(0, catalogue.ResistanceEncoding["susceptible"]);
        Assert.Equal(1, catalogue.ResistanceEncoding["resistant"]);
    }

    [Fact]
    public async Task Profile_validation_posts_snake_case_and_reads_feasible_actions_with_support_flags()
    {
        var handler = Serving("validate_200_open");

        var result = await ClientFactory.Create(handler).ValidateProfileAsync([1, 0, 0, 1, 0, 0, 0], CancellationToken.None);

        var request = handler.Requests.Single();
        Assert.Equal((HttpMethod.Post, new Uri("http://python.test/internal/profiles/validate")), (request.Method, request.Uri));
        Assert.Equal("""{"resistance_profile":[1,0,0,1,0,0,0]}""", request.Body);
        Assert.True(result.Valid);
        Assert.False(result.IsTerminal);
        Assert.Equal(new[] { 1, 2, 4, 5, 6 }, result.FeasibleActionIds);
        Assert.Contains(result.FeasibleActions, action => action is { Antibiotic: "GENTAMICIN", HasCandidateTransition: false });
    }

    [Fact]
    public async Task A_valid_all_resistant_profile_is_a_terminal_result_with_no_feasible_actions()
    {
        var result = await ClientFactory.Create(Serving("validate_200_terminal")).ValidateProfileAsync([1, 1, 1, 1, 1, 1, 1], CancellationToken.None);

        Assert.True(result.IsTerminal);
        Assert.Equal("no_effective_antibiotic", result.TerminalReason);
        Assert.Empty(result.FeasibleActions);
    }

    [Fact]
    public async Task A_ppo_simulation_round_trips_every_trace_field_including_unsupported_transitions()
    {
        var handler = Serving("simulate_200_ppo");

        var run = await ClientFactory.Create(handler).SimulateAsync(
            new PythonSimulateRequest([0, 1, 0, 0, 0, 0, 0], PythonStrategyIds.Ppo, 100001, null), CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[0,1,0,0,0,0,0],"strategy":"ppo","environment_seed":100001,"policy_seed":null}""", handler.Requests.Single().Body);
        Assert.Equal("simulation", run.Kind);
        Assert.Equal("d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093", run.Provenance.CheckpointSha256);
        Assert.Equal("normalized_resistance_burden", run.Provenance.RewardSpecification["objective"].GetString());
        Assert.Equal(7, run.Provenance.RewardSpecification["normalization"].GetInt32());
        Assert.Equal("not_applicable", run.SeedConfiguration.PolicySeedSource);
        Assert.Null(run.SeedConfiguration.PolicySeed);

        var result = run.Result;
        Assert.Equal((PythonStrategyIds.Ppo, "Frozen PPO Policy"), (result.Strategy, result.DisplayLabel));
        Assert.Equal((8, 9), (result.Steps.Count, result.States.Count));
        Assert.Equal("maximum_horizon", result.TerminationReason);
        var unsupported = result.Steps.Where(step => step.TransitionStatus == "unsupported_no_candidate").ToList();
        Assert.NotEmpty(unsupported);
        Assert.Equal(result.Metrics.UnsupportedStepCount, unsupported.Count);
        Assert.All(unsupported, step =>
        {
            Assert.False(step.HasCandidateTransition);
            Assert.Null(step.SelectedOutcome);
            Assert.Equal(step.ResistanceProfileBefore, step.ResistanceProfileAfter);
        });
        Assert.All(result.Steps, step => Assert.True(step.SelectedDrugSusceptible));
    }

    [Fact]
    public async Task A_baseline_simulation_reports_its_policy_seed_and_the_internal_greedy_identifier()
    {
        var handler = Serving("simulate_200_baseline");

        var run = await ClientFactory.Create(handler).SimulateAsync(
            new PythonSimulateRequest([0, 1, 0, 0, 0, 0, 0], PythonStrategyIds.Greedy, 100001, 900001), CancellationToken.None);

        Assert.Contains("\"strategy\":\"greedy\"", handler.Requests.Single().Body, StringComparison.Ordinal);
        Assert.Equal((PythonStrategyIds.Greedy, "Random Susceptible Baseline"), (run.Result.Strategy, run.Result.DisplayLabel));
        Assert.Equal(900001, run.Result.PolicySeed);
        Assert.Equal(900001, run.SeedConfiguration.PolicySeed);
    }

    [Fact]
    public async Task A_terminal_start_is_a_run_with_no_steps_and_one_terminal_state()
    {
        var run = await ClientFactory.Create(Serving("simulate_200_terminal")).SimulateAsync(
            new PythonSimulateRequest([1, 1, 1, 1, 1, 1, 1], PythonStrategyIds.Ppo, 1, null), CancellationToken.None);

        Assert.Empty(run.Result.Steps);
        var state = Assert.Single(run.Result.States);
        Assert.True(state.IsTerminal);
        Assert.Equal("no_effective_antibiotic", run.Result.TerminationReason);
        Assert.Equal(8, run.Result.Metrics.CumulativeResistanceBurden);
    }

    [Fact]
    public async Task A_comparison_returns_both_strategies_and_the_verified_contract()
    {
        var handler = Serving("compare_200");

        var comparison = await ClientFactory.Create(handler).CompareAsync(
            new PythonCompareRequest([0, 1, 0, 0, 0, 0, 0], 100001, 900001), CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[0,1,0,0,0,0,0],"environment_seed":100001,"policy_seed":900001}""", handler.Requests.Single().Body);
        Assert.Equal(new Uri("http://python.test/internal/compare"), handler.Requests.Single().Uri);
        Assert.Equal(PythonStrategyIds.Ppo, comparison.Ppo.Strategy);
        Assert.Equal(PythonStrategyIds.Greedy, comparison.Greedy.Strategy);
        Assert.Equal((8, 8), (comparison.Ppo.Steps.Count, comparison.Greedy.Steps.Count));
        var contract = comparison.ComparisonContract;
        Assert.True(contract.Verified);
        Assert.False(contract.TransitionOutcomesGuaranteedIdentical);
        Assert.True(contract.TransitionSeedSchedule.SharedByStepIndex);
        Assert.Contains("transition_seed_schedule", contract.ChecksPassed);
        Assert.Equal(100001, contract.Shared.EnvironmentSeed);
        Assert.Equal("susceptible_actions_only", contract.Shared.ActionMaskConfiguration.Rule);
        Assert.Contains("do not guarantee identical transition outcomes", comparison.PairingSemantics, StringComparison.Ordinal);
        Assert.Equal(
            comparison.Ppo.Steps.Select(step => step.TransitionSeed),
            comparison.Greedy.Steps.Select(step => step.TransitionSeed));
    }

    [Fact]
    public async Task Members_the_client_does_not_know_are_ignored()
    {
        var body = PythonFixtures.Mutate("model_200", node => node["added_by_a_future_service_version"] = "x");
        var handler = StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body));

        var model = await ClientFactory.Create(handler).GetModelAsync(CancellationToken.None);

        Assert.Equal("ppo_seed_12000", model.ModelId);
    }

    [Fact]
    public async Task Reward_specification_keys_pass_through_verbatim_including_future_ones()
    {
        var body = PythonFixtures.Mutate("simulate_200_ppo", node => node["provenance"]!["reward_specification"]!["future_key"] = 3);
        var handler = StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body));

        var run = await ClientFactory.Create(handler).SimulateAsync(
            new PythonSimulateRequest([0, 1, 0, 0, 0, 0, 0], PythonStrategyIds.Ppo, 1, null), CancellationToken.None);

        Assert.Equal(
            new[] { "future_key", "normalization", "objective", "terminal_convention" },
            run.Provenance.RewardSpecification.Keys.Order());
        Assert.Equal(JsonValueKind.Number, run.Provenance.RewardSpecification["future_key"].ValueKind);
    }
}
