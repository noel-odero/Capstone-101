"""Matched PPO, DQN and baseline rollouts through the shared evaluation utilities."""
from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any
import uuid

from ml.src.evaluation_runner import EpisodeResult
from ml.src.greedy_policy import GreedyPolicy
from ml.src.matched_policy_evaluation import _episode_burden
from ml.src.metrics import EpisodeMetrics
from ml.src.multi_seed_evaluation import MultiSeedResult, run_multi_seed_evaluation
from ml.src.ppo_inference import NO_CANDIDATE_STATUS, ContractMismatchError, InferenceContext
from ml.src.ppo_training import make_training_environment
from ml.src.statistical_comparison import match_run_pairs
from service import __version__
from service.errors import ComparisonContractError
from service.runtime import DISCLAIMER, ModelRuntime
from simulation.resistance_state import ANTIBIOTICS

STRATEGY_LABELS = {"ppo": "PPO", "dqn": "DQN", "greedy": "Random Susceptible Baseline"}
_POLICY_IMPLEMENTATION = "service.rollout.FrozenEnginePolicy (wraps ml.src.ppo_inference.FrozenPolicyInferenceEngine)"
_UNUSED_POLICY_SEED = 0

METRIC_DEFINITIONS = {
    "cumulative_resistance_burden": (
        "Negative of the simulator's cumulative reward (ml.src.matched_policy_evaluation._episode_burden): "
        "sum over steps of resistant_count_after / 7, with an all-resistant state charged for the remaining "
        "horizon. Lower means less simulated resistance burden; it is not a clinical outcome."
    ),
    "cumulative_reward": "Sum of simulator step rewards plus any terminal adjustment (ml.src.metrics).",
    "treatment_steps": "Number of actions taken before the episode ended.",
    "initial_resistant_count": "Resistant antibiotics in the initial profile.",
    "final_resistant_count": "Resistant antibiotics in the final profile.",
    "final_susceptible_count": "Susceptible antibiotics in the final profile (ml.src.metrics future_effective_antibiotics).",
    "change_in_susceptible_count": "final_susceptible_count minus the initial susceptible count.",
    "resistance_emergence_events": "Steps after which the resistant count increased (ml.src.metrics).",
    "resistance_emergence_rate": "resistance_emergence_events / treatment_steps; null when there are no steps.",
    "susceptible_action_rate": (
        "Fraction of steps whose selected drug was susceptible in the simulator "
        "(ml.src.metrics treatment_effectiveness_rate). The susceptible-only mask makes this 1.0 for all "
        "strategies, and it is not clinical efficacy; null when there are no steps."
    ),
    "unsupported_step_count": (
        "Steps with transition_status unsupported_no_candidate: the simulator had no candidate transition "
        "and left the profile unchanged."
    ),
    "cumulative_antibiotic_exposure": "Number of antibiotic administrations (one per step).",
}
PAIRING_SEMANTICS = (
    "Matched and verified before a result is returned: initial profile, environment seed, scenario, horizon, "
    "reward configuration and transition-data hash. Because the environment seed is shared, the simulator draws "
    "the same sequence of per-step transition seeds by step index. A transition seed only seeds the random draw "
    "among the candidate transitions of the selected action in the current state. Those candidate sets depend on "
    "the action and state, so equal seeds do not guarantee identical transition outcomes, and trajectories can "
    "diverge once the strategies choose different actions. PPO and DQN are deterministic and ignore the policy seed; "
    "the baseline uses it for tie-breaking among susceptible actions."
)
SINGLE_RUN_CAVEAT = (
    "One matched comparison is a single stochastic sample. It does not establish a superior strategy, "
    "and it is not clinical evidence."
)


class FrozenEnginePolicy:
    """Rebuild the full context at each decision, then ask the verified learned policy."""

    def __init__(self, engine):
        self._engine = engine

    def select_action(self, observation) -> int:
        return self._engine.recommend(InferenceContext.from_observation(observation)).action_id


def _profile(observation: tuple[float, ...]) -> list[int]:
    return [int(value) for value in observation[: len(ANTIBIOTICS)]]


def _resistant_names(profile: list[int]) -> list[str]:
    return [name for name, value in zip(ANTIBIOTICS, profile) if value == 1]


