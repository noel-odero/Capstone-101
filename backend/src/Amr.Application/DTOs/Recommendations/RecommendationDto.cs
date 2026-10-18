using Amr.Application.DTOs.Common;
using Amr.Domain.Enums;

namespace Amr.Application.DTOs.Recommendations;

/// <summary>The PPO-selected actions of a stored simulation. Each action is a policy choice among simulator-feasible drugs; it is not clinical advice.</summary>
public sealed record RecommendationDto(
    Guid SimulationId,
    StrategyKind Strategy,
    string DisplayLabel,
    ModelProvenanceDto Provenance,
    IReadOnlyList<int> InitialProfile,
    bool IsTerminalAtStart,
    string TerminationReason,
    IReadOnlyList<StepTraceDto> Steps,
    string Interpretation);
