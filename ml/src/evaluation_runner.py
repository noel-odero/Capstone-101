from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ResistanceState


class ObservationPolicy(Protocol):
    def select_action(self, observation: np.ndarray) -> int:
        ...


@dataclass(frozen=True)
class StepResult:
    observation: tuple[float, ...]
    action: int
    next_observation: tuple[float, ...]
    reward: float
    terminated: bool
    truncated: bool
    info: dict


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: int
    environment_seed: int
    policy_seed: int
    policy_name: str
    initial_resistance_profile: tuple[int, ...]
    final_resistance_profile: tuple[int, ...]
    initial_observation: tuple[float, ...]
    reset_info: dict
    steps: tuple[StepResult, ...]
    terminated: bool
    truncated: bool
    termination_reason: str

    @property
    def observations(self) -> tuple[tuple[float, ...], ...]:
        return (self.initial_observation,) + tuple(step.next_observation for step in self.steps)

    @property
    def actions(self) -> tuple[int, ...]:
        return tuple(step.action for step in self.steps)

    @property
    def antibiotics(self) -> tuple[str, ...]:
        return tuple(step.info["antibiotic"] for step in self.steps)

    @property
    def rewards(self) -> tuple[float, ...]:
        return tuple(step.reward for step in self.steps)

    @property
    def effectiveness(self) -> tuple[bool, ...]:
        return tuple(step.info["effective"] for step in self.steps)

    @property
    def cumulative_reward(self) -> float:
        return sum(self.rewards, start=0.0)

    @property
    def treatment_step_count(self) -> int:
        return len(self.steps)


@dataclass(frozen=True)
class EvaluationResult:
    scenario_id: str
    horizon: int
    reward_weights: dict[str, float]
    episodes: tuple[EpisodeResult, ...]


def _nonnegative_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative.")


def run_evaluation(
    environment: AntibioticEnvironment,
    policy_factory: Callable[..., ObservationPolicy],
    episode_count: int,
    *,
    environment_seed: int = 0,
    policy_seed: int = 0,
    initial_states: Sequence[ResistanceState | Sequence[int]] | None = None,
) -> EvaluationResult:
    """Collect stochastic episodes without computing comparative metrics.

    The factory is called as factory(environment.action_space, seed=episode_seed).
    Episode i uses environment_seed+i and policy_seed+i. Each episode creates a
    fresh policy and resets the supplied environment. Its configuration is not
    changed and it is not closed. Errors propagate; no fallback action is used.
    initial_states, if supplied, must contain one binary profile per episode.
    """
    if not isinstance(environment, AntibioticEnvironment):
        raise TypeError("Evaluation requires the stochastic AntibioticEnvironment.")
    if not callable(policy_factory):
        raise TypeError("policy_factory must construct a seeded observation policy.")
    _nonnegative_integer(episode_count, "episode_count")
    if episode_count == 0:
        raise ValueError("episode_count must be positive.")
    _nonnegative_integer(environment_seed, "environment_seed")
    _nonnegative_integer(policy_seed, "policy_seed")

    if initial_states is None:
        profiles = tuple(ResistanceState((0,) * 7) for _ in range(episode_count))
    else:
        if isinstance(initial_states, (str, bytes)) or not isinstance(initial_states, Sequence):
            raise TypeError("initial_states must be a sequence of resistance profiles.")
        if len(initial_states) != episode_count:
            raise ValueError("Supply exactly one initial state per episode.")
        profiles = tuple(
            state if isinstance(state, ResistanceState) else ResistanceState(tuple(state))
            for state in initial_states
        )

    horizon = environment.episode_termination.max_steps
    scenario_id = environment.episode_progression.episode_step.transition_model.sampler.scenario_id
    weights = environment.episode_progression.episode_step.reward_function.weights
    episodes = []

    for episode_id, initial_state in enumerate(profiles):
        episode_environment_seed = environment_seed + episode_id
        episode_policy_seed = policy_seed + episode_id
        observation, reset_info = environment.reset(
            seed=episode_environment_seed,
            options={"initial_resistance_state": initial_state},
        )
        initial_observation = tuple(float(value) for value in observation)
        reset_info = deepcopy(reset_info)
        episode = environment.episode
        if episode is None:
            raise RuntimeError("Environment reset did not initialize an episode.")
        terminated = environment.episode_termination.is_terminated(episode)
        truncated = False
        steps = []
        policy = policy_factory(environment.action_space, seed=episode_policy_seed)
        if not callable(getattr(policy, "select_action", None)):
            raise TypeError("Policy must provide select_action(observation).")

        while not (terminated or truncated):
            if len(steps) >= horizon:
                raise RuntimeError("Environment exceeded its configured horizon without ending.")
            before = tuple(float(value) for value in observation)
            action = policy.select_action(observation.copy())
            next_observation, reward, terminated, truncated, info = environment.step(action)
            steps.append(StepResult(
                observation=before,
                action=int(action),
                next_observation=tuple(float(value) for value in next_observation),
                reward=float(reward),
                terminated=bool(terminated),
                truncated=bool(truncated),
                info=deepcopy(info),
            ))
            observation = next_observation

        episode = environment.episode
        if episode is None:
            raise RuntimeError("Environment lost its episode state.")
        if terminated:
            if all(value == 1 for value in episode.resistance_state.resistance):
                reason = "no_effective_antibiotic"
            elif episode.treatment_step >= horizon:
                reason = "maximum_horizon"
            else:
                reason = "terminated"
        else:
            reason = "truncated"
        episodes.append(EpisodeResult(
            episode_id=episode_id,
            environment_seed=episode_environment_seed,
            policy_seed=episode_policy_seed,
            policy_name=f"{type(policy).__module__}.{type(policy).__qualname__}",
            initial_resistance_profile=initial_state.resistance,
            final_resistance_profile=episode.resistance_state.resistance,
            initial_observation=initial_observation,
            reset_info=reset_info,
            steps=tuple(steps),
            terminated=bool(terminated),
            truncated=bool(truncated),
            termination_reason=reason,
        ))

    return EvaluationResult(
        scenario_id=scenario_id,
        horizon=horizon,
        reward_weights={
            "effectiveness": weights.effectiveness,
            "resistance": weights.resistance,
            "exposure": weights.exposure,
        },
        episodes=tuple(episodes),
    )