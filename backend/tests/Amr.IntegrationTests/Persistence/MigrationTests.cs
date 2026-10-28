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
