using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence;
using Amr.Infrastructure.Persistence.Entities;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.IntegrationTests.Persistence;

/// <summary>The database itself enforces the design: keys, uniqueness, cascades, ranges and the completed-only status. Needs AMR_TEST_POSTGRES.</summary>
public class SchemaConstraintTests(PostgresDatabaseFixture db) : IClassFixture<PostgresDatabaseFixture>
{
    private static readonly DateTimeOffset Now = new(2026, 10, 15, 12, 0, 0, TimeSpan.Zero);

    private static string? SqlState(Exception exception)
    {
        for (var current = exception; current is not null; current = current.InnerException)
        {
            if (current is PostgresException postgres)
            {
                return postgres.SqlState;
            }
        }

        return null;
    }

    private static async Task<(ModelVersion Model, ExperimentRun Run)> NewGraphAsync(StrategyKind strategy = StrategyKind.Ppo)
    {
        var simulation = (await SampleDtos.Simulation(strategy)) with { Id = Guid.NewGuid() };
        var model = RunEntityMapper.ToEntity(simulation.Provenance, Now);
        return (model, RunEntityMapper.ToEntity(simulation, model.Id, Now, "test:owner"));
    }

    private async Task<Guid> SaveGraphAsync()
    {
        var (model, run) = await NewGraphAsync();
        await using var context = db.CreateContext();
        if (!await context.ModelVersions.AnyAsync(existing => existing.Fingerprint == model.Fingerprint))
        {
            context.ModelVersions.Add(model);
        }
        else
        {
            run.ModelVersionId = await context.ModelVersions.Where(existing => existing.Fingerprint == model.Fingerprint).Select(existing => existing.Id).SingleAsync();
        }

        context.ExperimentRuns.Add(run);
        await context.SaveChangesAsync();
        return run.Id;
    }

    private async Task<List<T>> QueryAsync<T>(string sql, Func<NpgsqlDataReader, T> read)
    {
        await using var connection = new NpgsqlConnection(db.ConnectionString);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand(sql, connection);
        await using var reader = await command.ExecuteReaderAsync();
        var rows = new List<T>();
        while (await reader.ReadAsync())
        {
            rows.Add(read(reader));
        }

        return rows;
    }

    [PostgresFact]
    public async Task The_tables_exist_and_the_foreign_keys_have_the_designed_delete_behavior()
    {
        var tables = await QueryAsync("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1", reader => reader.GetString(0));
        var keys = await QueryAsync(
            "SELECT conrelid::regclass::text, confrelid::regclass::text, confdeltype::text FROM pg_constraint WHERE contype = 'f' ORDER BY 1, 2",
            reader => (reader.GetString(0), reader.GetString(1), reader.GetString(2)));

        Assert.Equal(new[] { "__EFMigrationsHistory", "experiment_runs", "model_versions", "samples", "step_traces", "strategy_runs", "users" }, tables);
        Assert.Equal(
            new[] { ("experiment_runs", "model_versions", "r"), ("experiment_runs", "samples", "r"), ("step_traces", "strategy_runs", "c"), ("strategy_runs", "experiment_runs", "c") },
            keys.OrderBy(key => key.Item1, StringComparer.Ordinal).ThenBy(key => key.Item2, StringComparer.Ordinal));
    }

    [PostgresFact]
    public async Task Uniqueness_and_ordering_are_backed_by_indexes_including_a_descending_recent_runs_index()
    {
        var indexes = await QueryAsync("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'", reader => (reader.GetString(0), reader.GetString(1)));
        var byName = indexes.ToDictionary(index => index.Item1, index => index.Item2);

        Assert.Contains("UNIQUE", byName["ux_model_versions_fingerprint"], StringComparison.Ordinal);
        Assert.Contains("UNIQUE", byName["ux_strategy_runs_run_strategy"], StringComparison.Ordinal);
        Assert.Contains("(experiment_run_id, strategy)", byName["ux_strategy_runs_run_strategy"], StringComparison.Ordinal);
        Assert.Contains("(strategy_run_id, step_index)", byName["PK_step_traces"], StringComparison.Ordinal);
        Assert.Contains("(created_at_utc DESC, id DESC)", byName["ix_experiment_runs_recent"], StringComparison.Ordinal);
    }

