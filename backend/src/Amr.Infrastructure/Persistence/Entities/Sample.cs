namespace Amr.Infrastructure.Persistence.Entities;

public sealed class Sample
{
    public Guid Id { get; set; }
    public required string OwnerId { get; set; }
    public required string Label { get; set; }
    public DateTimeOffset AddedAtUtc { get; set; }
    public required int[] InitialProfile { get; set; }
}
