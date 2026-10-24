using System.ComponentModel.DataAnnotations;

namespace Amr.Application.DTOs.Analyses;

public sealed record CreateAnalysisCollectionRequest : IValidatableObject
{
    [Required, MaxLength(80)]
    public string Name { get; init; } = string.Empty;
    [MaxLength(500)]
    public string? Question { get; init; }
    [Required, MinLength(2), MaxLength(50)]
    public Guid[] AnalysisIds { get; init; } = [];

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (string.IsNullOrWhiteSpace(Name))
            yield return new ValidationResult("Enter a collection name.", [nameof(Name)]);
        if (AnalysisIds is not null && (AnalysisIds.Contains(Guid.Empty) || AnalysisIds.Distinct().Count() != AnalysisIds.Length))
            yield return new ValidationResult("Select distinct, non-empty analysis IDs.", [nameof(AnalysisIds)]);
    }
}

public sealed record AnalysisCollectionDto(Guid Id, string Name, string? Question, DateTimeOffset CreatedAtUtc, IReadOnlyList<Guid> AnalysisIds);
