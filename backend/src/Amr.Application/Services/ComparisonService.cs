using Amr.Application.DTOs.Comparisons;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.Application.Services;

public sealed class ComparisonService(IPythonServiceClient python) : IComparisonService
{
    public async Task<ComparisonDto> RunAsync(CreateComparisonRequest request, CancellationToken cancellationToken)
    {
        var run = await python.CompareAsync(
            new PythonCompareRequest(request.ResistanceProfile, request.EnvironmentSeed, request.PolicySeed),
            cancellationToken);

        // Python raises comparison_contract_violation instead of returning an unverified pair; a body that says otherwise is rejected too.
        if (!run.ComparisonContract.Verified || run.ComparisonContract.TransitionOutcomesGuaranteedIdentical)
        {
            throw ComparisonErrors.ContractViolation();
        }

        var comparison = run.ToComparisonDto();
        var (ppo, baseline) = (comparison.Ppo!, comparison.Baseline!);
        if (ppo.Strategy != StrategyKind.Ppo || baseline.Strategy != StrategyKind.RandomSusceptibleBaseline)
        {
            throw UpstreamErrors.InvalidResponse();
        }

        return RunResponseChecks.Answers(request, ppo.InitialProfile, ppo.EnvironmentSeed)
            && RunResponseChecks.Answers(request, baseline.InitialProfile, baseline.EnvironmentSeed)
            ? comparison
            : throw ComparisonErrors.ContractViolation();
    }

    /// <summary>Needs stored runs. Not implemented until persistence exists.</summary>
    public Task<ComparisonDto?> GetAsync(Guid id, CancellationToken cancellationToken) =>
        Task.FromException<ComparisonDto?>(PersistenceNotAvailable.Error());
}
