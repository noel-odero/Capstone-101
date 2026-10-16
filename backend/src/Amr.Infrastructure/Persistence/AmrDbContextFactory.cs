using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Used only by `dotnet ef`. The connection string comes from the same environment variable as the API
/// (ConnectionStrings__Amr), so no credential is ever written to a file.
/// </summary>
public sealed class AmrDbContextFactory : IDesignTimeDbContextFactory<AmrDbContext>
{
    public AmrDbContext CreateDbContext(string[] args)
    {
        var connectionString = Environment.GetEnvironmentVariable("ConnectionStrings__Amr");
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            throw new InvalidOperationException("Set the ConnectionStrings__Amr environment variable before running dotnet ef.");
        }

        var options = new DbContextOptionsBuilder<AmrDbContext>().UseNpgsql(connectionString).Options;
        return new AmrDbContext(options);
    }
}
