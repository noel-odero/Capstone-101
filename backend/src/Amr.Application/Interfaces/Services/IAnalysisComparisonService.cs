using Amr.Application.DTOs.Analyses;

namespace Amr.Application.Interfaces.Services;

public interface IAnalysisComparisonService
{
    Task<AnalysisComparisonDto> CompareAsync(CompareAnalysesRequest request, CancellationToken cancellationToken);
}
