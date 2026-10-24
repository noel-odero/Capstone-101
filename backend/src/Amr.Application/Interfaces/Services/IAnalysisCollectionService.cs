using Amr.Application.DTOs.Analyses;

namespace Amr.Application.Interfaces.Services;

public interface IAnalysisCollectionService
{
    Task<IReadOnlyList<AnalysisCollectionDto>> ListAsync(CancellationToken cancellationToken);
    Task<AnalysisCollectionDto> CreateAsync(CreateAnalysisCollectionRequest request, CancellationToken cancellationToken);
}
