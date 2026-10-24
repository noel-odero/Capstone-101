using Amr.Application.DTOs.Analyses;

namespace Amr.Application.Interfaces.Persistence;

public interface IAnalysisRepository
{
    /// <summary>Returns only persisted analyses owned by the current user; unknown and foreign IDs are omitted alike.</summary>
    Task<IReadOnlyList<SavedAnalysisDto>> FindManyAsync(IReadOnlyCollection<Guid> ids, CancellationToken cancellationToken);
}
