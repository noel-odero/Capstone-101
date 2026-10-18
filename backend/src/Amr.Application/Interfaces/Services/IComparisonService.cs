using Amr.Application.DTOs.Comparisons;

namespace Amr.Application.Interfaces.Services;

public interface IComparisonService
{
    Task<ComparisonDto> RunAsync(CreateComparisonRequest request, CancellationToken cancellationToken);

    /// <returns>Null when no comparison has the id.</returns>
    Task<ComparisonDto?> GetAsync(Guid id, CancellationToken cancellationToken);
}
