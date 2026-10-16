using Amr.Application.DTOs.Simulations;

namespace Amr.Application.Interfaces.Services;

public interface ISimulationService
{
    Task<SimulationDto> RunAsync(CreateSimulationRequest request, CancellationToken cancellationToken);

    /// <returns>Null when no simulation has the id.</returns>
    Task<SimulationDto?> GetAsync(Guid id, CancellationToken cancellationToken);
}
