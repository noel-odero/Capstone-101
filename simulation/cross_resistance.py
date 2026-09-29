from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.transition_function import ResistanceTransitionFunction


class CrossResistanceTransition:
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
        if candidate.outcome != "cross_resistance":
            raise ValueError(
                "Candidate must represent a cross-resistance transition."
            )

        if state.is_resistant(candidate.target_drug):
            raise ValueError(
                "Cross-resistance requires the target antibiotic "
                "to be susceptible in the current state."
            )

        return self.transition_function.apply(
            state,
            candidate,
        )