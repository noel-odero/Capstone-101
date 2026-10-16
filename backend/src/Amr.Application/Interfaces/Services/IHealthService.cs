using Amr.Application.DTOs.Health;

namespace Amr.Application.Interfaces.Services;

public interface IHealthService
{
    /// <summary>Readiness: the API plus every dependency probe. Ready only when the Python service and its verified model are healthy.</summary>
    Task<HealthDto> GetHealthAsync(CancellationToken cancellationToken);

    /// <summary>Liveness: the process answers. Touches no dependency.</summary>
    HealthDto GetLiveness();
}
