using System.Text.Json;
using System.Text.Json.Nodes;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Analyses;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace Amr.IntegrationTests.Persistence;

/// <summary>The repository against real PostgreSQL, below the HTTP layer: round trips, duplicates, concurrency and failure behavior.</summary>
public class RunRepositoryTests(PostgresDatabaseFixture db) : IClassFixture<PostgresDatabaseFixture>
{
    private static readonly JsonSerializerOptions PublicJson = CreatePublicJson();

    private static JsonSerializerOptions CreatePublicJson()
    {
        var options = new JsonSerializerOptions();
        Amr.Api.Configuration.ApiJsonOptions.Configure(options);
        return options;
    }

    private const string Owner = "test:owner-a";

    private static RunRepository Repository(AmrDbContext context, string? owner = Owner) =>
        new(context, TimeProvider.System, new Amr.TestSupport.FixedCurrentUser(owner), NullLogger<RunRepository>.Instance);

    private static void AssertSameJson<T>(T expected, T actual) =>
        Assert.True(
            JsonNode.DeepEquals(JsonSerializer.SerializeToNode(expected, PublicJson), JsonSerializer.SerializeToNode(actual, PublicJson)),
            $"{JsonSerializer.Serialize(expected, PublicJson)}{Environment.NewLine}{JsonSerializer.Serialize(actual, PublicJson)}");

    private static async Task<SimulationDto> NewSimulationAsync(StrategyKind strategy = StrategyKind.Ppo) =>
        (await SampleDtos.Simulation(strategy)) with { Id = Guid.NewGuid() };

    private static async Task<ComparisonDto> NewComparisonAsync() => (await SampleDtos.Comparison()) with { Id = Guid.NewGuid() };

    [PostgresFact]
    public async Task Research_collections_persist_the_question_and_cannot_include_or_expose_another_users_evidence()
    {
        var owner = $"collections:{Guid.NewGuid():N}";
        var first = await NewComparisonAsync();
        var second = first with { Id = Guid.NewGuid() };
        var foreign = first with { Id = Guid.NewGuid() };
        await using (var write = db.CreateContext())
        {
            await Repository(write, owner).SaveComparisonAsync(first, CancellationToken.None);
            await Repository(write, owner).SaveComparisonAsync(second, CancellationToken.None);
            await Repository(write, owner + ":other").SaveComparisonAsync(foreign, CancellationToken.None);
        }
        await using (var write = db.CreateContext())
        {
            var collections = new AnalysisCollectionRepository(write, new Amr.TestSupport.FixedCurrentUser(owner), TimeProvider.System);
            var saved = await collections.CreateAsync(new() { Name = "  Policy agreement  ", Question = "Why do equal burdens hide different actions?", AnalysisIds = [second.Id, first.Id] }, CancellationToken.None);
            Assert.Equal("Policy agreement", saved.Name);
            Assert.Equal(new[] { second.Id, first.Id }, saved.AnalysisIds);
            var error = await Assert.ThrowsAsync<AmrException>(() => collections.CreateAsync(new() { Name = "Not mine", AnalysisIds = [first.Id, foreign.Id] }, CancellationToken.None));
            Assert.Equal("analysis_not_found", error.Code);
        }
        await using var read = db.CreateContext();
        var mine = new AnalysisCollectionRepository(read, new Amr.TestSupport.FixedCurrentUser(owner), TimeProvider.System);
        var collection = Assert.Single(await mine.ListAsync(CancellationToken.None));
        Assert.Equal("Why do equal burdens hide different actions?", collection.Question);
        Assert.Equal(new[] { second.Id, first.Id }, collection.AnalysisIds);
        var others = new AnalysisCollectionRepository(read, new Amr.TestSupport.FixedCurrentUser(owner + ":other"), TimeProvider.System);
        Assert.Empty(await others.ListAsync(CancellationToken.None));
    }