    [PostgresFact]
    public async Task A_duplicate_run_id_a_duplicate_strategy_and_a_duplicate_step_are_rejected_with_unique_violations()
    {
        var (model, run) = await NewGraphAsync();
        await using (var seed = db.CreateContext())
        {
            if (!await seed.ModelVersions.AnyAsync(existing => existing.Fingerprint == model.Fingerprint))
            {
                seed.ModelVersions.Add(model);
                await seed.SaveChangesAsync();
            }
        }

        var modelId = await db.CreateContext().ModelVersions.Where(existing => existing.Fingerprint == model.Fingerprint).Select(existing => existing.Id).SingleAsync();
        run.ModelVersionId = modelId;
        await using (var first = db.CreateContext())
        {
            first.ExperimentRuns.Add(run);
            await first.SaveChangesAsync();
        }

        var (_, duplicate) = await NewGraphAsync();
        duplicate.Id = run.Id;
        duplicate.ModelVersionId = modelId;
        foreach (var strategy in duplicate.StrategyRuns)
        {
            strategy.ExperimentRunId = run.Id;
        }

        await using var duplicateContext = db.CreateContext();
        duplicateContext.ExperimentRuns.Add(duplicate);
        Assert.Equal("23505", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => duplicateContext.SaveChangesAsync())));

        var existingStrategy = run.StrategyRuns.Single();
        await using var twin = db.CreateContext();
        twin.StrategyRuns.Add(new StrategyRun
        {
            Id = Guid.NewGuid(),
            ExperimentRunId = run.Id,
            Strategy = existingStrategy.Strategy,
            DisplayLabel = "twin",
            InitialProfile = existingStrategy.InitialProfile,
            FinalProfile = existingStrategy.FinalProfile,
            TerminationReason = existingStrategy.TerminationReason,
            StatesJson = "[]",
        });
        Assert.Equal("23505", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => twin.SaveChangesAsync())));

        var step = existingStrategy.StepTraces[0];
        await using var repeated = db.CreateContext();
        repeated.StepTraces.Add(new StepTrace
        {
            StrategyRunId = existingStrategy.Id,
            StepIndex = step.StepIndex,
            ResistanceProfileBefore = step.ResistanceProfileBefore,
            Antibiotic = step.Antibiotic,
            FeasibleActionsJson = "[]",
            TransitionStatus = step.TransitionStatus,
            CandidateTransitionsJson = "[]",
            SourceIds = [],
            ResistanceProfileAfter = step.ResistanceProfileAfter,
            NewlyResistantAntibiotics = [],
            NewlySusceptibleAntibiotics = [],
        });
        Assert.Equal("23505", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => repeated.SaveChangesAsync())));
    }

    [PostgresFact]
    public async Task Rows_cannot_point_at_parents_that_do_not_exist_and_a_referenced_model_version_cannot_be_deleted()
    {
        var (_, run) = await NewGraphAsync();
        run.ModelVersionId = Guid.NewGuid();
        await using var orphanRun = db.CreateContext();
        orphanRun.ExperimentRuns.Add(run);
        Assert.Equal("23503", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => orphanRun.SaveChangesAsync())));

        var savedId = await SaveGraphAsync();
        await using var orphanStrategy = db.CreateContext();
        orphanStrategy.StrategyRuns.Add(new StrategyRun { Id = Guid.NewGuid(), ExperimentRunId = Guid.NewGuid(), Strategy = StrategyKind.Ppo, DisplayLabel = "x", InitialProfile = new int[7], FinalProfile = new int[7], TerminationReason = "x", StatesJson = "[]" });
        Assert.Equal("23503", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => orphanStrategy.SaveChangesAsync())));

        await using var restricted = db.CreateContext();
        var modelId = await restricted.ExperimentRuns.Where(existing => existing.Id == savedId).Select(existing => existing.ModelVersionId).SingleAsync();
        var error = await Assert.ThrowsAnyAsync<Exception>(() => restricted.Database.ExecuteSqlInterpolatedAsync($"DELETE FROM model_versions WHERE id = {modelId}"));
        Assert.Equal("23503", SqlState(error));
    }

    [PostgresFact]
    public async Task Deleting_a_run_removes_its_strategy_runs_and_steps_but_not_the_model_version()
    {
        var id = await SaveGraphAsync();
        await using var context = db.CreateContext();
        var modelId = await context.ExperimentRuns.Where(run => run.Id == id).Select(run => run.ModelVersionId).SingleAsync();

        await context.Database.ExecuteSqlInterpolatedAsync($"DELETE FROM experiment_runs WHERE id = {id}");

        Assert.Empty(await context.StrategyRuns.Where(strategy => strategy.ExperimentRunId == id).ToListAsync());
        Assert.Empty(await context.StepTraces.Where(step => step.StrategyRun.ExperimentRunId == id).ToListAsync());
        Assert.True(await context.ModelVersions.AnyAsync(model => model.Id == modelId));
    }

    [PostgresTheory]
    [InlineData("UPDATE experiment_runs SET status = 'failed' WHERE id = '{id}'")]
    [InlineData("UPDATE experiment_runs SET kind = 'comparison' WHERE id = '{id}'")]
    [InlineData("UPDATE experiment_runs SET kind = 'other' WHERE id = '{id}'")]
    [InlineData("UPDATE experiment_runs SET environment_seed = 4294967296 WHERE id = '{id}'")]
    [InlineData("UPDATE experiment_runs SET environment_seed = -1 WHERE id = '{id}'")]
    [InlineData("UPDATE experiment_runs SET initial_profile = ARRAY[0,1] WHERE id = '{id}'")]
    [InlineData("UPDATE strategy_runs SET strategy = 'greedy' WHERE experiment_run_id = '{id}'")]
    [InlineData("UPDATE strategy_runs SET unsupported_step_count = treatment_steps + 1 WHERE experiment_run_id = '{id}'")]
    [InlineData("UPDATE strategy_runs SET final_resistant_count = 8 WHERE experiment_run_id = '{id}'")]
    [InlineData("UPDATE step_traces SET action_id = 7 WHERE strategy_run_id IN (SELECT id FROM strategy_runs WHERE experiment_run_id = '{id}')")]
    [InlineData("UPDATE step_traces SET step_index = -1 WHERE step_index = 0 AND strategy_run_id IN (SELECT id FROM strategy_runs WHERE experiment_run_id = '{id}')")]
    [InlineData("UPDATE step_traces SET resistance_profile_after = ARRAY[0] WHERE strategy_run_id IN (SELECT id FROM strategy_runs WHERE experiment_run_id = '{id}')")]
    [InlineData("UPDATE model_versions SET checkpoint_sha256 = 'XYZ' WHERE id IN (SELECT model_version_id FROM experiment_runs WHERE id = '{id}')")]
    [InlineData("UPDATE model_versions SET horizon = 0 WHERE id IN (SELECT model_version_id FROM experiment_runs WHERE id = '{id}')")]
    public async Task Invalid_values_are_rejected_by_check_constraints(string statement)
    {
        var id = await SaveGraphAsync();
        await using var context = db.CreateContext();

        var error = await Assert.ThrowsAnyAsync<Exception>(() => context.Database.ExecuteSqlRawAsync(statement.Replace("{id}", id.ToString(), StringComparison.Ordinal)));

        Assert.Equal("23514", SqlState(error));
    }

    [PostgresFact]
    public async Task A_second_model_version_with_the_same_fingerprint_is_rejected()
    {
        var (model, _) = await NewGraphAsync();
        await using (var first = db.CreateContext())
        {
            if (!await first.ModelVersions.AnyAsync(existing => existing.Fingerprint == model.Fingerprint))
            {
                first.ModelVersions.Add(model);
                await first.SaveChangesAsync();
            }
        }

        var (twin, _) = await NewGraphAsync();
        await using var second = db.CreateContext();
        second.ModelVersions.Add(twin);

        Assert.Equal("23505", SqlState(await Assert.ThrowsAnyAsync<Exception>(() => second.SaveChangesAsync())));
    }

    [PostgresFact]
    public async Task Steps_inserted_out_of_order_are_read_back_in_step_order_and_state_the_run_they_belong_to()
    {
        var (model, run) = await NewGraphAsync();
        run.StrategyRuns.Single().StepTraces.Reverse();
        await using (var context = db.CreateContext())
        {
            var existing = await context.ModelVersions.Where(candidate => candidate.Fingerprint == model.Fingerprint).Select(candidate => (Guid?)candidate.Id).SingleOrDefaultAsync();
            if (existing is null)
            {
                context.ModelVersions.Add(model);
            }
            else
            {
                run.ModelVersionId = existing.Value;
            }

            context.ExperimentRuns.Add(run);
            await context.SaveChangesAsync();
        }

        await using var read = db.CreateContext();
        var indexes = await read.StepTraces.Where(step => step.StrategyRun.ExperimentRunId == run.Id).OrderBy(step => step.StepIndex).Select(step => step.StepIndex).ToListAsync();

        Assert.Equal(Enumerable.Range(0, run.StrategyRuns.Single().StepTraces.Count), indexes);
    }

    [PostgresFact]
    public async Task The_ef_model_and_the_migrations_agree()
    {
        await using var context = db.CreateContext();

        Assert.False(context.Database.HasPendingModelChanges());
        Assert.Empty(await context.Database.GetPendingMigrationsAsync());
    }
}
