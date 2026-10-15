using Amr.Application.DTOs.Health;

namespace Amr.Application.Interfaces.Clients;

/// <summary>Reports the health of one external dependency as public components. Implementations never throw for an unhealthy dependency.</summary>
public interface IDependencyHealthProbe
{
    Task<IReadOnlyList<ComponentHealthDto>> CheckAsync(CancellationToken cancellationToken);
}
