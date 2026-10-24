using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

/// <summary>Saved history queries. Default ordering is newest first, with a stable id tie-break.</summary>
public sealed record RecentRunsQuery : IValidatableObject
{
    [Range(1, int.MaxValue)]
    public int Page { get; init; } = 1;

    [Range(1, PaginationLimits.MaxPageSize)]
    public int PageSize { get; init; } = PaginationLimits.DefaultPageSize;

    [RegularExpression("^[01]{7}$")]
    public string? Profile { get; init; }

    [Range(0, 7)]
    public int? InitialResistantCount { get; init; }

    [RegularExpression("^(ppo|dqn|baseline|missing_dqn)$")]
    public string? Strategy { get; init; }

    public DateTimeOffset? From { get; init; }
    public DateTimeOffset? To { get; init; }

    [RegularExpression("^(newest|oldest|ppo|dqn|baseline|disagreement)$")]
    public string Sort { get; init; } = "newest";

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (From > To)
            yield return new ValidationResult("The start date must precede the end date.", [nameof(From), nameof(To)]);
    }
}

public sealed record StrategySummaryDto(
    StrategyKind Strategy,
    string DisplayLabel,
    double CumulativeResistanceBurden,
    int FinalResistantCount,
    string TerminationReason);

/// <summary>One row of run history, retaining the strategies actually recorded.</summary>
public sealed record RunSummaryDto(
    Guid Id,
    ExperimentKind Kind,
    RunStatus Status,
    DateTimeOffset CreatedAtUtc,
    IReadOnlyList<int> InitialProfile,
    string ModelId,
    IReadOnlyList<StrategySummaryDto> Strategies)
{
    public IReadOnlyList<string>? AntibioticOrder { get; init; }
}
