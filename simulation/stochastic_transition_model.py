from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.transition_sampler import SampledTransition, TransitionSampler


REFERENCE_SCENARIO_ID = "REF_UNIFORM_SUPPORTED"


class StochasticTransitionModel:
    def __init__(
        self,
        candidate_generator: CandidateTransitionGenerator | None = None,
        sampler: TransitionSampler | None = None,
        transition_function: ResistanceTransitionFunction | None = None,
    ):
        self.candidate_generator = (
            candidate_generator or CandidateTransitionGenerator()
        )
        self.sampler = sampler or TransitionSampler()
        self.transition_function = (
            transition_function or ResistanceTransitionFunction()
        )

    def step(
        self,
        state: ResistanceState,
        action: int,
        seed: int | None = None,
    ) -> tuple[ResistanceState, SampledTransition]:
        candidates = self.candidate_generator.generate(
            state,
            action,
        )

        if not candidates:
            return state, SampledTransition(
                candidate=CandidateTransition(
                    target_drug="",
                    outcome="no_change",
                    source_ids=(),
                ),
                probability=1.0,
                scenario_id=REFERENCE_SCENARIO_ID,
                candidates=(),
            )

        sampled = self.sampler.sample(
            candidates,
            seed=seed,
        )

        next_state = self.transition_function.apply(
            state,
            sampled.candidate,
        )

        return next_state, sampled