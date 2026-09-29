import gymnasium as gym
import numpy as np
from gymnasium import spaces

from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_termination import EpisodeTermination
from simulation.encoder import encode_observation
from simulation.observation import Observation
from simulation.resistance_state import ResistanceState
from simulation.reward import RewardFunction


class AntibioticEnvironment(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        action_space_config: ActionSpace | None = None,
        episode_progression: EpisodeProgression | None = None,
        episode_termination: EpisodeTermination | None = None,
        reward_function: RewardFunction | None = None,
        max_steps: int = 8,
    ):
        super().__init__()

        self.action_space_config = (
            action_space_config or ActionSpace()
        )

        self.episode_progression = (
            episode_progression
            or EpisodeProgression(self.action_space_config)
        )

        self.episode_termination = (
            episode_termination
            or EpisodeTermination(
                action_space=self.action_space_config,
                max_steps=max_steps,
            )
        )

        self.reward_function = (
            reward_function
            or RewardFunction(
                action_space=self.action_space_config
            )
        )

        self.action_space = spaces.Discrete(
            self.action_space_config.size
        )

        self.observation_space = spaces.Box(
            low=np.array(
                [-1] * self.action_space_config.size
                + [0] * self.action_space_config.size
                + [0],
                dtype=np.float32,
            ),
            high=np.array(
                [1] * self.action_space_config.size
                + [1] * self.action_space_config.size
                + [max_steps],
                dtype=np.float32,
            ),
            dtype=np.float32,
        )

        self.episode: EpisodeState | None = None

        self.last_action = tuple(
            0 for _ in range(self.action_space_config.size)
        )

    def _observation(self) -> np.ndarray:
        if self.episode is None:
            raise RuntimeError(
                "Environment must be reset before creating an observation."
            )

        observation = Observation(
            susceptibility=tuple(
                1
                if self.episode.resistance_state.is_resistant(
                    antibiotic
                )
                else 0
                for antibiotic in self.action_space_config.actions
            ),
            last_action=self.last_action,
            treatment_step=self.episode.treatment_step,
        )

        return np.array(
            encode_observation(observation),
            dtype=np.float32,
        )

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)

        self.episode = EpisodeState(
            resistance_state=ResistanceState(
                (0, 0, 0, 0, 0, 0, 0)
            )
        )

        self.last_action = tuple(
            0 for _ in range(self.action_space_config.size)
        )

        return self._observation(), {}

    def step(self, action):
        if self.episode is None:
            raise RuntimeError(
                "Environment must be reset before calling step()."
            )

        action = int(action)

        previous_state = self.episode.resistance_state

        next_episode = self.episode_progression.step(
            self.episode,
            action,
            seed=self.np_random.integers(0, 2**32 - 1),
        )

        reward = self.reward_function.calculate(
            previous_state,
            next_episode.resistance_state,
            action,
        )

        self.episode = next_episode

        self.last_action = tuple(
            1 if index == action else 0
            for index in range(self.action_space_config.size)
        )

        terminated = self.episode_termination.is_terminated(
            self.episode
        )

        truncated = False

        antibiotic = self.action_space_config.antibiotic_for(
            action
        )

        info = {
            "antibiotic": antibiotic,
            "effective": previous_state.is_susceptible(
                antibiotic
            ),
        }

        return (
            self._observation(),
            float(reward),
            terminated,
            truncated,
            info,
        )