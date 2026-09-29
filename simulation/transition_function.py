from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState


class ResistanceTransitionFunction:
    def apply(
        self,
        state: ResistanceState,
        candidate: CandidateTransition,
    ) -> ResistanceState:
        if candidate.outcome == "cross_resistance":
            return state.with_resistance(
                candidate.target_drug,
                True,
            )

        if candidate.outcome == "collateral_sensitivity":
            return state.with_resistance(
                candidate.target_drug,
                False,
            )

        if candidate.outcome == "neutral":
            return state

        raise ValueError(
            f"Unknown transition outcome: {candidate.outcome}"
        )