    [PostgresFact]
    public async Task History_selection_filters_sorting_and_batch_reads_keep_ownership_and_missing_policies()
    {
        var owner = $"history:{Guid.NewGuid():N}";
        var first = await NewComparisonAsync();
        var older = first with { Id = Guid.NewGuid(), CreatedAtUtc = first.CreatedAtUtc.AddMinutes(-1), Dqn = null };
        var foreign = first with { Id = Guid.NewGuid() };
        await using (var write = db.CreateContext())
        {
            await Repository(write, owner).SaveComparisonAsync(first, CancellationToken.None);
            await Repository(write, owner).SaveComparisonAsync(older, CancellationToken.None);
            await Repository(write, owner + ":other").SaveComparisonAsync(foreign, CancellationToken.None);
        }
        await using var read = db.CreateContext();
        var repository = Repository(read, owner);
        var profile = string.Join("", first.Ppo!.InitialProfile);
        var filtered = await repository.ListRecentAsync(new() { Profile = profile, InitialResistantCount = 1, Strategy = "dqn" }, CancellationToken.None);
        Assert.Equal(first.Id, Assert.Single(filtered.Items).Id);
        Assert.Equal(first.Provenance.AntibioticOrder, filtered.Items[0].AntibioticOrder);
        foreach (var sort in new[] { "newest", "oldest", "ppo", "dqn", "baseline", "disagreement" })
        {
            var page = await repository.ListRecentAsync(new() { Sort = sort, PageSize = 1 }, CancellationToken.None);
            Assert.Equal(2, page.TotalCount);
            Assert.Equal(sort == "oldest" ? older.Id : first.Id, Assert.Single(page.Items).Id);
        }
        var missing = await repository.ListRecentAsync(new() { Strategy = "missing_dqn", From = older.CreatedAtUtc.AddSeconds(-1), To = older.CreatedAtUtc.AddSeconds(1) }, CancellationToken.None);
        Assert.Equal(older.Id, Assert.Single(missing.Items).Id);
        Assert.Empty((await repository.ListRecentAsync(new() { Profile = "1111111" }, CancellationToken.None)).Items);
        var batch = await repository.FindManyAsync([first.Id, older.Id, foreign.Id, Guid.NewGuid()], CancellationToken.None);
        Assert.Equal(2, batch.Count);
        Assert.DoesNotContain(batch, item => item.Id == foreign.Id);
        Assert.DoesNotContain(batch.Single(item => item.Id == older.Id).Strategies, result => result.Strategy == StrategyKind.Dqn);
        Assert.NotEmpty(batch.Single(item => item.Id == first.Id).Strategies.Single(result => result.Strategy == StrategyKind.Dqn).Steps);
        var service = new Amr.Application.Services.AnalysisComparisonService(repository);
        var error = await Assert.ThrowsAsync<AmrException>(() => service.CompareAsync(new() { AnalysisIds = [first.Id, foreign.Id] }, CancellationToken.None));
        Assert.Equal("analysis_not_found", error.Code);
    }

    [PostgresTheory]
    [InlineData(StrategyKind.Ppo)]
    [InlineData(StrategyKind.RandomSusceptibleBaseline)]
    public async Task A_simulation_is_saved_and_found_exactly_as_it_was(StrategyKind strategy)
    {
        var simulation = await NewSimulationAsync(strategy);

        await using (var write = db.CreateContext())
        {
            await Repository(write).SaveSimulationAsync(simulation, CancellationToken.None);
        }

        await using var read = db.CreateContext();
        var found = await Repository(read).FindSimulationAsync(simulation.Id, CancellationToken.None);
        AssertSameJson(simulation with { IsPersisted = true }, found!);
    }

    [PostgresFact]
    public async Task Another_users_run_cannot_be_found_or_listed_and_the_owner_is_stored()
    {
        var simulation = await NewSimulationAsync();
        var comparison = await NewComparisonAsync();
        await using (var write = db.CreateContext())
        {
            await Repository(write).SaveSimulationAsync(simulation, CancellationToken.None);
            await Repository(write).SaveComparisonAsync(comparison, CancellationToken.None);
        }

        await using var read = db.CreateContext();
        Assert.NotNull(await Repository(read).FindSimulationAsync(simulation.Id, CancellationToken.None));
        Assert.Null(await Repository(read, "test:owner-b").FindSimulationAsync(simulation.Id, CancellationToken.None));
        Assert.Null(await Repository(read, "test:owner-b").FindComparisonAsync(comparison.Id, CancellationToken.None));
        var others = await Repository(read, "test:nobody-else").ListRecentAsync(new RecentRunsQuery { Page = 1, PageSize = 50 }, CancellationToken.None);
        Assert.Equal(0, others.TotalCount);
        var mine = await Repository(read).ListRecentAsync(new RecentRunsQuery { Page = 1, PageSize = 50 }, CancellationToken.None);
        Assert.Contains(mine.Items, item => item.Id == simulation.Id);
        Assert.Equal(Owner, (await read.ExperimentRuns.SingleAsync(run => run.Id == simulation.Id)).OwnerId);
    }

