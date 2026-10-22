using Amr.Application.DTOs.Samples;

namespace Amr.Application.Interfaces.Services;

public interface ISampleService
{
    Task<SampleDto> CreateAsync(CreateSampleRequest request, CancellationToken cancellationToken);
    Task<SampleDto?> FindAsync(Guid id, CancellationToken cancellationToken);
    Task<IReadOnlyList<SampleDto>> ListAsync(CancellationToken cancellationToken);
    Task ValidateRunAsync(Guid? sampleId, IReadOnlyList<int> profile, CancellationToken cancellationToken);
}
