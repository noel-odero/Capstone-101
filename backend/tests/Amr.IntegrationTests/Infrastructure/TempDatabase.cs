using Amr.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>A throwaway database on the AMR_TEST_POSTGRES server, dropped on disposal. Tests that need a pristine database (migrations) create their own.</summary>
public sealed class TempDatabase : IAsyncDisposable
{
    private readonly string _admin;
    private readonly string _name;

    private TempDatabase(string admin, string name)
    {
        _admin = admin;
        _name = name;
        ConnectionString = new NpgsqlConnectionStringBuilder(admin) { Database = name, Pooling = false }.ConnectionString;
    }

    public string ConnectionString { get; }

    public static async Task<TempDatabase> CreateAsync()
    {
        var admin = PostgresDatabaseFixture.AdminConnectionString
            ?? throw new InvalidOperationException($"{PostgresDatabaseFixture.AdminVariable} is not set.");
        var name = $"amr_it_{Guid.NewGuid():N}";
        await using var connection = new NpgsqlConnection(admin);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand($"CREATE DATABASE \"{name}\"", connection);
        await command.ExecuteNonQueryAsync();
        return new TempDatabase(admin, name);
    }

    public AmrDbContext CreateContext() =>
        new(new DbContextOptionsBuilder<AmrDbContext>().UseNpgsql(ConnectionString).Options);

    public async ValueTask DisposeAsync()
    {
        NpgsqlConnection.ClearAllPools();
        await using var connection = new NpgsqlConnection(_admin);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand($"DROP DATABASE IF EXISTS \"{_name}\" WITH (FORCE)", connection);
        await command.ExecuteNonQueryAsync();
    }
}
