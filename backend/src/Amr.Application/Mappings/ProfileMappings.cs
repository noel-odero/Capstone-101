using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Profiles;
using Amr.Application.Errors;
using Amr.Application.PythonContracts;

namespace Amr.Application.Mappings;

public static class ProfileMappings
{
    /// <summary>Python only answers a valid profile with a 200; anything else in this body means the contract changed.</summary>
    public static ProfileValidationDto ToDto(this PythonProfileValidation validation) =>
        validation.Valid
            ? new ProfileValidationDto(
                validation.ResistanceProfile,
                validation.ResistantAntibiotics,
                validation.SusceptibleAntibiotics,
                validation.ResistantCount,
                validation.SusceptibleOptionCount,
                validation.FeasibleActions.Select(action => action.ToDto()).ToList(),
                validation.IsTerminal,
                validation.TerminalReason,
                validation.Horizon)
            {
                TransitionEvidence = validation.TransitionEvidence.Select(action => new ActionTransitionEvidenceDto(
                    action.ActionId, action.Antibiotic, action.Eligible,
                    action.Candidates.Select(candidate => new TransitionEvidenceCandidateDto(
                        candidate.TargetDrug, candidate.Outcome, candidate.SourceIds)).ToList())).ToList(),
                InteractionDataSha256 = validation.InteractionDataSha256,
                ScenarioId = validation.ScenarioId,
            }
            : throw UpstreamErrors.InvalidResponse();

    public static FeasibleActionDto ToDto(this PythonFeasibleAction action) =>
        new(action.ActionId, action.Antibiotic, action.HasCandidateTransition);
}
