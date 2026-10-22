using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Amr.Application.Interfaces.Persistence;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;

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
        await db.SaveChangesAsync(cancellationToken);
        return new SampleDto(sample.Id, sample.Label, sample.AddedAtUtc, sample.InitialProfile, []);
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
