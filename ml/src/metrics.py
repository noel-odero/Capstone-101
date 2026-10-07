from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import math

from ml.src.evaluation_runner import EpisodeResult, EvaluationResult
from simulation.resistance_state import ResistanceState


@dataclass(frozen=True)
class EpisodeMetrics:
    episode_id: int
    environment_seed: int
    policy_seed: int
    policy_name: str
    scenario_id: str
    treatment_steps: int
    transitions: int
    effective_steps: int
    resistance_emergence_events: int
    treatment_effectiveness_rate: float | None
    resistance_emergence_rate: float | None
    future_effective_antibiotics: int
    change_in_future_effective_antibiotics: int
    cumulative_antibiotic_exposure: int
    cumulative_reward: float
    terminated: bool
    truncated: bool
    termination_reason: str

    def to_dict(self) -> dict:
        """Return a detached JSON-compatible record; undefined rates export as null."""
        return asdict(self)


@dataclass(frozen=True)
class MetricsSummary:
    episode_count: int
    zero_step_episode_count: int
    total_treatment_steps: int
    total_transitions: int
    total_effective_steps: int
    total_resistance_emergence_events: int
    pooled_treatment_effectiveness_rate: float | None
    pooled_resistance_emergence_rate: float | None
    mean_episode_treatment_effectiveness_rate: float | None
    mean_episode_resistance_emergence_rate: float | None
    treatment_rate_episode_count: int
    emergence_rate_episode_count: int
    mean_future_effective_antibiotics: float | None
    mean_change_in_future_effective_antibiotics: float | None
    total_cumulative_antibiotic_exposure: int
    mean_cumulative_antibiotic_exposure: float | None
    total_cumulative_reward: float
    mean_cumulative_reward: float | None
    terminated_episode_count: int
    truncated_episode_count: int
    termination_reason_counts: dict[str, int]


@dataclass(frozen=True)
class EvaluationMetrics:
    scenario_id: str
    policy_name: str | None
    horizon: int
    reward_specification: dict[str, str | int]
    episodes: tuple[EpisodeMetrics, ...]
    summary: MetricsSummary

    def to_dict(self) -> dict:
        """Export nested records with JSON arrays and no input-object references."""
        result = asdict(self)
        result["episodes"] = [episode.to_dict() for episode in self.episodes]
        return result


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: list[float | int]) -> float | None:
    return sum(values) / len(values) if values else None


def _observation_profile(observation: tuple[float, ...]) -> tuple[int, ...]:
    if len(observation) != 15:
        raise ValueError("Metrics require a 15-value observation.")
    return ResistanceState(tuple(observation[:7])).resistance


def calculate_episode_metrics(
    episode: EpisodeResult, *, scenario_id: str
) -> EpisodeMetrics:
    """Calculate metrics from one fully observed binary episode, without mutation.

    scenario_id is explicit because zero-step episodes have no transition info.
    Missing effectiveness, unknown profiles, inconsistent trajectories, and
    nonfinite rewards raise errors rather than silently producing measurements.
    """
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("A nonempty scenario_id is required.")
    initial = ResistanceState(episode.initial_resistance_profile).resistance
    final = ResistanceState(episode.final_resistance_profile).resistance
    if _observation_profile(episode.initial_observation) != initial:
        raise ValueError("Initial observation does not match the initial resistance profile.")

    previous = initial
    effective_steps = 0
    emergence_events = 0
    if not math.isfinite(episode.terminal_reward_adjustment):
        raise ValueError("Terminal reward adjustment must be finite.")
    cumulative_reward = episode.terminal_reward_adjustment
    for step in episode.steps:
        before = _observation_profile(step.observation)
        after = _observation_profile(step.next_observation)
        if before != previous:
            raise ValueError("Resistance profiles are discontinuous between steps.")
        if "scenario_id" in step.info and step.info["scenario_id"] != scenario_id:
            raise ValueError("Transition scenario does not match the evaluation scenario.")
        if "effective" not in step.info:
            raise ValueError("Treatment effectiveness metadata is missing.")
        if not isinstance(step.info["effective"], bool):
            raise ValueError("Treatment effectiveness must be a boolean.")
        if not math.isfinite(step.reward):
            raise ValueError("Recorded rewards must be finite.")
        effective_steps += int(step.info["effective"])
        emergence_events += int(sum(after) > sum(before))
        cumulative_reward += step.reward
        previous = after

    if previous != final:
        raise ValueError("Final resistance profile does not match the trajectory.")
    count = len(episode.steps)
    future_effective = final.count(0)
    return EpisodeMetrics(
        episode_id=episode.episode_id,
        environment_seed=episode.environment_seed,
        policy_seed=episode.policy_seed,
        policy_name=episode.policy_name,
        scenario_id=scenario_id,
        treatment_steps=count,
        transitions=count,
        effective_steps=effective_steps,
        resistance_emergence_events=emergence_events,
        treatment_effectiveness_rate=_ratio(effective_steps, count),
        resistance_emergence_rate=_ratio(emergence_events, count),
        future_effective_antibiotics=future_effective,
        change_in_future_effective_antibiotics=future_effective - initial.count(0),
        cumulative_antibiotic_exposure=count,
        cumulative_reward=cumulative_reward,
        terminated=episode.terminated,
        truncated=episode.truncated,
        termination_reason=episode.termination_reason,
    )


