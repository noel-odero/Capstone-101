from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import hashlib
import json

from ml.src.evaluation_runner import EvaluationResult, ObservationPolicy, run_evaluation
from ml.src.metrics import EvaluationMetrics, calculate_metrics
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ResistanceState


@dataclass(frozen=True)
class SeedRunResult:
    run_id: int
    environment_base_seed: int
    policy_base_seed: int
    evaluation: EvaluationResult
    metrics: EvaluationMetrics

    @property
    def episode_identities(self) -> tuple[tuple[int, int], ...]:
        return tuple((self.run_id, episode.episode_id) for episode in self.evaluation.episodes)


@dataclass(frozen=True)
class MultiSeedResult:
    seed_pairs: tuple[tuple[int, int], ...]
    initial_resistance_profiles: tuple[tuple[int, ...], ...]
    environment_configuration: dict
    runs: tuple[SeedRunResult, ...]

    def to_dict(self) -> dict:
        """Return detached JSON-compatible records, without cross-run summaries."""
        result = asdict(self)
        for run, exported in zip(self.runs, result["runs"]):
            exported["episode_identities"] = run.episode_identities
        return result


def _seed_plan(
    seed_pairs: Sequence[tuple[int, int]], episode_count: int
) -> tuple[tuple[int, int], ...]:
    if isinstance(seed_pairs, (str, bytes)) or not isinstance(seed_pairs, Sequence):
        raise TypeError("seed_pairs must be an ordered sequence.")
    if not seed_pairs:
        raise ValueError("Supply at least one seed pair.")
    environment_seeds: set[int] = set()
    policy_seeds: set[int] = set()
    pairs = []
    for pair in seed_pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Each seed pair must contain exactly two integers.")
        for seed in pair:
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise TypeError("Seeds must be integers.")
            if seed < 0:
                raise ValueError("Seeds must be nonnegative.")
        for base, seen, stream in (
            (pair[0], environment_seeds, "environment"),
            (pair[1], policy_seeds, "policy"),
        ):
            expanded = set(range(base, base + episode_count))
            if seen & expanded:
                raise ValueError(f"Overlapping expanded {stream} seed schedules.")
            seen.update(expanded)
        pairs.append((pair[0], pair[1]))
    return tuple(pairs)


def _class_name(value: object) -> str:
    return f"{type(value).__module__}.{type(value).__qualname__}"


def _configuration(environment: AntibioticEnvironment) -> dict:
    """Snapshot exposed configuration of the current stochastic simulation stack."""
    progression = environment.episode_progression
    episode_step = progression.episode_step
    model = episode_step.transition_model
    generator = model.candidate_generator
    executor = episode_step.treatment_executor
    interaction_bytes = json.dumps(
        generator.interactions, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    components = {
        "environment": environment,
        "progression": progression,
        "episode_step": episode_step,
        "termination": environment.episode_termination,
        "model": model,
        "generator": generator,
        "sampler": model.sampler,
        "transition_function": model.transition_function,
        "reward_function": episode_step.reward_function,
        "executor": executor,
        "effectiveness": executor.treatment_effectiveness,
    }
    return {
        "component_types": {name: _class_name(value) for name, value in components.items()},
        "action_mappings": {
            "environment": environment.action_space_config.actions,
            "progression": progression.action_space.actions,
            "episode_step": episode_step.action_space.actions,
            "generator": generator.action_space.actions,
            "executor": executor.action_space.actions,
            "effectiveness": executor.treatment_effectiveness.action_space.actions,
            "reward": episode_step.reward_function.action_space.actions,
            "termination": environment.episode_termination.action_space.actions,
        },
        "action_start": int(environment.action_space.start),
        "action_count": int(environment.action_space.n),
        "scenario_id": model.sampler.scenario_id,
        "occurrence_probability_assumption": model.sampler.occurrence_probability,
        "horizon": environment.episode_termination.max_steps,
        "reward_weights": asdict(episode_step.reward_function.weights),
        "observation_low": environment.observation_space.low.tolist(),
        "observation_high": environment.observation_space.high.tolist(),
        "observation_dtype": str(environment.observation_space.dtype),
        "interaction_data_sha256": hashlib.sha256(interaction_bytes).hexdigest(),
    }


def run_multi_seed_evaluation(
    environment_factory: Callable[[], AntibioticEnvironment],
    policy_factory: Callable[..., ObservationPolicy],
    seed_pairs: Sequence[tuple[int, int]],
    *,
    initial_states: Sequence[ResistanceState | Sequence[int]],
) -> MultiSeedResult:
    """Run one policy under matched conditions across disjoint seed schedules.

    A fresh environment is owned and closed per run; the existing runner creates
    a fresh seeded policy per episode. IDs are (run_id, episode_id). Each run's
    trajectories and metrics remain separate. No comparisons or statistics.
    """
    if not callable(environment_factory) or not callable(policy_factory):
        raise TypeError("Environment and policy factories must be callable.")
    if isinstance(initial_states, (str, bytes)) or not isinstance(initial_states, Sequence):
        raise TypeError("initial_states must be an ordered sequence of profiles.")
    if not initial_states:
        raise ValueError("Supply at least one initial state.")
    profiles = tuple(
        state if isinstance(state, ResistanceState) else ResistanceState(tuple(state))
        for state in initial_states
    )
    plan = _seed_plan(seed_pairs, len(profiles))
    environments = []
    policies = []
    runs = []
    expected_configuration = None
    expected_policy_name = None

    def fresh_policy(action_space, seed):
        policy = policy_factory(action_space, seed=seed)
        if any(policy is previous for previous in policies):
            raise ValueError("Policy factory reused a policy instance.")
        policies.append(policy)
        return policy

    for run_id, (environment_seed, policy_seed) in enumerate(plan):
        environment = environment_factory()
        if not isinstance(environment, AntibioticEnvironment):
            raise TypeError("Environment factory must return a stochastic AntibioticEnvironment.")
        if any(environment is previous for previous in environments):
            raise ValueError("Environment factory reused an environment instance.")
        environments.append(environment)
        try:
            configuration = _configuration(environment)
            if expected_configuration is not None and configuration != expected_configuration:
                raise ValueError("Environment configuration or transition data differs across runs.")
            if expected_configuration is None:
                expected_configuration = configuration
            evaluation = run_evaluation(
                environment, fresh_policy, len(profiles),
                environment_seed=environment_seed,
                policy_seed=policy_seed,
                initial_states=profiles,
            )
            if _configuration(environment) != configuration:
                raise ValueError("Environment configuration or transition data changed during a run.")
            metrics = calculate_metrics(evaluation)
            if expected_policy_name is not None and metrics.policy_name != expected_policy_name:
                raise ValueError("Policy identity differs across seed runs.")
            expected_policy_name = metrics.policy_name
            runs.append(SeedRunResult(run_id, environment_seed, policy_seed, evaluation, metrics))
        finally:
            environment.close()

    return MultiSeedResult(
        seed_pairs=plan,
        initial_resistance_profiles=tuple(state.resistance for state in profiles),
        environment_configuration=expected_configuration,
        runs=tuple(runs),
    )