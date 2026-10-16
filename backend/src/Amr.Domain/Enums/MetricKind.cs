namespace Amr.Domain.Enums;

/// <summary>How a metric is accumulated. No exposed metric is an average or a percentage; rates are proportions in [0, 1].</summary>
public enum MetricKind
{
    /// <summary>A running total of per-step quantities over the episode.</summary>
    Cumulative,

    /// <summary>A tally of discrete items or steps, or the count in a single state.</summary>
    Count,

    /// <summary>A signed difference between two counts.</summary>
    Difference,

    /// <summary>A ratio of two counts within one episode, in [0, 1]; null when its denominator is zero.</summary>
    Rate,
}
