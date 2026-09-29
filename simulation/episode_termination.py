from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.resistance_state import ANTIBIOTICS


class EpisodeTermination:
    def __init__(
        self,
        action_space: ActionSpace | None = None,
        max_steps: int = 8,
    ):
        self.action_space = action_space or ActionSpace()

        if max_steps <= 0:
            raise ValueError("Maximum steps must be greater than zero.")

        self.max_steps = max_steps

    def is_terminated(self, episode: EpisodeState) -> bool:
        if episode.treatment_step >= self.max_steps:
            return True

        all_resistant = all(
            episode.resistance_state.is_resistant(antibiotic)
            for antibiotic in ANTIBIOTICS
        )

        if all_resistant:
            return True

        return False