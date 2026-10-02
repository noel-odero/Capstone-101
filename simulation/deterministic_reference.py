from itertools import product

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from simulation.action_space import ActionSpace
from simulation.candidate_transition import CandidateTransition
from simulation.episode import EpisodeState
from simulation.episode_termination import EpisodeTermination
from simulation.observation import Observation
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.reward import RewardFunction
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.transition_model import TransitionResult


REFERENCE_SCENARIO_ID = "REF_DETERMINISTIC_FIRST_SUPPORTED"


class DeterministicTransitionModel:
    """Computational fixture: select the lexicographically first supported outcome."""

    def __init__(self):
        self._generator = CandidateTransitionGenerator()
        self._transition_function = ResistanceTransitionFunction()

    def step(
        self,
        state: ResistanceState,
        action: int,
        seed: int | None = None,
    ) -> TransitionResult:
        candidates = self._generator.generate(state, action)
        if not candidates:
            return TransitionResult(state, "unsupported_no_candidate", ())

        target_drug, outcome = min(
            (candidate.target_drug, candidate.outcome)
            for candidate in candidates
        )
        source_ids = tuple(sorted({
            source_id
            for candidate in candidates
            if (candidate.target_drug, candidate.outcome) == (target_drug, outcome)
            for source_id in candidate.source_ids
        }))
        candidate = CandidateTransition(target_drug, outcome, source_ids)
        return TransitionResult(
            self._transition_function.apply(state, candidate),
            outcome,
            source_ids,
        )


class DeterministicReferenceEnvironment(gym.Env):
    """Finite computational reference, not deterministic bacterial evolution.

    Planning state is EpisodeState: resistance profile plus elapsed steps.
    Last action is observed but does not affect transitions, reward, or termination.
    """

    metadata = {"render_modes": []}

    def __init__(self, max_steps: int = 8):
        super().__init__()
        if isinstance(max_steps, bool) or not isinstance(max_steps, int):
            raise TypeError("Maximum steps must be an integer.")
        self._termination = EpisodeTermination(max_steps=max_steps)
        self._model = DeterministicTransitionModel()
        self._action_config = ActionSpace()
        self._reward = RewardFunction(action_space=self._action_config)
        self.max_steps = max_steps
        self.action_space = spaces.Discrete(len(ANTIBIOTICS))
        self.observation_space = spaces.Box(
            low=np.zeros(15, dtype=np.float32),
            high=np.asarray([1] * 14 + [max_steps], dtype=np.float32),
            dtype=np.float32,
        )
        self.episode: EpisodeState | None = None

    def states(self) -> tuple[EpisodeState, ...]:
        """Enumerate every planning state, including terminal states."""
        return tuple(
            EpisodeState(ResistanceState(resistance), treatment_step)
            for resistance in product((0, 1), repeat=len(ANTIBIOTICS))
            for treatment_step in range(self.max_steps + 1)
        )

    def is_terminal(self, state: EpisodeState) -> bool:
        return self._termination.is_terminated(state)

    def _validate_state(self, state: EpisodeState) -> None:
        if not isinstance(state, EpisodeState):
            raise TypeError("Planning state must be an EpisodeState.")
        if not isinstance(state.resistance_state, ResistanceState):
            raise TypeError("Planning state must contain a ResistanceState.")
        if (
            isinstance(state.treatment_step, bool)
            or not isinstance(state.treatment_step, int)
            or not 0 <= state.treatment_step <= self.max_steps
        ):
            raise ValueError("Treatment step must be an integer within the horizon.")

    def _validate_action(self, action: int) -> int:
        if isinstance(action, (bool, np.bool_)) or not isinstance(action, (int, np.integer)):
            raise TypeError("Action must be an integer.")
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")
        return int(action)

    def transition(
        self, state: EpisodeState, action: int
    ) -> tuple[EpisodeState, float, bool, dict]:
        """Return the sole next state (probability 1) without mutating the environment.

        Terminal planning states are absorbing and return zero additional reward.
        """
        self._validate_state(state)
        action = self._validate_action(action)
        if self.is_terminal(state):
            return state, 0.0, True, {
                "scenario_id": REFERENCE_SCENARIO_ID,
                "transition_probability": 1.0,
                "probability_source": "reference_scenario",
                "transition_status": "terminal",
            }

        result = self._model.step(state.resistance_state, action)
        next_state = state.advance(result.next_state)
        antibiotic = self._action_config.antibiotic_for(action)
        return (
            next_state,
            self._reward.calculate(state.resistance_state, result.next_state, action),
            self.is_terminal(next_state),
            {
                "scenario_id": REFERENCE_SCENARIO_ID,
                "transition_probability": 1.0,
                "probability_source": "reference_scenario",
                "transition_status": result.outcome,
                "source_ids": list(result.source_ids),
                "antibiotic": antibiotic,
                "effective": state.resistance_state.is_susceptible(antibiotic),
            },
        )

    @staticmethod
    def _observation(state: EpisodeState, action: int | None = None) -> np.ndarray:
        observation = Observation(
            susceptibility=state.resistance_state.resistance,
            last_action=tuple(int(index == action) for index in range(len(ANTIBIOTICS))),
            treatment_step=state.treatment_step,
        )
        return np.asarray(observation.to_vector(), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise TypeError("Reset options must be a dictionary.")
        if set(options) - {"initial_resistance_state"}:
            raise ValueError("Unsupported reset options.")
        resistance = options.get("initial_resistance_state", (0,) * len(ANTIBIOTICS))
        if not isinstance(resistance, ResistanceState):
            if not isinstance(resistance, (tuple, list)):
                raise TypeError("Initial state must be a ResistanceState, tuple, or list.")
            resistance = ResistanceState(tuple(resistance))
        self.episode = EpisodeState(resistance)
        return self._observation(self.episode), {}

    def step(self, action):
        if self.episode is None:
            raise RuntimeError("Environment must be reset before calling step().")
        if self.is_terminal(self.episode):
            raise RuntimeError("Episode is terminal; reset before calling step().")
        next_state, reward, terminated, info = self.transition(self.episode, action)
        self.episode = next_state
        return self._observation(next_state, int(action)), float(reward), terminated, False, info