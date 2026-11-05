using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Amr.Application.Interfaces.Persistence;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.Infrastructure.Persistence;

public sealed class SampleRepository(AmrDbContext db, ICurrentUser currentUser, TimeProvider clock) : ISampleRepository
{
    private string Owner => currentUser.UserId is { Length: > 0 } id ? id : throw new InvalidOperationException("Samples require an authenticated user.");

    public async Task<SampleDto> CreateAsync(CreateSampleRequest request, CancellationToken cancellationToken)
    {
        var label = request.Label.Trim();
        if (label.Length == 0)
        {
            throw new AmrException(ErrorCategory.InvalidRequest, "sample_label_required", "Enter a sample label.");
        }
        var sample = new Sample { Id = Guid.NewGuid(), OwnerId = Owner, Label = label, AddedAtUtc = clock.GetUtcNow(), InitialProfile = [.. request.ResistanceProfile] };
        db.Samples.Add(sample);
        try
        {
            await db.SaveChangesAsync(cancellationToken);
        }
        catch (DbUpdateException exception) when (exception.InnerException is PostgresException
            { SqlState: PostgresErrorCodes.UniqueViolation, ConstraintName: "ux_samples_owner_normalized_label" })
        {
            db.Entry(sample).State = EntityState.Detached;
            throw new AmrException(ErrorCategory.InvalidRequest, "sample_label_exists", "A sample with this label already exists. Choose a different label.");
        }
        return new SampleDto(sample.Id, sample.Label, sample.AddedAtUtc, sample.InitialProfile, []);
    }

    public async Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken)
    {
        var owner = Owner;
        await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
        // Lock the parent so concurrent analysis inserts finish before unlinking, or wait until deletion commits.
        var sample = await db.Samples.FromSqlInterpolated(
            $"SELECT * FROM samples WHERE id = {id} AND owner_id = {owner} FOR UPDATE")
            .AsNoTracking().SingleOrDefaultAsync(cancellationToken);
        if (sample is null) return false;

        await db.ExperimentRuns.Where(run => run.SampleId == id && run.OwnerId == owner)
            .ExecuteUpdateAsync(update => update.SetProperty(run => run.SampleId, (Guid?)null), cancellationToken);
        await Mine().Where(value => value.Id == id).ExecuteDeleteAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return true;
    }

    public async Task<SampleDto?> FindAsync(Guid id, CancellationToken cancellationToken)
    {
        var samples = await Project(Mine().Where(sample => sample.Id == id)).ToListAsync(cancellationToken);
        return samples.SingleOrDefault();
    }

    public async Task<IReadOnlyList<SampleDto>> ListAsync(CancellationToken cancellationToken) =>
        await Project(Mine().OrderByDescending(sample => sample.AddedAtUtc).ThenByDescending(sample => sample.Id)).ToListAsync(cancellationToken);

    private IQueryable<Sample> Mine()
    {
        var owner = Owner;
        return db.Samples.Where(sample => sample.OwnerId == owner);
    }

    private IQueryable<SampleDto> Project(IQueryable<Sample> samples)
    {
        var owner = Owner;
        return samples.Select(sample => new SampleDto(
            sample.Id, sample.Label, sample.AddedAtUtc, sample.InitialProfile,
            db.ExperimentRuns.Where(run => run.SampleId == sample.Id && run.OwnerId == owner)
                .OrderByDescending(run => run.CreatedAtUtc).ThenByDescending(run => run.Id)
                .Select(run => new SampleRunDto(run.Id, run.CreatedAtUtc)).ToList()));
    }
}
