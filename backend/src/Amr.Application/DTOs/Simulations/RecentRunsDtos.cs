using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Simulations;

/// <summary>Query for GET /simulations/recent. Ordering is fixed: newest first, ties broken by id descending.</summary>
public sealed record RecentRunsQuery
{
    [Range(1, int.MaxValue)]
    public int Page { get; init; } = 1;

    [Range(1, PaginationLimits.MaxPageSize)]
    public int PageSize { get; init; } = PaginationLimits.DefaultPageSize;
}

public sealed record StrategySummaryDto(
    StrategyKind Strategy,
    string DisplayLabel,
    double CumulativeResistanceBurden,
    int FinalResistantCount,
    string TerminationReason);

/// <summary>One row of run history. Kind distinguishes a single-strategy simulation (one strategy) from a comparison (two).</summary>
public sealed record RunSummaryDto(
    Guid Id,
    ExperimentKind Kind,
    RunStatus Status,
    DateTimeOffset CreatedAtUtc,
    IReadOnlyList<int> InitialProfile,
    string ModelId,
    IReadOnlyList<StrategySummaryDto> Strategies);