def calculate_metrics(evaluation: EvaluationResult) -> EvaluationMetrics:
    """Summarize one policy/scenario evaluation; no comparisons or uncertainty estimates.

    Pooled rates weight steps; mean episode rates weight defined episodes equally.
    Zero-step episodes contribute to counts and endpoint/reward/exposure means,
    but not to rate denominators or mean-rate contributor counts.
    """
    if not isinstance(evaluation.scenario_id, str) or not evaluation.scenario_id.strip():
        raise ValueError("A nonempty scenario_id is required.")
    names = {episode.policy_name for episode in evaluation.episodes}
    if len(names) > 1:
        raise ValueError("Aggregate one policy at a time; mixed policy identities are unsupported.")
    episodes = tuple(
        calculate_episode_metrics(episode, scenario_id=evaluation.scenario_id)
        for episode in evaluation.episodes
    )
    total_steps = sum(episode.treatment_steps for episode in episodes)
    total_transitions = sum(episode.transitions for episode in episodes)
    effective_steps = sum(episode.effective_steps for episode in episodes)
    emergence_events = sum(episode.resistance_emergence_events for episode in episodes)
    treatment_rates = [
        episode.treatment_effectiveness_rate for episode in episodes
        if episode.treatment_effectiveness_rate is not None
    ]
    emergence_rates = [
        episode.resistance_emergence_rate for episode in episodes
        if episode.resistance_emergence_rate is not None
    ]
    summary = MetricsSummary(
        episode_count=len(episodes),
        zero_step_episode_count=sum(episode.treatment_steps == 0 for episode in episodes),
        total_treatment_steps=total_steps,
        total_transitions=total_transitions,
        total_effective_steps=effective_steps,
        total_resistance_emergence_events=emergence_events,
        pooled_treatment_effectiveness_rate=_ratio(effective_steps, total_steps),
        pooled_resistance_emergence_rate=_ratio(emergence_events, total_transitions),
        mean_episode_treatment_effectiveness_rate=_mean(treatment_rates),
        mean_episode_resistance_emergence_rate=_mean(emergence_rates),
        treatment_rate_episode_count=len(treatment_rates),
        emergence_rate_episode_count=len(emergence_rates),
        mean_future_effective_antibiotics=_mean([
            episode.future_effective_antibiotics for episode in episodes
        ]),
        mean_change_in_future_effective_antibiotics=_mean([
            episode.change_in_future_effective_antibiotics for episode in episodes
        ]),
        total_cumulative_antibiotic_exposure=sum(
            episode.cumulative_antibiotic_exposure for episode in episodes
        ),
        mean_cumulative_antibiotic_exposure=_mean([
            episode.cumulative_antibiotic_exposure for episode in episodes
        ]),
        total_cumulative_reward=sum((episode.cumulative_reward for episode in episodes), start=0.0),
        mean_cumulative_reward=_mean([episode.cumulative_reward for episode in episodes]),
        terminated_episode_count=sum(episode.terminated for episode in episodes),
        truncated_episode_count=sum(episode.truncated for episode in episodes),
        termination_reason_counts=dict(Counter(episode.termination_reason for episode in episodes)),
    )
    return EvaluationMetrics(
        scenario_id=evaluation.scenario_id,
        policy_name=next(iter(names)) if names else None,
        horizon=evaluation.horizon,
        reward_specification=deepcopy(evaluation.reward_specification),
        episodes=episodes,
        summary=summary,
    )