    [PostgresFact]
    public async Task Storage_requires_an_authenticated_user()
    {
        await using var context = db.CreateContext();
        var simulation = await NewSimulationAsync();

        await Assert.ThrowsAsync<InvalidOperationException>(() => Repository(context, owner: null).SaveSimulationAsync(simulation, CancellationToken.None));
        await Assert.ThrowsAsync<InvalidOperationException>(() => Repository(context, owner: "").FindSimulationAsync(simulation.Id, CancellationToken.None));
        await Assert.ThrowsAsync<InvalidOperationException>(() => Repository(context, owner: null).ListRecentAsync(new RecentRunsQuery(), CancellationToken.None));
    }

    [PostgresFact]
    public async Task A_terminal_simulation_with_no_steps_is_saved_and_found()
    {
        var simulation = (await SampleDtos.TerminalSimulation()) with { Id = Guid.NewGuid() };

        await using var write = db.CreateContext();
        await Repository(write).SaveSimulationAsync(simulation, CancellationToken.None);
        await using var read = db.CreateContext();
        var found = await Repository(read).FindSimulationAsync(simulation.Id, CancellationToken.None);

        Assert.Empty(found!.Result!.Steps);
        AssertSameJson(simulation with { IsPersisted = true }, found);
    }

    [PostgresFact]
    public async Task A_comparison_is_saved_and_found_exactly_as_it_was_and_only_as_a_comparison()
    {
        var comparison = await NewComparisonAsync();

        await using (var write = db.CreateContext())
        {
            await Repository(write).SaveComparisonAsync(comparison, CancellationToken.None);
        }

        await using var read = db.CreateContext();
        var repository = Repository(read);
        AssertSameJson(comparison with { IsPersisted = true }, (await repository.FindComparisonAsync(comparison.Id, CancellationToken.None))!);
        Assert.Null(await repository.FindSimulationAsync(comparison.Id, CancellationToken.None));
    }

    [PostgresFact]
    public async Task Saving_the_same_id_twice_fails_safely_and_keeps_the_first_run()
    {
        var simulation = await NewSimulationAsync();
        await using (var first = db.CreateContext())
        {
            await Repository(first).SaveSimulationAsync(simulation, CancellationToken.None);
        }

        await using var second = db.CreateContext();
        var error = await Assert.ThrowsAsync<AmrException>(() => Repository(second).SaveSimulationAsync(simulation with { SeedConfiguration = simulation.SeedConfiguration with { EnvironmentSeed = 9 } }, CancellationToken.None));

        Assert.Equal((ErrorCategory.Internal, ErrorCodes.PersistenceFailed), (error.Category, error.Code));
        await using var read = db.CreateContext();
        var kept = await Repository(read).FindSimulationAsync(simulation.Id, CancellationToken.None);
        Assert.Equal(simulation.SeedConfiguration.EnvironmentSeed, kept!.SeedConfiguration.EnvironmentSeed);
    }

    [PostgresFact]
    public async Task Many_concurrent_saves_with_separate_contexts_all_succeed_and_share_one_model_version()
    {
        var simulations = await Task.WhenAll(Enumerable.Range(0, 24).Select(_ => NewSimulationAsync()));
        await using var counter = db.CreateContext();
        var runsBefore = await counter.ExperimentRuns.CountAsync();

        await Task.WhenAll(simulations.Select(async simulation =>
        {
            await using var context = db.CreateContext();
            await Repository(context).SaveSimulationAsync(simulation, CancellationToken.None);
        }));

        Assert.Equal(runsBefore + 24, await counter.ExperimentRuns.CountAsync());
        var fingerprint = simulations[0].Provenance;
        Assert.Equal(1, await counter.ModelVersions.CountAsync(model => model.CheckpointSha256 == fingerprint.CheckpointSha256 && model.ModelId == fingerprint.ModelId));
    }

