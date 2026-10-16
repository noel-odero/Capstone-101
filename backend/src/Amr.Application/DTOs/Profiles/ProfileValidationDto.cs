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
    int Horizon);
