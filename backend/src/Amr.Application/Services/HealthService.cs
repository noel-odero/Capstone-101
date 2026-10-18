using Amr.Application.DTOs.Health;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

/// <summary>Combines the API's own liveness with every dependency probe. Ready only when nothing is unhealthy, including the verified model.</summary>
public sealed class HealthService(IEnumerable<IDependencyHealthProbe> probes) : IHealthService
{
    private static readonly ComponentHealthDto Api = new(HealthComponents.Api, HealthState.Healthy, Detail: null);

    public HealthDto GetLiveness() => Summarize([Api]);

    public async Task<HealthDto> GetHealthAsync(CancellationToken cancellationToken)
    {
        var components = new List<ComponentHealthDto> { Api };
        foreach (var probe in probes)
        {
            components.AddRange(await probe.CheckAsync(cancellationToken));
        }

        return Summarize(components);
    }

    private static HealthDto Summarize(IReadOnlyList<ComponentHealthDto> components)
    {
        var worst = components.Max(component => component.Status);
        return new HealthDto(worst, Ready: worst == HealthState.Healthy, components);
    }
}
