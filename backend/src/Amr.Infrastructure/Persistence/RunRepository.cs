using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Amr.Application.Interfaces.Persistence;
using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// PostgreSQL storage of completed runs. A save is one transaction: the model version upsert, the run, its strategy runs
/// and every step trace commit together or roll back together. There are no retries and no partial rows.
/// Every operation is scoped to the authenticated user: another user's run is indistinguishable from a missing one.
/// </summary>
public sealed partial class RunRepository(AmrDbContext db, TimeProvider clock, ICurrentUser currentUser, ILogger<RunRepository> logger) : IRunRepository
{
    private string RequireOwner() =>
        currentUser.UserId is { Length: > 0 } id
            ? id
            : throw new InvalidOperationException("Runs are stored per user, but the request has no authenticated user.");

    public Task SaveSimulationAsync(SimulationDto simulation, CancellationToken cancellationToken) =>
        SaveAsync(simulation.Id, ExperimentKind.Simulation, simulation.Provenance, (modelId, now, owner) => RunEntityMapper.ToEntity(simulation, modelId, now, owner), cancellationToken);

    public Task SaveComparisonAsync(ComparisonDto comparison, CancellationToken cancellationToken) =>
        SaveAsync(comparison.Id, ExperimentKind.Comparison, comparison.Provenance, (modelId, now, owner) => RunEntityMapper.ToEntity(comparison, modelId, now, owner), cancellationToken);

    public async Task<SimulationDto?> FindSimulationAsync(Guid id, CancellationToken cancellationToken)
    {
        var run = await FindAsync(id, ExperimentKind.Simulation, cancellationToken);
        return run is null ? null : RunEntityMapper.ToSimulationDto(run);
    }

    public async Task<ComparisonDto?> FindComparisonAsync(Guid id, CancellationToken cancellationToken)
    {
        var run = await FindAsync(id, ExperimentKind.Comparison, cancellationToken);
        return run is null ? null : RunEntityMapper.ToComparisonDto(run);
    }

    public async Task<PagedResultDto<RunSummaryDto>> ListRecentAsync(RecentRunsQuery query, CancellationToken cancellationToken)
    {
        var owner = RequireOwner();
        try
        {
            var mine = db.ExperimentRuns.Where(run => run.OwnerId == owner);
            var total = await mine.CountAsync(cancellationToken);
            var skip = (long)(query.Page - 1) * query.PageSize;
            if (skip >= total)
            {
                return new PagedResultDto<RunSummaryDto>([], query.Page, query.PageSize, total);
            }

            var rows = await mine
                .OrderByDescending(run => run.CreatedAtUtc)
                .ThenByDescending(run => run.Id)
                .Skip((int)skip)
                .Take(query.PageSize)
                .Select(run => new
                {
                    run.Id,
                    run.Kind,
                    run.Status,
                    run.CreatedAtUtc,
                    run.InitialProfile,
                    run.ModelVersion.ModelId,
                    Strategies = run.StrategyRuns.Select(strategy => new
                    {
                        strategy.Strategy,
                        strategy.DisplayLabel,
                        strategy.CumulativeResistanceBurden,
                        strategy.FinalResistantCount,
                        strategy.TerminationReason,
                    }).ToList(),
                })
                .ToListAsync(cancellationToken);

            var items = rows.Select(row => new RunSummaryDto(
                row.Id,
                row.Kind,
                row.Status,
                row.CreatedAtUtc,
                row.InitialProfile,
                row.ModelId,
                row.Strategies
                    .OrderBy(strategy => strategy.Strategy)
                    .Select(strategy => new StrategySummaryDto(strategy.Strategy, strategy.DisplayLabel, strategy.CumulativeResistanceBurden, strategy.FinalResistantCount, strategy.TerminationReason))
                    .ToList())).ToList();
            return new PagedResultDto<RunSummaryDto>(items, query.Page, query.PageSize, total);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            LogReadFailed(logger, exception);
            throw PersistenceFailureClassifier.ForRead(exception);
        }
    }

    private async Task<ExperimentRun?> FindAsync(Guid id, ExperimentKind kind, CancellationToken cancellationToken)
    {
        var owner = RequireOwner();
        try
        {
            return await db.ExperimentRuns
                .Include(run => run.ModelVersion)
                .Include(run => run.StrategyRuns)
                .ThenInclude(strategy => strategy.StepTraces)
                .AsSplitQuery()
                .SingleOrDefaultAsync(run => run.Id == id && run.Kind == kind && run.OwnerId == owner, cancellationToken);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            LogReadFailed(logger, exception);
            throw PersistenceFailureClassifier.ForRead(exception);
        }
    }

    private async Task SaveAsync(
        Guid runId,
        ExperimentKind kind,
        ModelProvenanceDto provenance,
        Func<Guid, DateTimeOffset, string, ExperimentRun> build,
        CancellationToken cancellationToken)
    {
        var owner = RequireOwner();
        try
        {
            var now = clock.GetUtcNow();
            await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
            var modelVersionId = await EnsureModelVersionAsync(provenance, now, cancellationToken);
            db.ExperimentRuns.Add(build(modelVersionId, now, owner));
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            var error = PersistenceFailureClassifier.ForWrite(exception);
            LogSaveFailed(logger, exception, runId, kind, error.Code);
            throw error;
        }
    }

    /// <summary>Inserts the model version if absent, race-free: concurrent saves of the same configuration end with one row.</summary>
    private async Task<Guid> EnsureModelVersionAsync(ModelProvenanceDto provenance, DateTimeOffset now, CancellationToken cancellationToken)
    {
        var model = RunEntityMapper.ToEntity(provenance, now);
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"""
            INSERT INTO model_versions
                (id, fingerprint, model_id, algorithm, checkpoint_sha256, interaction_data_sha256, scenario_id, horizon,
                 action_mask_rule, reward_specification, antibiotic_order, first_recorded_at_utc)
            VALUES
                ({model.Id}, {model.Fingerprint}, {model.ModelId}, {model.Algorithm}, {model.CheckpointSha256}, {model.InteractionDataSha256},
                 {model.ScenarioId}, {model.Horizon}, {model.ActionMaskRule}, {model.RewardSpecificationJson}::jsonb, {model.AntibioticOrder}, {model.FirstRecordedAtUtc})
            ON CONFLICT (fingerprint) DO NOTHING
            """,
            cancellationToken);

        return await db.ModelVersions
            .Where(existing => existing.Fingerprint == model.Fingerprint)
            .Select(existing => existing.Id)
            .SingleAsync(cancellationToken);
    }

    /// <summary>Everything the database or the connection can throw, but not a caller cancellation and not an already-safe error.</summary>
    private static bool IsDatabaseFailure(Exception exception, CancellationToken cancellationToken) =>
        exception is not AmrException && !(exception is OperationCanceledException && cancellationToken.IsCancellationRequested);

    [LoggerMessage(Level = LogLevel.Error, Message = "Run {RunId} ({Kind}) completed in the scientific service but was not saved ({ErrorCode}). It has no public record and no result was returned to the client.")]
    private static partial void LogSaveFailed(ILogger logger, Exception exception, Guid runId, ExperimentKind kind, string errorCode);

    [LoggerMessage(Level = LogLevel.Error, Message = "Stored runs could not be read.")]
    private static partial void LogReadFailed(ILogger logger, Exception exception);
}
