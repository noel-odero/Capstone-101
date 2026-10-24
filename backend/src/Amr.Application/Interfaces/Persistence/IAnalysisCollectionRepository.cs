using Amr.Application.DTOs.Analyses;

namespace Amr.Application.Interfaces.Persistence;

public interface IAnalysisCollectionRepository
{
    Task<IReadOnlyList<AnalysisCollectionDto>> ListAsync(CancellationToken cancellationToken);
    Task<AnalysisCollectionDto> CreateAsync(CreateAnalysisCollectionRequest request, CancellationToken cancellationToken);
}