    [PostgresFact]
    public async Task Concurrent_saves_of_one_id_produce_exactly_one_winner_and_clean_failures()
    {
        var simulation = await NewSimulationAsync();

        var outcomes = await Task.WhenAll(Enumerable.Range(0, 8).Select(async _ =>
        {
            await using var context = db.CreateContext();
            try
            {
                await Repository(context).SaveSimulationAsync(simulation, CancellationToken.None);
                return "saved";
            }
            catch (AmrException error)
            {
                return error.Code;
            }
        }));

        Assert.Equal(1, outcomes.Count(outcome => outcome == "saved"));
        Assert.All(outcomes.Where(outcome => outcome != "saved"), outcome => Assert.Equal(ErrorCodes.PersistenceFailed, outcome));
        await using var read = db.CreateContext();
        Assert.Equal(1, await read.ExperimentRuns.CountAsync(run => run.Id == simulation.Id));
        Assert.Equal(1, await read.StrategyRuns.CountAsync(strategy => strategy.ExperimentRunId == simulation.Id));
    }

    [PostgresFact]
    public async Task A_save_that_fails_leaves_no_partial_rows_and_no_new_model_version()
    {
        var simulation = await NewSimulationAsync();
        await using (var first = db.CreateContext())
        {
            await Repository(first).SaveSimulationAsync(simulation, CancellationToken.None);
        }

        await using var counter = db.CreateContext();
        var before = (await counter.ModelVersions.CountAsync(), await counter.StrategyRuns.CountAsync(), await counter.StepTraces.CountAsync());
        var otherModel = simulation with { Provenance = simulation.Provenance with { CheckpointSha256 = new string('c', 64) } };

        await using var second = db.CreateContext();
        await Assert.ThrowsAsync<AmrException>(() => Repository(second).SaveSimulationAsync(otherModel, CancellationToken.None));

        Assert.Equal(before, (await counter.ModelVersions.CountAsync(), await counter.StrategyRuns.CountAsync(), await counter.StepTraces.CountAsync()));
    }

    [PostgresFact]
    public async Task A_cancelled_save_stores_nothing()
    {
        var simulation = await NewSimulationAsync();
        using var cancellation = new CancellationTokenSource();
        await cancellation.CancelAsync();

        await using var context = db.CreateContext();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => Repository(context).SaveSimulationAsync(simulation, cancellation.Token));

        await using var read = db.CreateContext();
        Assert.False(await read.ExperimentRuns.AnyAsync(run => run.Id == simulation.Id));
    }

    [PostgresFact]
    public async Task An_unknown_id_is_null_and_a_page_past_the_end_is_empty()
    {
        await using var context = db.CreateContext();
        var repository = Repository(context);

        Assert.Null(await repository.FindSimulationAsync(Guid.NewGuid(), CancellationToken.None));
        Assert.Null(await repository.FindComparisonAsync(Guid.NewGuid(), CancellationToken.None));
        var page = await repository.ListRecentAsync(new RecentRunsQuery { Page = int.MaxValue, PageSize = 50 }, CancellationToken.None);
        Assert.Empty(page.Items);
    }

    [Fact]
    public async Task An_unreachable_database_is_a_safe_unavailable_error_for_writes_and_reads()
    {
        var options = new DbContextOptionsBuilder<AmrDbContext>().UseNpgsql(AmrApiFactory.UnreachableDatabase).Options;
        var simulation = await NewSimulationAsync();
        await using var context = new AmrDbContext(options);
        var repository = Repository(context);

        var write = await Assert.ThrowsAsync<AmrException>(() => repository.SaveSimulationAsync(simulation, CancellationToken.None));
        var read = await Assert.ThrowsAsync<AmrException>(() => repository.FindSimulationAsync(simulation.Id, CancellationToken.None));
        var list = await Assert.ThrowsAsync<AmrException>(() => repository.ListRecentAsync(new RecentRunsQuery(), CancellationToken.None));

        Assert.All(new[] { write, read, list }, error => Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.DatabaseUnavailable), (error.Category, error.Code)));
        Assert.Contains("No record exists", write.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("127.0.0.1", write.Message, StringComparison.Ordinal);
    }
}