def _snapshot(index: int, profile: list[int], last_action: int | None, is_terminal: bool) -> dict[str, Any]:
    resistant = _resistant_names(profile)
    return {
        "state_index": index,
        "treatment_step": index,
        "resistance_profile": profile,
        "resistant_antibiotics": resistant,
        "resistant_count": len(resistant),
        "susceptible_count": len(ANTIBIOTICS) - len(resistant),
        "last_action_id": last_action,
        "last_action_antibiotic": None if last_action is None else ANTIBIOTICS[last_action],
        "is_terminal": is_terminal,
    }


def _step_trace(runtime: ModelRuntime, index: int, step, episode: EpisodeResult) -> dict[str, Any]:
    before, after = _profile(step.observation), _profile(step.next_observation)
    info = step.info
    candidates = [
        {
            "target_drug": item["target_drug"],
            "outcome": item["outcome"],
            "source_ids": list(item["source_ids"]),
            "scenario_probability": item["scenario_probability"],
        }
        for item in info["candidate_scenario_probabilities"]
    ]
    return {
        "step_index": index,
        "treatment_step_before": index,
        "treatment_step_after": index + 1,
        "resistance_profile_before": before,
        "action_id": step.action,
        "antibiotic": info["antibiotic"],
        "feasible_actions": runtime.feasible_actions(InferenceContext.from_observation(step.observation)),
        "selected_drug_susceptible": info["effective"],
        "transition_status": info["transition_status"],
        "has_candidate_transition": bool(candidates),
        "candidate_transitions": candidates,
        "selected_outcome": info["selected_outcome"],
        "selected_target_drug": info["selected_target_drug"],
        "source_ids": list(info["source_ids"]),
        "selected_candidate_probability": info["selected_candidate_probability"],
        "no_transition_probability": info["no_transition_probability"],
        "transition_seed": info["transition_seed"],
        "reward": step.reward,
        "resistance_profile_after": after,
        "newly_resistant_antibiotics": [
            name for name, b, a in zip(ANTIBIOTICS, before, after) if b == 0 and a == 1
        ],
        "newly_susceptible_antibiotics": [
            name for name, b, a in zip(ANTIBIOTICS, before, after) if b == 1 and a == 0
        ],
        "resistant_count_after": sum(after),
        "susceptible_count_after": len(ANTIBIOTICS) - sum(after),
        "is_terminal_after": step.terminated,
        "termination_reason": episode.termination_reason if step.terminated else None,
    }


def _strategy_result(
    runtime: ModelRuntime,
    strategy: str,
    episode: EpisodeResult,
    metrics: EpisodeMetrics,
    environment_seed: int,
    policy_seed: int | None,
) -> dict[str, Any]:
    steps = [_step_trace(runtime, index, step, episode) for index, step in enumerate(episode.steps)]
    initial = list(episode.initial_resistance_profile)
    states = [_snapshot(0, initial, None, episode.terminated and not steps)]
    for index, trace in enumerate(steps, start=1):
        states.append(
            _snapshot(index, trace["resistance_profile_after"], trace["action_id"], trace["is_terminal_after"])
        )
    return {
        "strategy": strategy,
        "display_label": STRATEGY_LABELS[strategy],
        "implementation": _POLICY_IMPLEMENTATION if strategy != "greedy" else episode.policy_name,
        "model": runtime.policy_model(strategy),
        "initial_profile": initial,
        "final_profile": list(episode.final_resistance_profile),
        "environment_seed": environment_seed,
        "policy_seed": policy_seed,
        "termination_reason": episode.termination_reason,
        "states": states,
        "steps": steps,
        "metrics": {
            "cumulative_resistance_burden": _episode_burden(episode) + 0.0,  # avoids JSON -0.0
            "cumulative_reward": metrics.cumulative_reward,
            "treatment_steps": metrics.treatment_steps,
            "initial_resistant_count": sum(initial),
            "final_resistant_count": sum(episode.final_resistance_profile),
            "final_susceptible_count": metrics.future_effective_antibiotics,
            "change_in_susceptible_count": metrics.change_in_future_effective_antibiotics,
            "resistance_emergence_events": metrics.resistance_emergence_events,
            "resistance_emergence_rate": metrics.resistance_emergence_rate,
            "susceptible_action_rate": metrics.treatment_effectiveness_rate,
            "unsupported_step_count": sum(
                trace["transition_status"] == NO_CANDIDATE_STATUS for trace in steps
            ),
            "cumulative_antibiotic_exposure": metrics.cumulative_antibiotic_exposure,
        },
    }


