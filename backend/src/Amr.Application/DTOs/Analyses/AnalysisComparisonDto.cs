using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Analyses;

public sealed record CompareAnalysesRequest : IValidatableObject
{
    [Required, MinLength(2), MaxLength(50)]
    public Guid[] AnalysisIds { get; init; } = [];

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (AnalysisIds is null) yield break;
        if (AnalysisIds.Contains(Guid.Empty) || AnalysisIds.Distinct().Count() != AnalysisIds.Length)
            yield return new ValidationResult("Select distinct, non-empty analysis IDs.", [nameof(AnalysisIds)]);
    }
}

public sealed record SavedAnalysisDto(
    Guid Id,
    ExperimentKind Kind,
    DateTimeOffset CreatedAtUtc,
    IReadOnlyList<int> InitialProfile,
    ModelProvenanceDto Provenance,
    SeedConfigurationDto SeedConfiguration,
    IReadOnlyList<StrategyResultDto> Strategies,
    IReadOnlyDictionary<string, MetricDefinitionDto> MetricDefinitions,
    bool? ComparisonVerified,
    Guid? SampleId);

public sealed record CompatibilityIssueDto(string Code, string Severity, string Message, IReadOnlyList<Guid> AnalysisIds);
public sealed record AnalysisCompatibilityDto(string Status, IReadOnlyList<CompatibilityIssueDto> Issues);
public sealed record PolicyBurdenDifferencesDto(Guid AnalysisId, double? PpoMinusDqn, double? PpoMinusBaseline, double? DqnMinusBaseline);
public sealed record AnalysisComparisonDto(
    IReadOnlyList<SavedAnalysisDto> Analyses,
    AnalysisCompatibilityDto Compatibility,
    IReadOnlyList<PolicyBurdenDifferencesDto> BurdenDifferences,
    string Interpretation);
