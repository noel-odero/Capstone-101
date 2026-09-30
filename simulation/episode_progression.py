import random

from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.episode_step import EpisodeStep


class EpisodeProgression:
    def __init__(
        self,
        action_space: ActionSpace | None = None,
        episode_step: EpisodeStep | None = None,
    ):
        self.action_space = action_space or ActionSpace()
        self.episode_step = episode_step or EpisodeStep(
            action_space=self.action_space,
        )

    def step(
        self,
        episode: EpisodeState,
        action: int,
        seed: int | None = None,
        rng: random.Random | None = None,
    ) -> EpisodeState:
        result = self.episode_step.execute(
            state=episode.resistance_state,
            action=action,
            treatment_step=episode.treatment_step,
            seed=seed,
            rng=rng,
        )

        return episode.advance(result.next_state)