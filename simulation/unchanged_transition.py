from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState


class UnchangedStateTransition:
    def apply(
        self,
        state: ResistanceState,
        candidate: CandidateTransition,
    ) -> ResistanceState:
        if candidate.outcome != "neutral":
            raise ValueError(
                "Candidate must represent an unchanged-state transition."
            )

        return state