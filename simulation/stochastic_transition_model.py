import random

from simulation.resistance_state import ResistanceState
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.transition_sampler import SampledTransition, TransitionSampler


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
        rng: random.Random | None = None,
    ) -> tuple[ResistanceState, SampledTransition]:
        candidates = self.candidate_generator.generate(
            state,
            action,
        )

        sampled = self.sampler.sample(
            candidates,
            seed=seed,
            rng=rng,
        )

        if sampled.candidate is None:
            return state, sampled

        next_state = self.transition_function.apply(
            state,
            sampled.candidate,
        )

        return next_state, sampled