def _evaluate(
    runtime: ModelRuntime, strategy: str, profile: tuple[int, ...], environment_seed: int, policy_seed: int
) -> tuple[MultiSeedResult, EpisodeResult, EpisodeMetrics]:
    """One episode through the existing runner; each call builds its own environment and policy instances."""
    engine, config = runtime.engine_for(strategy), runtime.config
    policy_factory = (
        (lambda action_space, seed: FrozenEnginePolicy(engine)) if strategy != "greedy" else GreedyPolicy
    )
    result = run_multi_seed_evaluation(
        lambda: make_training_environment(config),
        policy_factory,
        [(environment_seed, policy_seed)],
        initial_states=[profile],
    )
    live_hash = result.environment_configuration["interaction_data_sha256"]
    if live_hash != runtime.manifest.interaction_data_sha256:
        raise ContractMismatchError("Live transition data differs from the pinned manifest hash.")
    run = result.runs[0]
    return result, run.evaluation.episodes[0], run.metrics.episodes[0]


def _provenance(runtime: ModelRuntime, configuration: dict[str, Any], strategy: str = "ppo") -> dict[str, Any]:
    model = runtime.policy_model("ppo" if strategy == "greedy" else strategy)
    return {
        "service_version": __version__,
        **model,
        "interaction_data_sha256": configuration["interaction_data_sha256"],
        "scenario_id": configuration["scenario_id"],
        "horizon": configuration["horizon"],
        "reward_specification": configuration["reward_specification"],
        "action_mask_rule": configuration["action_mask_configuration"]["rule"],
        "antibiotic_order": list(ANTIBIOTICS),
        "evaluation_utility": "ml.src.multi_seed_evaluation.run_multi_seed_evaluation",
    }


def _seed(value: int | None) -> tuple[int, str]:
    return (secrets.randbelow(2**31), "service_generated") if value is None else (value, "client")


def _envelope() -> dict[str, Any]:
    return {
        "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_definitions": METRIC_DEFINITIONS,
        "disclaimer": DISCLAIMER,
    }


def simulate(
    runtime: ModelRuntime,
    *,
    strategy: str,
    resistance_profile: list[int],
    environment_seed: int | None,
    policy_seed: int | None,
) -> dict[str, Any]:
    profile = InferenceContext(tuple(resistance_profile), None, 0).resistance_profile
    env_seed, env_source = _seed(environment_seed)
    if strategy != "greedy":
        applied_policy_seed, policy_source, notes = None, "not_applicable", [
            f"{strategy.upper()} is deterministic; any supplied policy_seed is ignored."
        ]
        internal_policy_seed = _UNUSED_POLICY_SEED
    else:
        applied_policy_seed, policy_source = _seed(policy_seed)
        internal_policy_seed = applied_policy_seed
        notes = ["policy_seed drives the baseline's uniform tie-breaking among susceptible actions."]
    result, episode, metrics = _evaluate(runtime, strategy, profile, env_seed, internal_policy_seed)
    return {
        **_envelope(),
        "kind": "simulation",
        "provenance": _provenance(runtime, result.environment_configuration, strategy),
        "seed_configuration": {
            "environment_seed": env_seed,
            "environment_seed_source": env_source,
            "policy_seed": applied_policy_seed,
            "policy_seed_source": policy_source,
            "notes": notes,
        },
        "result": _strategy_result(runtime, strategy, episode, metrics, env_seed, applied_policy_seed),
    }


def _first_divergent_step(ppo: dict[str, Any], greedy: dict[str, Any]) -> int | None:
    ppo_steps, greedy_steps = ppo["steps"], greedy["steps"]
    for index, (left, right) in enumerate(zip(ppo_steps, greedy_steps)):
        if (left["action_id"], left["resistance_profile_after"]) != (right["action_id"], right["resistance_profile_after"]):
            return index
    return None if len(ppo_steps) == len(greedy_steps) else min(len(ppo_steps), len(greedy_steps))


