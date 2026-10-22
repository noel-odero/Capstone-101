using Amr.Application.DTOs.Samples;

namespace Amr.Application.Interfaces.Persistence;

public interface ISampleRepository
{
    Task<SampleDto> CreateAsync(CreateSampleRequest request, CancellationToken cancellationToken);
    Task<SampleDto?> FindAsync(Guid id, CancellationToken cancellationToken);
    Task<IReadOnlyList<SampleDto>> ListAsync(CancellationToken cancellationToken);
}
