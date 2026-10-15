using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Microsoft.Extensions.Logging;

namespace Amr.Infrastructure.Python;

/// <summary>Reports whether the Python service is reachable and, separately, whether it has a verified frozen model.</summary>
public sealed partial class PythonServiceHealthChecker(IPythonServiceClient client, ILogger<PythonServiceHealthChecker> logger)
    : IDependencyHealthProbe
{
    public async Task<IReadOnlyList<ComponentHealthDto>> CheckAsync(CancellationToken cancellationToken)
    {
        try
        {
            var health = await client.GetHealthAsync(cancellationToken);
            var modelReady = health.ModelReady && health.Status == "ok";
            return
            [
                new ComponentHealthDto(HealthComponents.PythonService, HealthState.Healthy, Detail: null),
                new ComponentHealthDto(HealthComponents.Model, modelReady ? HealthState.Healthy : HealthState.Unhealthy, modelReady ? null : ErrorCodes.ModelUnavailable),
            ];
        }
        catch (AmrException exception)
        {
            LogProbeFailed(logger, exception.Code);
            return
            [
                new ComponentHealthDto(HealthComponents.PythonService, HealthState.Unhealthy, exception.Code),
                new ComponentHealthDto(HealthComponents.Model, HealthState.Unhealthy, ErrorCodes.ModelUnavailable),
            ];
        }
    }

    [LoggerMessage(Level = LogLevel.Warning, Message = "Python service health probe failed with {ErrorCode}.")]
    private static partial void LogProbeFailed(ILogger logger, string errorCode);
}
