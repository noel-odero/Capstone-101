using Amr.Application.DTOs.Recommendations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;

namespace Amr.Application.Services;

/// <summary>Reads PPO steps of stored simulations, so it cannot work until persistence exists. Stage D replaces this class.</summary>
public sealed class RecommendationService : IRecommendationService
{
    public Task<RecommendationDto?> GetBySimulationAsync(Guid simulationId, CancellationToken cancellationToken) =>
        Task.FromException<RecommendationDto?>(PersistenceNotAvailable.Error());
}
