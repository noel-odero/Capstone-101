using Amr.Application.DTOs.Comparisons;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;
using Amr.Application.PythonContracts;
using Amr.Domain.Enums;

namespace Amr.Application.Services;

public sealed class ComparisonService(IPythonServiceClient python, IRunRepository runs) : IComparisonService
{
    /// <summary>A comparison is stored only after the contract and the request match were verified, so an unverified pair is never persisted.</summary>
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

        var comparison = run.ToComparisonDto() with { SampleId = request.SampleId };
        var (ppo, baseline) = (comparison.Ppo!, comparison.Baseline!);
        if (ppo.Strategy != StrategyKind.Ppo || baseline.Strategy != StrategyKind.RandomSusceptibleBaseline
            || comparison.Dqn is not { Strategy: StrategyKind.Dqn, Model: not null })
        {
            throw UpstreamErrors.InvalidResponse();
        }

        if (!RunResponseChecks.Answers(request, ppo.InitialProfile, ppo.EnvironmentSeed)
            || !RunResponseChecks.Answers(request, baseline.InitialProfile, baseline.EnvironmentSeed)
            || comparison.Dqn is { } dqn && !RunResponseChecks.Answers(request, dqn.InitialProfile, dqn.EnvironmentSeed))
        {
            throw ComparisonErrors.ContractViolation();
        }

        await runs.SaveComparisonAsync(comparison, cancellationToken);
        return comparison with { IsPersisted = true };
    }

    public Task<ComparisonDto?> GetAsync(Guid id, CancellationToken cancellationToken) =>
        runs.FindComparisonAsync(id, cancellationToken);
}
