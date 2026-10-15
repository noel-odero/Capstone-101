using System.Net;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Services;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application.Services;

public class SimulationServiceTests
{
    private static readonly int[] Profile = [0, 1, 0, 0, 0, 0, 0];

    private static CreateSimulationRequest Request(StrategyKind strategy = StrategyKind.Ppo, long? environmentSeed = 100001, long? policySeed = null, int[]? profile = null) =>
        new() { ResistanceProfile = profile ?? Profile, Strategy = strategy, EnvironmentSeed = environmentSeed, PolicySeed = policySeed };

    private static (SimulationService Service, StubHandler Handler) Serving(string fixture, HttpStatusCode status = HttpStatusCode.OK, string? body = null)
    {
        var handler = StubHandler.Returning(() => body is null ? PythonFixtures.Fixture(fixture, status) : PythonFixtures.Respond(status, body));
        return (new SimulationService(ClientFactory.Create(handler)), handler);
    }

    [Fact]
    public async Task A_ppo_request_is_sent_to_python_with_the_ppo_identifier_and_the_given_seeds()
    {
        var (service, handler) = Serving("simulate_200_ppo");

        await service.RunAsync(Request(StrategyKind.Ppo, 100001, null), CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[0,1,0,0,0,0,0],"strategy":"ppo","environment_seed":100001,"policy_seed":null}""", handler.Requests.Single().Body);
    }

    [Fact]
    public async Task The_public_baseline_is_sent_to_python_as_greedy_and_comes_back_as_the_baseline()
    {
        var (service, handler) = Serving("simulate_200_baseline");

        var simulation = await service.RunAsync(Request(StrategyKind.RandomSusceptibleBaseline, 100001, 900001), CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[0,1,0,0,0,0,0],"strategy":"greedy","environment_seed":100001,"policy_seed":900001}""", handler.Requests.Single().Body);
        Assert.Equal(StrategyKind.RandomSusceptibleBaseline, simulation.Result!.Strategy);
        Assert.Equal("Random Susceptible Baseline", simulation.Result.DisplayLabel);
        Assert.Equal(900001, simulation.Result.PolicySeed);
    }

    [Fact]
    public async Task Model_and_simulator_provenance_is_propagated_exactly()
    {
        var (service, _) = Serving("simulate_200_ppo");

        var simulation = await service.RunAsync(Request(), CancellationToken.None);

        var provenance = simulation.Provenance;
        Assert.Equal("ppo_seed_12000", provenance.ModelId);
        Assert.Equal("MaskablePPO", provenance.Algorithm);
        Assert.Equal("d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093", provenance.CheckpointSha256);
        Assert.Equal("7a5e3e1fe730676a0793674e4ff4aaf3c6ce1177ad5588eed4bb2e5d627edb44", provenance.InteractionDataSha256);
        Assert.Equal(("REF_UNIFORM_SUPPORTED", 8, "susceptible_actions_only"), (provenance.ScenarioId, provenance.Horizon, provenance.ActionMaskRule));
        Assert.Equal(7, provenance.AntibioticOrder.Count);
        Assert.Equal(("client", "not_applicable", null), (simulation.SeedConfiguration.EnvironmentSeedSource, simulation.SeedConfiguration.PolicySeedSource, simulation.SeedConfiguration.PolicySeed));
        Assert.Equal(100001, simulation.SeedConfiguration.EnvironmentSeed);
        Assert.Contains("not clinical advice", simulation.Disclaimer, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task The_reward_specification_passes_through_without_dropping_unknown_keys()
    {
        var body = PythonFixtures.Mutate("simulate_200_ppo", node => node["provenance"]!["reward_specification"]!["future_key"] = "kept");
        var (service, _) = Serving("", body: body);

        var simulation = await service.RunAsync(Request(), CancellationToken.None);

        Assert.Equal(
            new[] { "future_key", "normalization", "objective", "terminal_convention" },
            simulation.Provenance.RewardSpecification.Keys.Order());
        Assert.Equal("kept", simulation.Provenance.RewardSpecification["future_key"].GetString());
    }

    [Fact]
    public async Task Unsupported_transitions_stay_explicit_and_unchanged_in_the_trace()
    {
        var (service, _) = Serving("simulate_200_ppo");

        var result = (await service.RunAsync(Request(), CancellationToken.None)).Result!;

        var unsupported = result.Steps.Where(step => step.TransitionStatus == "unsupported_no_candidate").ToList();
        Assert.NotEmpty(unsupported);
        Assert.Equal(result.Metrics.UnsupportedStepCount, unsupported.Count);
        Assert.All(unsupported, step =>
        {
            Assert.False(step.HasCandidateTransition);
            Assert.Empty(step.CandidateTransitions);
            Assert.Null(step.SelectedOutcome);
            Assert.Equal(step.ResistanceProfileBefore, step.ResistanceProfileAfter);
            Assert.Empty(step.NewlyResistantAntibiotics);
        });
        Assert.All(result.Steps, step => Assert.Equal(step.FeasibleActions.Single(action => action.ActionId == step.ActionId).HasCandidateTransition, step.HasCandidateTransition));
    }

    [Fact]
    public async Task A_valid_terminal_profile_is_a_completed_run_with_no_selected_action()
    {
        var (service, _) = Serving("simulate_200_terminal");

        var simulation = await service.RunAsync(Request(environmentSeed: 1, profile: [1, 1, 1, 1, 1, 1, 1]), CancellationToken.None);

        Assert.Equal(RunStatus.Completed, simulation.Status);
        Assert.Empty(simulation.Result!.Steps);
        Assert.True(Assert.Single(simulation.Result.States).IsTerminal);
        Assert.Equal("no_effective_antibiotic", simulation.Result.TerminationReason);
    }

    [Fact]
    public async Task The_run_is_identified_by_pythons_run_id_and_is_marked_as_not_persisted()
    {
        var (service, _) = Serving("simulate_200_ppo");

        var simulation = await service.RunAsync(Request(), CancellationToken.None);

        var fixtureId = Guid.Parse(System.Text.Json.JsonDocument.Parse(PythonFixtures.Read("simulate_200_ppo")).RootElement.GetProperty("run_id").GetString()!);
        Assert.Equal(fixtureId, simulation.Id);
        Assert.False(simulation.IsPersisted);
        Assert.Equal(RunStatus.Completed, simulation.Status);
        Assert.Null(simulation.Error);
        Assert.Equal(TimeSpan.Zero, simulation.CreatedAtUtc.Offset);
    }

    [Fact]
    public async Task A_result_for_a_different_strategy_than_requested_is_rejected()
    {
        var (service, _) = Serving("simulate_200_ppo");

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(StrategyKind.RandomSusceptibleBaseline), CancellationToken.None));

        Assert.Equal((ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse), (error.Category, error.Code));
    }

    [Theory]
    [InlineData(new int[] { 1, 1, 0, 0, 0, 0, 0 }, 100001L)]
    [InlineData(new int[] { 0, 1, 0, 0, 0, 0, 0 }, 5L)]
    public async Task A_result_for_a_different_profile_or_seed_than_requested_is_rejected(int[] profile, long seed)
    {
        var (service, _) = Serving("simulate_200_ppo");

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(profile: profile, environmentSeed: seed), CancellationToken.None));

        Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
    }

    [Theory]
    [InlineData("run_id", "not-a-guid")]
    [InlineData("created_at_utc", "yesterday-ish")]
    public async Task An_unusable_run_id_or_timestamp_is_an_invalid_response(string field, string value)
    {
        var body = PythonFixtures.Mutate("simulate_200_ppo", node => node[field] = value);
        var (service, _) = Serving("", body: body);

        var error = await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Request(), CancellationToken.None));

        Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
    }

    [Fact]
    public async Task The_cancellation_token_reaches_the_python_request()
    {
        var handler = StubHandler.Hanging();
        var service = new SimulationService(ClientFactory.Create(handler));
        using var cancellation = new CancellationTokenSource();

        var pending = service.RunAsync(Request(), cancellation.Token);
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        Assert.True(handler.Requests.Single().Token.IsCancellationRequested);
    }

    [Fact]
    public async Task A_python_rejection_and_an_unavailable_model_propagate_with_their_public_codes()
    {
        var (rejecting, _) = Serving("validate_422_invalid_context", HttpStatusCode.UnprocessableEntity);
        var (unavailable, _) = Serving("model_503_checkpoint_integrity_failure", HttpStatusCode.ServiceUnavailable);

        var rejected = await Assert.ThrowsAsync<AmrException>(() => rejecting.RunAsync(Request(), CancellationToken.None));
        var down = await Assert.ThrowsAsync<AmrException>(() => unavailable.RunAsync(Request(), CancellationToken.None));

        Assert.Equal(ErrorCodes.ValidationFailed, rejected.Code);
        Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable), (down.Category, down.Code));
        Assert.DoesNotContain("checkpoint", down.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Retrieval_is_explicitly_not_implemented_without_persistence_and_never_invents_a_run()
    {
        var (service, handler) = Serving("simulate_200_ppo");

        var error = await Assert.ThrowsAsync<AmrException>(() => service.GetAsync(Guid.NewGuid(), CancellationToken.None));

        Assert.Equal((ErrorCategory.NotImplemented, ErrorCodes.PersistenceNotAvailable), (error.Category, error.Code));
        Assert.Equal(0, handler.CallCount);
    }
}
