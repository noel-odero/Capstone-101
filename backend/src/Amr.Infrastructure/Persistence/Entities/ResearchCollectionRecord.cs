namespace Amr.Infrastructure.Persistence.Entities;

public sealed class ResearchCollectionRecord
{
    public Guid Id { get; set; }
    public required string OwnerId { get; set; }
    public required string Name { get; set; }
    public string? Question { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
    public required Guid[] AnalysisIds { get; set; }
}
