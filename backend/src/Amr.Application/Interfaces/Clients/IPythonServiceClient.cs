using Amr.Application.PythonContracts;

namespace Amr.Application.Interfaces.Clients;

/// <summary>
/// Typed access to the private Python scientific service. Failures surface as
/// <see cref="Errors.AmrException"/> with a stable code; GetHealthAsync reports an unavailable model as a result instead.
/// </summary>
public interface IPythonServiceClient
{
    Task<PythonHealth> GetHealthAsync(CancellationToken cancellationToken);

    Task<PythonModelInfo> GetModelAsync(CancellationToken cancellationToken);

    Task<PythonAntibiotics> GetAntibioticsAsync(CancellationToken cancellationToken);

    Task<PythonProfileValidation> ValidateProfileAsync(IReadOnlyList<int> resistanceProfile, CancellationToken cancellationToken);

    Task<PythonSimulation> SimulateAsync(PythonSimulateRequest request, CancellationToken cancellationToken);

    Task<PythonComparison> CompareAsync(PythonCompareRequest request, CancellationToken cancellationToken);
}