def _comparison_contract(
    runtime: ModelRuntime,
    profile: tuple[int, ...],
    environment_seed: int,
    ppo_run: MultiSeedResult,
    greedy_run: MultiSeedResult,
    ppo: dict[str, Any],
    greedy: dict[str, Any],
    dqn_run: MultiSeedResult | None = None,
    dqn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify the matched design or raise; the result reports only what was checked or observed."""
    try:
        match_run_pairs(ppo_run, greedy_run)
        if dqn_run is not None:
            match_run_pairs(ppo_run, dqn_run)
    except ValueError as error:
        raise ComparisonContractError("existing_matched_run_validation") from error

    runs = [ppo_run, greedy_run, *([dqn_run] if dqn_run is not None else [])]
    results = [ppo, greedy, *([dqn] if dqn is not None else [])]
    ppo_config = ppo_run.environment_configuration
    configs = [run.environment_configuration for run in runs]
    episodes = [run.runs[0].evaluation.episodes[0] for run in runs]
    pinned = runtime.config
    common = min(len(result["steps"]) for result in results)
    checks = {
        "initial_profile": all(episode.initial_resistance_profile == profile for episode in episodes),
        "environment_seed": all(episode.environment_seed == environment_seed for episode in episodes),
        "scenario_id": all(config["scenario_id"] == runtime.manifest.scenario_id for config in configs),
        "horizon": all(config["horizon"] == runtime.engine.horizon for config in configs),
        "interaction_data_sha256": all(config["interaction_data_sha256"] == runtime.manifest.interaction_data_sha256 for config in configs),
        "reward_specification": all(config["reward_specification"] == pinned.reward_configuration for config in configs),
        "action_mask_configuration": all(config["action_mask_configuration"] == pinned.action_mask_configuration for config in configs),
        "transition_seed_schedule": all(
            result["steps"][index]["transition_seed"] == ppo["steps"][index]["transition_seed"]
            for result in results for index in range(common)
        ),
    }
    for check, passed in checks.items():
        if not passed:
            raise ComparisonContractError(check)

    differences = [_first_divergent_step(ppo, result) for result in results[1:]]
    first_divergence = min((step for step in differences if step is not None), default=None)
    return {
        "verified": True,
        "checks_passed": list(checks),
        "shared": {
            "initial_profile": list(profile),
            "environment_seed": environment_seed,
            "scenario_id": ppo_config["scenario_id"],
            "horizon": ppo_config["horizon"],
            "interaction_data_sha256": ppo_config["interaction_data_sha256"],
            "reward_specification": ppo_config["reward_specification"],
            "action_mask_configuration": ppo_config["action_mask_configuration"],
        },
        "transition_seed_schedule": {
            "shared_by_step_index": True,
            "steps_compared": common,
            "meaning": "Equal transition seeds only seed the random draw among the selected action's candidate "
            "transitions in the current state; they do not make the outcomes equal.",
        },
        "transition_outcomes_guaranteed_identical": False,
        "observed": {
            "steps_compared": common,
            "steps_with_same_action": sum(
                all(result["steps"][index]["action_id"] == ppo["steps"][index]["action_id"] for result in results)
                for index in range(common)
            ),
            "first_divergent_step": first_divergence,
            "trajectories_identical": first_divergence is None,
        },
    }


def compare(
    runtime: ModelRuntime,
    *,
    resistance_profile: list[int],
    environment_seed: int | None,
    policy_seed: int | None,
) -> dict[str, Any]:
    profile = InferenceContext(tuple(resistance_profile), None, 0).resistance_profile
    env_seed, env_source = _seed(environment_seed)
    baseline_seed, policy_source = _seed(policy_seed)
    ppo_run, ppo_episode, ppo_metrics = _evaluate(runtime, "ppo", profile, env_seed, baseline_seed)
    greedy_run, greedy_episode, greedy_metrics = _evaluate(runtime, "greedy", profile, env_seed, baseline_seed)
    dqn_run, dqn_episode, dqn_metrics = _evaluate(runtime, "dqn", profile, env_seed, baseline_seed)
    ppo = _strategy_result(runtime, "ppo", ppo_episode, ppo_metrics, env_seed, None)
    greedy = _strategy_result(runtime, "greedy", greedy_episode, greedy_metrics, env_seed, baseline_seed)
    dqn = _strategy_result(runtime, "dqn", dqn_episode, dqn_metrics, env_seed, None)
    contract = _comparison_contract(runtime, profile, env_seed, ppo_run, greedy_run, ppo, greedy, dqn_run, dqn)
    return {
        **_envelope(),
        "kind": "comparison",
        "provenance": _provenance(runtime, ppo_run.environment_configuration),
        "seed_configuration": {
            "environment_seed": env_seed,
            "environment_seed_source": env_source,
            "policy_seed": baseline_seed,
            "policy_seed_source": policy_source,
            "notes": ["policy_seed applies to the baseline only; PPO and DQN ignore it."],
        },
        "pairing_semantics": PAIRING_SEMANTICS,
        "comparison_contract": contract,
        "ppo": ppo,
        "dqn": dqn,
        "greedy": greedy,
        "single_run_caveat": SINGLE_RUN_CAVEAT,
    }
