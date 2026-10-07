import gymnasium as gym
import numpy as np
from gymnasium import spaces

from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
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

        self.episode_termination = (
            episode_termination
            or EpisodeTermination(
                action_space=self.action_space_config,
                max_steps=max_steps,
            )
        )

        self.reward_function = (
            reward_function
            or RewardFunction()
        )

        self.episode_progression = episode_progression or EpisodeProgression(
            action_space=self.action_space_config,
            episode_step=EpisodeStep(
                reward_function=self.reward_function,
                action_space=self.action_space_config,
            ),
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
                + [self.episode_termination.max_steps],
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

    def action_masks(self) -> np.ndarray:
        """Return the valid-action mask expected by mask-aware policies."""
        if self.episode is None:
            return np.ones(self.action_space_config.size, dtype=bool)
        return np.asarray(
            [
                self.episode.resistance_state.is_susceptible(antibiotic)
                for antibiotic in self.action_space_config.actions
            ],
            dtype=bool,
        )

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)

        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise TypeError("Reset options must be a dictionary.")

        unknown_options = set(options) - {"initial_resistance_state"}
        if unknown_options:
            raise ValueError(
                f"Unsupported reset options: {sorted(unknown_options)}"
            )

        initial_state = options.get(
            "initial_resistance_state",
            (0, 0, 0, 0, 0, 0, 0),
        )
        if not isinstance(initial_state, ResistanceState):
            if not isinstance(initial_state, (tuple, list)):
                raise TypeError(
                    "initial_resistance_state must be a ResistanceState, "
                    "tuple, or list."
                )
            initial_state = ResistanceState(tuple(initial_state))

        self.episode = EpisodeState(
            resistance_state=initial_state
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

        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action,
            (int, np.integer),
        ):
            raise TypeError("Action must be an integer.")

        action = int(action)
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        step_seed = int(
            self.np_random.integers(
                0,
                2**32 - 1,
            )
        )

        step_result = self.episode_progression.step(
            self.episode,
            action,
            horizon=self.episode_termination.max_steps,
            seed=step_seed,
        )

        self.episode = self.episode.advance(step_result.next_state)

        self.last_action = tuple(
            1 if index == action else 0
            for index in range(self.action_space_config.size)
        )

        terminated = self.episode_termination.is_terminated(
            self.episode
        )

        truncated = False

        sampled = step_result.sampled_transition
        selected_candidate = sampled.candidate
        candidate_details = [
            {
                "target_drug": candidate.target_drug,
                "outcome": candidate.outcome,
                "source_ids": list(candidate.source_ids),
                "scenario_probability": probability,
            }
            for candidate, probability in zip(
                sampled.candidates,
                sampled.candidate_probabilities,
            )
        ]

        info = {
            "antibiotic": step_result.treatment.antibiotic,
            "effective": step_result.treatment.effective,
            "scenario_id": sampled.scenario_id,
            "transition_status": sampled.status,
            "selected_outcome": (
                selected_candidate.outcome
                if selected_candidate is not None
                else None
            ),
            "selected_target_drug": (
                selected_candidate.target_drug
                if selected_candidate is not None
                else None
            ),
            "source_ids": (
                list(selected_candidate.source_ids)
                if selected_candidate is not None
                else []
            ),
            "selected_candidate_probability": sampled.probability,
            "candidate_scenario_probabilities": candidate_details,
            "no_transition_probability": sampled.no_transition_probability,
            "occurrence_probability_assumption": sampled.occurrence_probability,
            "transition_seed": sampled.seed,
        }

        observation = np.array(
            encode_observation(step_result.observation),
            dtype=np.float32,
        )

        return (
            observation,
            float(step_result.reward),
            terminated,
            truncated,
            info,
        )