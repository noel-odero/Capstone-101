using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;
using Amr.Application.PythonContracts;

namespace Amr.Application.Services;

public sealed class SimulationService(IPythonServiceClient python) : ISimulationService
{
    public async Task<SimulationDto> RunAsync(CreateSimulationRequest request, CancellationToken cancellationToken)
    {
        var run = await python.SimulateAsync(
            new PythonSimulateRequest(
                request.ResistanceProfile,
                StrategyMapping.ToPythonId(request.Strategy),
                request.EnvironmentSeed,
                request.PolicySeed),
            cancellationToken);

        var simulation = run.ToSimulationDto();
        var result = simulation.Result!;
        return result.Strategy == request.Strategy && RunResponseChecks.Answers(request, result.InitialProfile, result.EnvironmentSeed)
            ? simulation
            : throw UpstreamErrors.InvalidResponse();
    }

    /// <summary>Needs stored runs. Not implemented until persistence exists.</summary>
    public Task<SimulationDto?> GetAsync(Guid id, CancellationToken cancellationToken) =>
        Task.FromException<SimulationDto?>(PersistenceNotAvailable.Error());
}
