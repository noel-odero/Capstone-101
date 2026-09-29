from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.treatment_action_executor import TreatmentActionExecutor
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.transition_sampler import TransitionSampler


class EpisodeProgression:
    def __init__(
        self,
        action_space: ActionSpace | None = None,
        treatment_executor: TreatmentActionExecutor | None = None,
        transition_generator: CandidateTransitionGenerator | None = None,
        transition_sampler: TransitionSampler | None = None,
        transition_function: ResistanceTransitionFunction | None = None,
    ):
        self.action_space = action_space or ActionSpace()

        self.treatment_executor = (
            treatment_executor
            or TreatmentActionExecutor(self.action_space)
        )

        self.transition_generator = (
            transition_generator
            or CandidateTransitionGenerator(self.action_space)
        )

        self.transition_sampler = (
            transition_sampler
            or TransitionSampler()
        )

        self.transition_function = (
            transition_function
            or ResistanceTransitionFunction()
        )

    def step(
        self,
        episode: EpisodeState,
        action: int,
        seed: int | None = None,
    ) -> EpisodeState:
        self.treatment_executor.execute(
            episode.resistance_state,
            action,
        )

        candidates = self.transition_generator.generate(
            episode.resistance_state,
            action,
        )

        sampled = self.transition_sampler.sample(
            candidates,
            seed=seed,
        )

        next_state = self.transition_function.apply(
            episode.resistance_state,
            sampled.candidate,
        )

        return episode.advance(next_state)