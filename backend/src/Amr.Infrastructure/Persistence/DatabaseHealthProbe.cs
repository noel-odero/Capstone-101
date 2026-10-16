using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Readiness of the database: reachable, and every migration applied. Migrations are never applied by the API, so a
/// reachable database with pending migrations is reported as not ready instead of failing later on the first save.
/// Only stable codes are reported; connection details never are.
/// </summary>
public sealed partial class DatabaseHealthProbe(AmrDbContext db, IOptions<DatabaseOptions> options, ILogger<DatabaseHealthProbe> logger) : IDependencyHealthProbe
{
    public async Task<IReadOnlyList<ComponentHealthDto>> CheckAsync(CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(options.Value.HealthTimeoutSeconds));
        try
        {
            var pending = await db.Database.GetPendingMigrationsAsync(timeout.Token);
            return [pending.Any() ? Unhealthy(ErrorCodes.DatabaseMigrationsPending) : new ComponentHealthDto(HealthComponents.Database, HealthState.Healthy, Detail: null)];
        }
        catch (Exception exception) when (!cancellationToken.IsCancellationRequested)
        {
            LogProbeFailed(logger, exception);
            return [Unhealthy(ErrorCodes.DatabaseUnavailable)];
        }
    }

    private static ComponentHealthDto Unhealthy(string code) => new(HealthComponents.Database, HealthState.Unhealthy, code);

    [LoggerMessage(Level = LogLevel.Warning, Message = "Database health probe failed.")]
    private static partial void LogProbeFailed(ILogger logger, Exception exception);
}
