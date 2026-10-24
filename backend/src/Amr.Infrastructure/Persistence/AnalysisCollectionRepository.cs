using Amr.Application.DTOs.Analyses;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Amr.Application.Interfaces.Persistence;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;

namespace Amr.Infrastructure.Persistence;

public sealed class AnalysisCollectionRepository(AmrDbContext db, ICurrentUser currentUser, TimeProvider clock) : IAnalysisCollectionRepository
{
    private string Owner => currentUser.UserId is { Length: > 0 } id ? id : throw new InvalidOperationException("Collections require an authenticated user.");

    public async Task<IReadOnlyList<AnalysisCollectionDto>> ListAsync(CancellationToken cancellationToken)
    {
        var owner = Owner;
        return await db.AnalysisCollections.Where(collection => collection.OwnerId == owner)
            .OrderByDescending(collection => collection.CreatedAtUtc).ThenByDescending(collection => collection.Id)
            .Select(collection => new AnalysisCollectionDto(collection.Id, collection.Name, collection.Question, collection.CreatedAtUtc, collection.AnalysisIds))
            .ToListAsync(cancellationToken);
    }

    public async Task<AnalysisCollectionDto> CreateAsync(CreateAnalysisCollectionRequest request, CancellationToken cancellationToken)
    {
        var owner = Owner;
        var count = await db.ExperimentRuns.CountAsync(run => run.OwnerId == owner && request.AnalysisIds.Contains(run.Id), cancellationToken);
        if (count != request.AnalysisIds.Length)
            throw new AmrException(ErrorCategory.NotFound, "analysis_not_found", "One or more selected analyses are unavailable.");
        var collection = new ResearchCollectionRecord {
            Id = Guid.NewGuid(), OwnerId = owner, Name = request.Name.Trim(), Question = string.IsNullOrWhiteSpace(request.Question) ? null : request.Question.Trim(),
            CreatedAtUtc = clock.GetUtcNow(), AnalysisIds = [.. request.AnalysisIds],
        };
        db.AnalysisCollections.Add(collection);
        await db.SaveChangesAsync(cancellationToken);
        return new(collection.Id, collection.Name, collection.Question, collection.CreatedAtUtc, collection.AnalysisIds);
    }
}
