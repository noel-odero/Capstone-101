using Amr.Application.DTOs.Analyses;
using Amr.Application.Interfaces.Persistence;
using Amr.Domain.Enums;
using Microsoft.EntityFrameworkCore;

namespace Amr.Infrastructure.Persistence;

public sealed partial class RunRepository : IAnalysisRepository
{
    public async Task<IReadOnlyList<SavedAnalysisDto>> FindManyAsync(IReadOnlyCollection<Guid> ids, CancellationToken cancellationToken)
    {
        var owner = RequireOwner();
        try
        {
            var rows = await db.ExperimentRuns
                .AsNoTracking()
                .Where(run => run.OwnerId == owner && ids.Contains(run.Id))
                .Include(run => run.ModelVersion)
                .Include(run => run.StrategyRuns).ThenInclude(strategy => strategy.StepTraces)
                .AsSplitQuery()
                .ToListAsync(cancellationToken);
            return rows.Select(run =>
            {
                if (run.Kind == ExperimentKind.Comparison)
                {
                    var dto = RunEntityMapper.ToComparisonDto(run);
                    var strategies = new[] { dto.Ppo, dto.Dqn, dto.Baseline }.OfType<Amr.Application.DTOs.Common.StrategyResultDto>().ToArray();
                    return new SavedAnalysisDto(dto.Id, run.Kind, dto.CreatedAtUtc, run.InitialProfile, dto.Provenance,
                        dto.SeedConfiguration, strategies, dto.MetricDefinitions, dto.Contract?.Verified, dto.SampleId);
                }
                var single = RunEntityMapper.ToSimulationDto(run);
                return new SavedAnalysisDto(single.Id, run.Kind, single.CreatedAtUtc, run.InitialProfile, single.Provenance,
                    single.SeedConfiguration, single.Result is null ? [] : [single.Result], single.MetricDefinitions, null, run.SampleId);
            }).ToArray();
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            LogReadFailed(logger, exception);
            throw PersistenceFailureClassifier.ForRead(exception);
        }
    }
}
