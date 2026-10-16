using Amr.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>
/// A disposable PostgreSQL database per test class, created on the server named by AMR_TEST_POSTGRES (an admin connection
/// string, for example a throwaway container) and dropped afterwards. Migrations are applied explicitly, exactly as an
/// operator would. When AMR_REQUIRE_POSTGRES is true a missing server fails the tests instead of skipping them.
/// </summary>
public class PostgresDatabaseFixture : IAsyncLifetime
{
    public const string AdminVariable = "AMR_TEST_POSTGRES";
    public const string RequireVariable = "AMR_REQUIRE_POSTGRES";

    private string? _databaseName;
    private string? _admin;

    public static string? AdminConnectionString => Environment.GetEnvironmentVariable(AdminVariable);

    public static bool Required => string.Equals(Environment.GetEnvironmentVariable(RequireVariable), "true", StringComparison.OrdinalIgnoreCase);

    public string ConnectionString { get; private set; } = string.Empty;

    protected virtual bool ApplyMigrations => true;

    public AmrDbContext CreateContext() =>
        new(new DbContextOptionsBuilder<AmrDbContext>().UseNpgsql(ConnectionString).Options);

    public virtual async Task InitializeAsync()
    {
        _admin = AdminConnectionString;
        if (string.IsNullOrWhiteSpace(_admin))
        {
            return;
        }

        _databaseName = $"amr_it_{Guid.NewGuid():N}";
        await using (var connection = new NpgsqlConnection(_admin))
        {
            await connection.OpenAsync();
            await using var command = new NpgsqlCommand($"CREATE DATABASE \"{_databaseName}\"", connection);
            await command.ExecuteNonQueryAsync();
        }

        ConnectionString = new NpgsqlConnectionStringBuilder(_admin) { Database = _databaseName, Pooling = true, MaxPoolSize = 40 }.ConnectionString;
        if (ApplyMigrations)
        {
            await using var context = CreateContext();
            await context.Database.MigrateAsync();
        }
    }

    public async Task DisposeAsync()
    {
        if (_databaseName is null || _admin is null)
        {
            return;
        }

        NpgsqlConnection.ClearAllPools();
        await using var connection = new NpgsqlConnection(_admin);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand($"DROP DATABASE IF EXISTS \"{_databaseName}\" WITH (FORCE)", connection);
        await command.ExecuteNonQueryAsync();
    }
}

/// <summary>A database that exists but has no schema, for testing behavior when migrations were not applied.</summary>
public sealed class UnmigratedPostgresDatabaseFixture : PostgresDatabaseFixture
{
    protected override bool ApplyMigrations => false;
}

public sealed class PostgresFactAttribute : FactAttribute
{
    public PostgresFactAttribute()
    {
        if (PostgresDatabaseFixture.AdminConnectionString is null && !PostgresDatabaseFixture.Required)
        {
            Skip = $"Set {PostgresDatabaseFixture.AdminVariable} to an admin connection string of a disposable PostgreSQL server.";
        }
    }
}

public sealed class PostgresTheoryAttribute : TheoryAttribute
{
    public PostgresTheoryAttribute()
    {
        if (PostgresDatabaseFixture.AdminConnectionString is null && !PostgresDatabaseFixture.Required)
        {
            Skip = $"Set {PostgresDatabaseFixture.AdminVariable} to an admin connection string of a disposable PostgreSQL server.";
        }
    }
}
