using Amr.Application.DTOs.Recommendations;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;

namespace Amr.Application.Services;

public sealed class RecommendationService(IRunRepository runs) : IRecommendationService
{
    public async Task<RecommendationDto?> GetBySimulationAsync(Guid simulationId, CancellationToken cancellationToken)
    {
        var simulation = await runs.FindSimulationAsync(simulationId, cancellationToken);
        return simulation?.ToRecommendationDto();
    }
}
