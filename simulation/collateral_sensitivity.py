from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.transition_function import ResistanceTransitionFunction


class CollateralSensitivityTransition:
    def __init__(
        self,
        transition_function: ResistanceTransitionFunction | None = None,
    ):
        self.transition_function = (
            transition_function or ResistanceTransitionFunction()
        )

    def apply(
        self,
        state: ResistanceState,
        candidate: CandidateTransition,
    ) -> ResistanceState:
        if candidate.outcome != "collateral_sensitivity":
            raise ValueError(
                "Candidate must represent a collateral-sensitivity transition."
            )

        if not state.is_resistant(candidate.target_drug):
            raise ValueError(
                "Collateral sensitivity requires the target antibiotic "
                "to be resistant in the current state."
            )

        return self.transition_function.apply(
            state,
            candidate,
        )