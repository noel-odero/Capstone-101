using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;
using Amr.Application.PythonContracts;

namespace Amr.Application.Services;

public sealed class SimulationService(IPythonServiceClient python, IRunRepository runs) : ISimulationService
{
    /// <summary>
    /// Runs in Python, verifies the response answers the request, then stores it. IsPersisted is set only after the commit.
    /// If storing fails the exception says the run has no record; the Python execution is not retried or repeated.
    /// </summary>
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
        if (result.Strategy != request.Strategy || !RunResponseChecks.Answers(request, result.InitialProfile, result.EnvironmentSeed))
        {
            throw UpstreamErrors.InvalidResponse();
        }

        await runs.SaveSimulationAsync(simulation, cancellationToken);
        return simulation with { IsPersisted = true };
    }

    public Task<SimulationDto?> GetAsync(Guid id, CancellationToken cancellationToken) =>
        runs.FindSimulationAsync(id, cancellationToken);
}
