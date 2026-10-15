using Amr.Application.DTOs.Health;

namespace Amr.Application.Interfaces.Services;

public interface IHealthService
{
    Task<HealthDto> GetHealthAsync(CancellationToken cancellationToken);
}
