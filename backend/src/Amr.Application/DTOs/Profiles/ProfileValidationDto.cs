using Amr.Application.DTOs.Common;

namespace Amr.Application.DTOs.Profiles;

/// <summary>A valid all-resistant profile is reported with IsTerminal true and no feasible actions; it is not an error.</summary>
public sealed record ProfileValidationDto(
    IReadOnlyList<int> ResistanceProfile,
    IReadOnlyList<string> ResistantAntibiotics,
    IReadOnlyList<string> SusceptibleAntibiotics,
    int ResistantCount,
    int SusceptibleOptionCount,
    IReadOnlyList<FeasibleActionDto> FeasibleActions,
    bool IsTerminal,
    string? TerminalReason,
    int Horizon)
{
    public IReadOnlyList<ActionTransitionEvidenceDto> TransitionEvidence { get; init; } = [];
    public string? InteractionDataSha256 { get; init; }
    public string? ScenarioId { get; init; }
}

public sealed record TransitionEvidenceCandidateDto(string TargetDrug, string Outcome, IReadOnlyList<string> SourceIds);

public sealed record ActionTransitionEvidenceDto(
    int ActionId, string Antibiotic, bool Eligible, IReadOnlyList<TransitionEvidenceCandidateDto> Candidates);
