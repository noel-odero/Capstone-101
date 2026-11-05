using Amr.Infrastructure.Persistence;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql;

namespace Amr.IntegrationTests.Persistence;

/// <summary>Migrations against real PostgreSQL, each on a pristine database. Migrations are applied only by an explicit call, as an operator would.</summary>
public class MigrationTests
{
    [PostgresFact]
    public async Task Unique_sample_labels_preserve_existing_duplicates_and_avoid_numbered_label_collisions()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();
        await context.GetService<IMigrator>().MigrateAsync("20261028082441_RequireEmailVerification");
        var owner = "migration-test";
        var firstId = Guid.NewGuid();
        var secondId = Guid.NewGuid();
        var reservedId = Guid.NewGuid();
        var longLabel = new string('x', 80);
        await context.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO samples (id, owner_id, label, initial_profile, added_at_utc) VALUES
            ({firstId}, {owner}, 'UTI-024', ARRAY[0,0,0,0,0,0,0], '2026-01-01T00:00:00Z'),
            ({secondId}, {owner}, 'uti-024', ARRAY[1,0,0,0,0,0,0], '2026-01-02T00:00:00Z'),
            ({reservedId}, {owner}, 'UTI-024 (2)', ARRAY[0,0,0,0,0,0,0], '2026-01-03T00:00:00Z'),
            ({Guid.NewGuid()}, {owner}, {longLabel}, ARRAY[0,0,0,0,0,0,0], '2026-01-04T00:00:00Z'),
            ({Guid.NewGuid()}, {owner}, {longLabel}, ARRAY[0,0,0,0,0,0,0], '2026-01-05T00:00:00Z')
            """);

        await context.Database.MigrateAsync();

        var samples = await context.Samples.ToListAsync();
        Assert.Equal(5, samples.Count);
        Assert.Equal(5, samples.Select(sample => sample.NormalizedLabel).Distinct().Count());
        Assert.Equal("UTI-024", samples.Single(sample => sample.Id == firstId).Label);
        Assert.Equal("uti-024 (3)", samples.Single(sample => sample.Id == secondId).Label);
        Assert.Equal("UTI-024 (2)", samples.Single(sample => sample.Id == reservedId).Label);
        Assert.Equal(new[] { 1, 0, 0, 0, 0, 0, 0 }, samples.Single(sample => sample.Id == secondId).InitialProfile);
        Assert.All(samples, sample => Assert.InRange(sample.Label.Length, 1, 80));
    }

    private static async Task<List<string>> TablesAsync(string connectionString)
    {
        await using var connection = new NpgsqlConnection(connectionString);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1", connection);
        await using var reader = await command.ExecuteReaderAsync();
        var tables = new List<string>();
        while (await reader.ReadAsync())
        {
            tables.Add(reader.GetString(0));
        }

        return tables;
    }

    [PostgresFact]
    public async Task A_new_database_has_nothing_until_migrations_are_applied_explicitly()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();

        Assert.Empty(await TablesAsync(temp.ConnectionString));
        Assert.NotEmpty(await context.Database.GetPendingMigrationsAsync());
    }

    [PostgresFact]
    public async Task Migrating_creates_the_schema_records_the_migration_and_is_a_no_op_the_second_time()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();

        await context.Database.MigrateAsync();
        var applied = (await context.Database.GetAppliedMigrationsAsync()).ToList();
        await context.Database.MigrateAsync();

        Assert.Equal(context.Database.GetMigrations().Count(), applied.Count);
        Assert.EndsWith("_InitialCreate", applied[0], StringComparison.Ordinal);
        Assert.EndsWith("_AddRunOwner", applied[1], StringComparison.Ordinal);
        Assert.EndsWith("_AddUsers", applied[2], StringComparison.Ordinal);
        Assert.EndsWith("_AddSamples", applied[3], StringComparison.Ordinal);
        Assert.EndsWith("_AddDqnStrategy", applied[4], StringComparison.Ordinal);
        Assert.EndsWith("_AddAnalysisCollections", applied[5], StringComparison.Ordinal);
        Assert.Equal(applied, (await context.Database.GetAppliedMigrationsAsync()).ToList());
        Assert.Equal(new[] { "__EFMigrationsHistory", "analysis_collections", "email_verifications", "experiment_runs", "model_versions", "samples", "step_traces", "strategy_runs", "users" }, await TablesAsync(temp.ConnectionString));
        Assert.Empty(await context.Database.GetPendingMigrationsAsync());
        Assert.False(context.Database.HasPendingModelChanges());
    }

    [PostgresFact]
    public async Task The_idempotent_script_applies_to_an_empty_database_and_can_be_applied_again()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();
        var script = context.GetService<IMigrator>().GenerateScript(options: MigrationsSqlGenerationOptions.Idempotent);

        await context.Database.ExecuteSqlRawAsync(script.Replace("{", "{{", StringComparison.Ordinal).Replace("}", "}}", StringComparison.Ordinal));
        await context.Database.ExecuteSqlRawAsync(script.Replace("{", "{{", StringComparison.Ordinal).Replace("}", "}}", StringComparison.Ordinal));

        Assert.Contains("model_versions", await TablesAsync(temp.ConnectionString));
        Assert.Empty(await context.Database.GetPendingMigrationsAsync());
    }

    [PostgresFact]
    public async Task The_migration_can_be_rolled_back_and_applied_again()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();
        await context.Database.MigrateAsync();

        await context.GetService<IMigrator>().MigrateAsync("0");
        var afterRollback = await TablesAsync(temp.ConnectionString);
        await context.Database.MigrateAsync();

        Assert.Equal(new[] { "__EFMigrationsHistory" }, afterRollback);
        Assert.Contains("step_traces", await TablesAsync(temp.ConnectionString));
    }

    [PostgresFact]
    public async Task Migrating_needs_no_data_and_leaves_existing_rows_alone_on_a_second_run()
    {
        await using var temp = await TempDatabase.CreateAsync();
        await using var context = temp.CreateContext();
        await context.Database.MigrateAsync();
        var simulation = (await SampleDtos.Simulation()) with { Id = Guid.NewGuid() };
        await new RunRepository(context, TimeProvider.System, new Amr.TestSupport.FixedCurrentUser("test:owner"), Microsoft.Extensions.Logging.Abstractions.NullLogger<RunRepository>.Instance).SaveSimulationAsync(simulation, CancellationToken.None);

        await context.Database.MigrateAsync();

        Assert.Equal(1, await context.ExperimentRuns.CountAsync());
    }
}
