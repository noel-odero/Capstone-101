using Amr.Application.DTOs.Common;

namespace Amr.Application.Services;

/// <summary>Cheap integrity checks that a Python run answers the request that was sent. They compare values; they compute nothing scientific.</summary>
internal static class RunResponseChecks
{
    public static bool ConsistentOutcome(StrategyResultDto result, ModelProvenanceDto provenance) =>
        (result.Metrics.CumulativeResistanceBurden is null) == (result.TerminationReason == "evidence_boundary")
        && (provenance.ActionMaskRule != "susceptible_actions_with_candidate_transitions"
            || result.Steps.All(step => step.HasCandidateTransition && step.SelectedDrugSusceptible
                && step.TransitionStatus != "unsupported_no_candidate"));

    public static bool Answers(RunRequestBase request, IReadOnlyList<int> initialProfile, long environmentSeed) =>
        request.ResistanceProfile.SequenceEqual(initialProfile)
        && (request.EnvironmentSeed is null || request.EnvironmentSeed == environmentSeed);
}
