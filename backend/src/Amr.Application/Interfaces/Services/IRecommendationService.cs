using Amr.Application.DTOs.Recommendations;

namespace Amr.Application.Interfaces.Services;

public interface IRecommendationService
{
    /// <summary>
    /// Recommendations describe a frozen learned policy. Returns null, which the API reports as 404
    /// recommendation_not_found, when the id is unknown or the run has no learned-policy steps (a baseline simulation, a
    /// comparison, or a failed run). The two cases are deliberately indistinguishable.
    /// </summary>
    Task<RecommendationDto?> GetBySimulationAsync(Guid simulationId, CancellationToken cancellationToken);
}
