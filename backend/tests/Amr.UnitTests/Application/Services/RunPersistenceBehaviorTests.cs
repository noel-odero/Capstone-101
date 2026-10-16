using System.Net;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Mappings;
using Amr.Application.Services;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application.Services;

/// <summary>When a run is saved, what is saved, and what the caller is told. The repository is a recording double.</summary>
public class RunPersistenceBehaviorTests
{
    private static readonly int[] Profile = [0, 1, 0, 0, 0, 0, 0];

    private static CreateSimulationRequest Simulate(long? seed = 100001) =>
        new() { ResistanceProfile = Profile, Strategy = StrategyKind.Ppo, EnvironmentSeed = seed };

    private static CreateComparisonRequest Compare(long? seed = 100001) =>
        new() { ResistanceProfile = Profile, EnvironmentSeed = seed, PolicySeed = 900001 };

    private static SimulationService Simulations(FakeRunRepository runs, string fixture = "simulate_200_ppo", HttpStatusCode status = HttpStatusCode.OK, string? body = null) =>
        new(ClientFactory.Create(StubHandler.Returning(() => body is null ? PythonFixtures.Fixture(fixture, status) : PythonFixtures.Respond(status, body))), runs);

    private static ComparisonService Comparisons(FakeRunRepository runs, string? body = null) =>
        new(ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body ?? PythonFixtures.Read("compare_200")))), runs);

    [Fact]
    public async Task A_simulation_is_saved_unpersisted_and_returned_persisted_only_after_the_save_succeeded()
    {
        var runs = new FakeRunRepository();

        var returned = await Simulations(runs).RunAsync(Simulate(), CancellationToken.None);

        var saved = Assert.Single(runs.SavedSimulations);
        Assert.False(saved.IsPersisted);
        Assert.True(returned.IsPersisted);
        Assert.Equal(saved.Id, returned.Id);
        Assert.Equal(RunStatus.Completed, returned.Status);
    }

    [Fact]
    public async Task A_failed_save_is_the_outcome_and_no_result_is_returned()
    {
        var runs = new FakeRunRepository { SaveFailure = PersistenceErrors.Unavailable() };

        var error = await Assert.ThrowsAsync<AmrException>(() => Simulations(runs).RunAsync(Simulate(), CancellationToken.None));

        Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.DatabaseUnavailable), (error.Category, error.Code));
        Assert.Contains("No record exists", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_persistence_failure_that_is_not_availability_is_a_500()
    {
        var runs = new FakeRunRepository { SaveFailure = PersistenceErrors.Failed() };

        var error = await Assert.ThrowsAsync<AmrException>(() => Simulations(runs).RunAsync(Simulate(), CancellationToken.None));

        Assert.Equal((ErrorCategory.Internal, ErrorCodes.PersistenceFailed), (error.Category, error.Code));
    }

    [Fact]
    public async Task The_python_call_is_made_once_even_when_the_save_fails()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("simulate_200_ppo"));
        var service = new SimulationService(ClientFactory.Create(handler), new FakeRunRepository { SaveFailure = PersistenceErrors.Failed() });

        await Assert.ThrowsAsync<AmrException>(() => service.RunAsync(Simulate(), CancellationToken.None));

        Assert.Equal(1, handler.CallCount);
    }

    [Fact]
    public async Task Nothing_is_saved_when_python_fails_or_the_response_does_not_answer_the_request()
    {
        var runs = new FakeRunRepository();

        await Assert.ThrowsAsync<AmrException>(() => Simulations(runs, "simulate_500_internal_error", HttpStatusCode.InternalServerError).RunAsync(Simulate(), CancellationToken.None));
        await Assert.ThrowsAsync<AmrException>(() => Simulations(runs).RunAsync(Simulate(seed: 5), CancellationToken.None));
        var wrongStrategy = PythonFixtures.Mutate("simulate_200_ppo", node => node["result"]!["strategy"] = "greedy");
        await Assert.ThrowsAsync<AmrException>(() => Simulations(runs, body: wrongStrategy).RunAsync(Simulate(), CancellationToken.None));
        var unknownMetrics = PythonFixtures.Mutate("simulate_200_ppo", node => node["metric_definitions"]!.AsObject().Remove("treatment_steps"));
        await Assert.ThrowsAsync<AmrException>(() => Simulations(runs, body: unknownMetrics).RunAsync(Simulate(), CancellationToken.None));

        Assert.Empty(runs.Calls);
    }

    [Fact]
    public async Task A_comparison_is_saved_only_after_its_contract_and_request_match_are_verified()
    {
        var runs = new FakeRunRepository();

        var returned = await Comparisons(runs).RunAsync(Compare(), CancellationToken.None);

        var saved = Assert.Single(runs.SavedComparisons);
        Assert.False(saved.IsPersisted);
        Assert.True(returned.IsPersisted);
        Assert.True(returned.Contract!.Verified);
        Assert.Equal(["save-comparison"], runs.Calls);
    }

    [Theory]
    [InlineData("verified")]
    [InlineData("identical")]
    [InlineData("seed")]
    public async Task A_comparison_that_breaks_the_contract_is_never_saved(string violation)
    {
        var runs = new FakeRunRepository();
        var body = PythonFixtures.Mutate("compare_200", node =>
        {
            switch (violation)
            {
                case "verified":
                    node["comparison_contract"]!["verified"] = false;
                    break;
                case "identical":
                    node["comparison_contract"]!["transition_outcomes_guaranteed_identical"] = true;
                    break;
                default:
                    node["greedy"]!["environment_seed"] = 5;
                    break;
            }
        });

        var error = await Assert.ThrowsAsync<AmrException>(() => Comparisons(runs, body).RunAsync(Compare(), CancellationToken.None));

        Assert.Equal(ErrorCodes.ComparisonContractViolation, error.Code);
        Assert.Empty(runs.Calls);
    }

    [Fact]
    public async Task A_failed_comparison_save_is_reported_and_not_claimed()
    {
        var runs = new FakeRunRepository { SaveFailure = PersistenceErrors.Unavailable() };

        var error = await Assert.ThrowsAsync<AmrException>(() => Comparisons(runs).RunAsync(Compare(), CancellationToken.None));

        Assert.Equal(ErrorCodes.DatabaseUnavailable, error.Code);
        Assert.Empty(runs.SavedComparisons);
    }

    [Fact]
    public async Task Retrieval_returns_whatever_the_repository_holds_and_null_for_nothing()
    {
        var stored = await Simulations(new FakeRunRepository()).RunAsync(Simulate(), CancellationToken.None);
        var runs = new FakeRunRepository { Simulation = id => id == stored.Id ? stored : null };
        var service = Simulations(runs);

        Assert.Same(stored, await service.GetAsync(stored.Id, CancellationToken.None));
        Assert.Null(await service.GetAsync(Guid.NewGuid(), CancellationToken.None));
        Assert.Null(await new ComparisonService(ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Fixture("compare_200"))), runs).GetAsync(Guid.NewGuid(), CancellationToken.None));
    }

    [Fact]
    public async Task A_recommendation_exists_only_for_a_completed_ppo_simulation()
    {
        var ppo = await Simulations(new FakeRunRepository()).RunAsync(Simulate(), CancellationToken.None);
        var baseline = await Simulations(new FakeRunRepository(), "simulate_200_baseline")
            .RunAsync(new() { ResistanceProfile = Profile, Strategy = StrategyKind.RandomSusceptibleBaseline, EnvironmentSeed = 100001, PolicySeed = 900001 }, CancellationToken.None);
        var runs = new FakeRunRepository { Simulation = id => id == ppo.Id ? ppo : id == baseline.Id ? baseline : null };
        var service = new RecommendationService(runs);

        var found = await service.GetBySimulationAsync(ppo.Id, CancellationToken.None);

        Assert.Equal(ppo.Id, found!.SimulationId);
        Assert.Equal(StrategyKind.Ppo, found.Strategy);
        Assert.Same(ppo.Result!.Steps, found.Steps);
        Assert.Equal(RecommendationMappings.Interpretation, found.Interpretation);
        Assert.Null(await service.GetBySimulationAsync(baseline.Id, CancellationToken.None));
        Assert.Null(await service.GetBySimulationAsync(Guid.NewGuid(), CancellationToken.None));
    }

    [Fact]
    public async Task A_failed_run_never_yields_a_recommendation()
    {
        var ppo = await Simulations(new FakeRunRepository()).RunAsync(Simulate(), CancellationToken.None);
        var failed = ppo with { Status = RunStatus.Failed, Result = null, Error = new(ErrorCodes.InternalError, "failed") };

        Assert.Null(failed.ToRecommendationDto());
    }

    [Fact]
    public async Task History_asks_the_repository_for_the_requested_page()
    {
        var runs = new FakeRunRepository();

        var page = await new RunHistoryService(runs).GetRecentAsync(new() { Page = 3, PageSize = 7 }, CancellationToken.None);

        Assert.Equal((3, 7, 0), (page.Page, page.PageSize, page.TotalCount));
        Assert.Equal(["list-recent"], runs.Calls);
    }
}
