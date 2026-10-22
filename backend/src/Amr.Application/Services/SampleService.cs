using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

public sealed class SampleService(ISampleRepository samples) : ISampleService
{
    public Task<SampleDto> CreateAsync(CreateSampleRequest request, CancellationToken cancellationToken) =>
        samples.CreateAsync(request, cancellationToken);

    public Task<SampleDto?> FindAsync(Guid id, CancellationToken cancellationToken) =>
        samples.FindAsync(id, cancellationToken);

    public Task<IReadOnlyList<SampleDto>> ListAsync(CancellationToken cancellationToken) =>
        samples.ListAsync(cancellationToken);

    public async Task ValidateRunAsync(Guid? sampleId, IReadOnlyList<int> profile, CancellationToken cancellationToken)
    {
        if (sampleId is not { } id) return;

        var sample = await samples.FindAsync(id, cancellationToken)
            ?? throw new AmrException(ErrorCategory.NotFound, "sample_not_found", "No sample has this id.");
        if (!sample.ResistanceProfile.SequenceEqual(profile))
        {
            throw new AmrException(ErrorCategory.InvalidRequest, "sample_profile_mismatch", "Use the saved sample's initial resistance profile.");
        }
    }
}
