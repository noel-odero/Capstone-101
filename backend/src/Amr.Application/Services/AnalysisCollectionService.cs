using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Analyses;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

public sealed class AnalysisCollectionService(IAnalysisCollectionRepository collections) : IAnalysisCollectionService
{
    public Task<IReadOnlyList<AnalysisCollectionDto>> ListAsync(CancellationToken cancellationToken) => collections.ListAsync(cancellationToken);

    public Task<AnalysisCollectionDto> CreateAsync(CreateAnalysisCollectionRequest request, CancellationToken cancellationToken)
    {
        Validator.ValidateObject(request, new ValidationContext(request), validateAllProperties: true);
        return collections.CreateAsync(request, cancellationToken);
    }
}
