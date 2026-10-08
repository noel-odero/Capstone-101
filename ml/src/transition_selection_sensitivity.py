from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from ml.src.evaluation_runner import EpisodeResult, EvaluationResult, StepResult
from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.metrics import calculate_episode_metrics
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, environment_manifest, load_ppo_model, make_training_environment
from ml.src.ppo_visualizations import generate_transition_sensitivity_plots
from ml.src.greedy_policy import GreedyPolicy
from simulation.deterministic_reference import (
    DeterministicReferenceEnvironment,
    REFERENCE_SCENARIO_ID as DETERMINISTIC_SCENARIO_ID,
)
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.transition_sampler import REFERENCE_SCENARIO_ID as UNIFORM_SCENARIO_ID
from simulation.transition_sampler import RESISTANCE_CHANGING_OUTCOMES


CONDITIONS = (UNIFORM_SCENARIO_ID, DETERMINISTIC_SCENARIO_ID)
POLICIES = ("ppo", "greedy")


def _label(profile) -> str:
    return "".join("R" if bit else "S" for bit in profile)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _environment_for_condition(condition: str, config: PPOConfig):
    if condition == UNIFORM_SCENARIO_ID:
        return make_training_environment(config)
    if condition == DETERMINISTIC_SCENARIO_ID:
        return DeterministicReferenceEnvironment(max_steps=config.horizon)
    raise ValueError(f"Unsupported transition-selection condition: {condition}")


def _environment_contract(environment, condition: str) -> dict[str, Any]:
    if condition == UNIFORM_SCENARIO_ID:
        return {
            "scenario_id": condition,
            "actions": tuple(environment.action_space_config.actions),
            "horizon": environment.episode_termination.max_steps,
            "reward": environment.reward_function.specification.to_dict(),
            "observation_shape": environment.observation_space.shape,
            "observation_low": environment.observation_space.low.tolist(),
            "observation_high": environment.observation_space.high.tolist(),
            "mask_rule": "susceptible_actions_only",
            "interactions": environment.episode_progression.episode_step.transition_model.candidate_generator.interactions,
            "terminal_flags": tuple(
                environment.episode_termination.is_terminated(state)
                for state in environment.episode_termination.all_states()
            ) if hasattr(environment.episode_termination, "all_states") else None,
        }
    return {
        "scenario_id": condition,
        "actions": tuple(environment._action_config.actions),
        "horizon": environment.max_steps,
        "reward": environment._reward.specification.to_dict(),
        "observation_shape": environment.observation_space.shape,
        "observation_low": environment.observation_space.low.tolist(),
        "observation_high": environment.observation_space.high.tolist(),
        "mask_rule": "susceptible_actions_only",
        "interactions": environment._model._generator.interactions,
        "terminal_flags": tuple(environment.is_terminal(state) for state in environment.states()),
    }


def inspect_transition_compatibility(config: PPOConfig) -> dict[str, Any]:
    if config.horizon != 8 or config.scenario_id != UNIFORM_SCENARIO_ID or config.gamma != 1.0:
        raise ValueError("Step 7 requires the existing REF_UNIFORM_SUPPORTED training setup, H=8, gamma=1.")
    environments = {condition: _environment_for_condition(condition, config) for condition in CONDITIONS}
    try:
        contracts = {condition: _environment_contract(environment, condition) for condition, environment in environments.items()}
        uniform, deterministic = (contracts[condition] for condition in CONDITIONS)
        comparisons = {
            "state_representation": uniform["observation_shape"] == deterministic["observation_shape"] == (15,) and all(
                _profile_observation_contract_matches(environments, profile)
                for profile in canonical_initial_profiles()
            ),
            "ordered_seven_action_ids": uniform["actions"] == deterministic["actions"] == ANTIBIOTICS,
            "action_feasibility_rule": uniform["mask_rule"] == deterministic["mask_rule"] == "susceptible_actions_only" and all(
                _profile_masks_match(environments, profile)
                for profile in canonical_initial_profiles()
            ),
            "reward_specification": uniform["reward"] == deterministic["reward"],
            "horizon": uniform["horizon"] == deterministic["horizon"] == 8,
            "terminal_handling": uniform["terminal_flags"] == deterministic["terminal_flags"]
            if uniform["terminal_flags"] is not None else all(
                environments[UNIFORM_SCENARIO_ID].episode_termination.is_terminated(state)
                == environments[DETERMINISTIC_SCENARIO_ID].is_terminal(state)
                for state in environments[DETERMINISTIC_SCENARIO_ID].states()
            ),
            "candidate_generator_data": uniform["interactions"] == deterministic["interactions"],
        }
        if not all(comparisons.values()):
            raise ValueError(f"Transition conditions have incompatible shared contracts: {comparisons}")
        return {
            "conditions": {
                UNIFORM_SCENARIO_ID: {
                    "selection": "uniform random selection over deduplicated supported candidates",
                    "transition_randomness": "yes; the per-step environment emits a transition_seed",
                },
                DETERMINISTIC_SCENARIO_ID: {
                    "selection": "lexicographically smallest (target_drug, outcome); aggregate matching source IDs",
                    "transition_randomness": "none; transition_seed is not applicable and is recorded as null",
                },
            },
            "contract_checks": comparisons,
            "contract_details": {
                condition: {
                    "action_ids": list(contract["actions"]),
                    "horizon": contract["horizon"],
                    "reward_specification": contract["reward"],
                    "observation_shape": list(contract["observation_shape"]),
                    "observation_low": contract["observation_low"],
                    "observation_high": contract["observation_high"],
                    "action_mask": contract["mask_rule"],
                } for condition, contract in contracts.items()
            },
            "paired_evaluation_contract": {
                "initial_profiles": "all 128 canonical profiles in identical order",
                "evaluation_schedule": "reuses the five evaluation seed bases saved for each checkpoint in the existing matched ensemble",
                "policy_seed_schedule": "reuses the per-case PPO/Greedy policy seed pair from that checkpoint's matched config",
                "uniform_transition_seed": "environment seed stream as in existing evaluation; paired PPO/Greedy use the same reset seed and same per-step seed over their shared prefix",
                "deterministic_transition_seed": "not required by REF_DETERMINISTIC_FIRST_SUPPORTED; evaluation and Greedy policy seeds are retained for schedule alignment, but no transition seed is fabricated",
            },
            "resistance_burden": "negative cumulative reward, using the shared normalized resistance burden and all-resistant terminal-tail convention",
            "additional_scenarios": "none; SENSITIVITY_Q_* changes occurrence-probability assumptions rather than only candidate-selection semantics",
        }
    finally:
        for environment in environments.values():
            environment.close()


def _rollout(environment, condition, policy, profile, episode_id, evaluation_seed, policy_seed, policy_name):
    observation, reset_info = environment.reset(
        seed=evaluation_seed,
        options={"initial_resistance_state": profile},
    )
    initial_observation = tuple(float(value) for value in observation)
    initial_state = environment.episode.resistance_state.resistance
    terminal = environment.is_terminal(environment.episode) if condition == DETERMINISTIC_SCENARIO_ID else environment.episode_termination.is_terminated(environment.episode)
    terminal_adjustment = -float(environment.max_steps if condition == DETERMINISTIC_SCENARIO_ID else environment.episode_termination.max_steps) if terminal and all(initial_state) else 0.0
    steps = []
    while not terminal:
        current_episode = environment.episode
        current_state = current_episode.resistance_state.resistance
        action_mask = environment.action_masks()
        if not action_mask.any():
            raise RuntimeError("Nonterminal state has no feasible action.")
        before = tuple(float(value) for value in observation)
        action = int(policy.select_action(observation.copy()))
        if action >= len(action_mask) or not action_mask[action]:
            raise RuntimeError("Policy selected an infeasible action.")
        next_observation, reward, terminal, truncated, info = environment.step(action)
        if truncated:
            raise RuntimeError("Finite-horizon evaluation unexpectedly truncated.")
        next_state = environment.episode.resistance_state.resistance
        if info.get("scenario_id") != condition:
            raise RuntimeError("Transition metadata does not identify the active condition.")
        transition_seed = info.get("transition_seed")
        if condition == DETERMINISTIC_SCENARIO_ID and transition_seed is not None:
            raise RuntimeError("Deterministic reference unexpectedly reports a transition RNG seed.")
        steps.append(StepResult(
            observation=before,
            action=action,
            next_observation=tuple(float(value) for value in next_observation),
            reward=float(reward),
            terminated=bool(terminal),
            truncated=False,
            info=dict(info),
        ))
        observation = next_observation
        if len(steps) > 8:
            raise RuntimeError("Evaluation exceeded the fixed eight-step horizon.")
    final_profile = environment.episode.resistance_state.resistance
    episode = EpisodeResult(
        episode_id=episode_id,
        environment_seed=evaluation_seed,
        policy_seed=policy_seed,
        policy_name=policy_name,
        initial_resistance_profile=initial_state,
        final_resistance_profile=final_profile,
        initial_observation=initial_observation,
        reset_info=reset_info,
        steps=tuple(steps),
        terminated=bool(terminal),
        truncated=False,
        termination_reason=(
            "no_effective_antibiotic" if all(final_profile) else "maximum_horizon"
        ),
        terminal_reward_adjustment=terminal_adjustment,
    )
    return episode


def _initial_observation(profile):
    return np.asarray(
        [*profile, *([0] * len(ANTIBIOTICS)), 0],
        dtype=np.float32,
    )


def _case_record(episode: EpisodeResult, metrics, *, condition, training_seed, schedule_index, seed_base, profile_index):
    burden = -episode.cumulative_reward
    outcomes = [step.info["transition_status"] for step in episode.steps]
    actions = [step.action for step in episode.steps]
    transitions = len(episode.steps)
    resistance_changing = sum(outcome in RESISTANCE_CHANGING_OUTCOMES for outcome in outcomes)
    unsupported = sum(outcome == "unsupported_no_candidate" for outcome in outcomes)
    unchanged = sum(
        tuple(step.observation[:7]) == tuple(step.next_observation[:7])
        for step in episode.steps
    )
    return {
        "condition": condition,
        "training_seed": training_seed,
        "evaluation_schedule_index": schedule_index,
        "evaluation_seed_base": seed_base,
        "profile_index": profile_index,
        "case_id": f"{training_seed}:{seed_base}:profile_{profile_index:03d}",
        "initial_profile": _label(episode.initial_resistance_profile),
        "evaluation_seed": episode.environment_seed,
        "policy_seed": episode.policy_seed,
        "steps": metrics.treatment_steps,
        "final_resistant_count": sum(episode.final_resistance_profile),
        "resistance_emergence_events": metrics.resistance_emergence_events,
        "resistance_emergence_rate": metrics.resistance_emergence_rate,
        "effectiveness_rate": metrics.treatment_effectiveness_rate,
        "cumulative_reward": episode.cumulative_reward,
        "cumulative_resistance_burden": burden,
        "unsupported_no_candidate_count": unsupported,
        "resistance_changing_outcome_count": resistance_changing,
        "unchanged_state_outcome_count": unchanged,
        "unsupported_fraction": unsupported / transitions if transitions else None,
        "resistance_changing_fraction": resistance_changing / transitions if transitions else None,
        "unchanged_state_fraction": unchanged / transitions if transitions else None,
        "transition_count": transitions,
        "action_counts": dict(Counter(ANTIBIOTICS[action] for action in actions)),
        "outcome_counts": dict(Counter(outcomes)),
    }


def _paired_condition_rows(rows):
    indexed = {(row["condition"], row["training_seed"], row["evaluation_seed_base"], row["profile_index"], row["policy"]): row for row in rows}
    paired = []
    keys = {(row["training_seed"], row["evaluation_seed_base"], row["profile_index"], row["policy"]) for row in rows}
    for training_seed, seed_base, profile_index, policy in sorted(keys):
        uniform = indexed[(UNIFORM_SCENARIO_ID, training_seed, seed_base, profile_index, policy)]
        deterministic = indexed[(DETERMINISTIC_SCENARIO_ID, training_seed, seed_base, profile_index, policy)]
        if (uniform["initial_profile"], uniform["evaluation_seed"], uniform["policy_seed"]) != (
            deterministic["initial_profile"], deterministic["evaluation_seed"], deterministic["policy_seed"],
        ):
            raise ValueError("Transition-condition cases are not paired on profile/evaluation/policy seed.")
        paired.append({
            "training_seed": training_seed,
            "evaluation_seed_base": seed_base,
            "profile_index": profile_index,
            "policy": policy,
            "case_id": uniform["case_id"],
            "initial_profile": uniform["initial_profile"],
            "uniform_burden": uniform["cumulative_resistance_burden"],
            "deterministic_burden": deterministic["cumulative_resistance_burden"],
            "transition_effect_deterministic_minus_uniform": deterministic["cumulative_resistance_burden"] - uniform["cumulative_resistance_burden"],
        })
    return paired


def _profile_masks_match(environments, profile):
    masks = []
    for environment in environments.values():
        observation, _ = environment.reset(seed=0, options={"initial_resistance_state": profile})
        expected = np.asarray([bit == 0 for bit in profile.resistance], dtype=bool)
        masks.append(environment.action_masks())
        if not np.array_equal(observation[:7] == 0, expected):
            return False
    return np.array_equal(*masks)


def _profile_observation_contract_matches(environments, profile):
    observations = []
    for environment in environments.values():
        observation, _ = environment.reset(seed=0, options={"initial_resistance_state": profile})
        observations.append(np.asarray(observation, dtype=np.float32))
    return (
        all(np.array_equal(observation[:7], np.asarray(profile.resistance, dtype=np.float32)) for observation in observations)
        and all(np.array_equal(observation[7:14], np.zeros(7, dtype=np.float32)) for observation in observations)
        and all(observation[14] == 0 for observation in observations)
    )


def _paired_policy_rows(rows, condition):
    selected = [row for row in rows if row["condition"] == condition]
    indexed = {
        (row["training_seed"], row["evaluation_seed_base"], row["profile_index"], row["policy"]): row
        for row in selected
    }
    keys = {(row["training_seed"], row["evaluation_seed_base"], row["profile_index"]) for row in selected}
    pairs = []
    for training_seed, seed_base, profile_index in sorted(keys):
        ppo = indexed[(training_seed, seed_base, profile_index, "ppo")]
        greedy = indexed[(training_seed, seed_base, profile_index, "greedy")]
        if (ppo["initial_profile"], ppo["evaluation_seed"], ppo["policy_seed"]) != (
            greedy["initial_profile"], greedy["evaluation_seed"], greedy["policy_seed"],
        ):
            raise ValueError("PPO and Greedy cases are not aligned on profile and evaluation/policy seeds.")
        pairs.append((ppo, greedy))
    if len(indexed) != 2 * len(pairs):
        raise ValueError("PPO/Greedy case set contains missing or duplicate pair members.")
    return pairs


def _aggregate(rows):
    output = {}
    for condition in CONDITIONS:
        for policy in POLICIES:
            selected = [row for row in rows if row["condition"] == condition and row["policy"] == policy]
            output[f"{condition}:{policy}"] = {
                "case_count": len(selected),
                "cumulative_resistance_burden": mean(row["cumulative_resistance_burden"] for row in selected),
                "final_resistant_count": mean(row["final_resistant_count"] for row in selected),
                "resistance_emergence_rate": _mean_defined(row["resistance_emergence_rate"] for row in selected),
                "effectiveness_rate": _mean_defined(row["effectiveness_rate"] for row in selected),
                "cumulative_reward": mean(row["cumulative_reward"] for row in selected),
                "transition_count": sum(row["transition_count"] for row in selected),
            }
    for condition in CONDITIONS:
        ppo = output[f"{condition}:ppo"]["cumulative_resistance_burden"]
        greedy = output[f"{condition}:greedy"]["cumulative_resistance_burden"]
        paired_policy = _paired_policy_rows(rows, condition)
        paired_differences = [greedy_case["cumulative_resistance_burden"] - ppo_case["cumulative_resistance_burden"] for ppo_case, greedy_case in paired_policy]
        profile_differences = defaultdict(list)
        for ppo_case, greedy_case in paired_policy:
            profile_differences[ppo_case["profile_index"]].append(
                greedy_case["cumulative_resistance_burden"] - ppo_case["cumulative_resistance_burden"]
            )
        profile_mean_differences = [mean(values) for values in profile_differences.values()]
        output[f"{condition}:paired_ppo_vs_greedy"] = {
            "paired_case_count": len(paired_differences),
            "ppo_mean_burden": ppo,
            "greedy_mean_burden": greedy,
            "mean_greedy_minus_ppo_burden": mean(paired_differences),
            "ppo_better_matched_cases": sum(value > 1e-12 for value in paired_differences),
            "tied_matched_cases": sum(abs(value) <= 1e-12 for value in paired_differences),
            "greedy_better_matched_cases": sum(value < -1e-12 for value in paired_differences),
            "profile_direction_counts": {
                "profile_count": len(profile_mean_differences),
                "ppo_better_profiles": sum(value > 1e-12 for value in profile_mean_differences),
                "tied_profiles": sum(abs(value) <= 1e-12 for value in profile_mean_differences),
                "greedy_better_profiles": sum(value < -1e-12 for value in profile_mean_differences),
            },
            "case_difference_distribution_units": "descriptive matched trajectories; not independent inference units",
        }
    output["per_training_seed"] = {}
    output["per_training_seed_schedule"] = {}
    for seed in sorted({row["training_seed"] for row in rows}):
        output["per_training_seed"][str(seed)] = {}
        output["per_training_seed_schedule"][str(seed)] = {}
        for condition in CONDITIONS:
            seed_rows = [row for row in rows if row["training_seed"] == seed and row["condition"] == condition]
            paired = _paired_policy_rows(seed_rows, condition)
            differences = [greedy["cumulative_resistance_burden"] - ppo["cumulative_resistance_burden"] for ppo, greedy in paired]
            output["per_training_seed"][str(seed)][condition] = {
                "matched_case_count": len(paired),
                "ppo_mean_burden": mean(ppo["cumulative_resistance_burden"] for ppo, _ in paired),
                "greedy_mean_burden": mean(greedy["cumulative_resistance_burden"] for _, greedy in paired),
                "mean_greedy_minus_ppo_burden": mean(differences),
            }
            output["per_training_seed_schedule"][str(seed)][condition] = {}
            for seed_base in sorted({row["evaluation_seed_base"] for row in seed_rows}):
                schedule_rows = [row for row in seed_rows if row["evaluation_seed_base"] == seed_base]
                schedule_pairs = _paired_policy_rows(schedule_rows, condition)
                schedule_differences = [greedy["cumulative_resistance_burden"] - ppo["cumulative_resistance_burden"] for ppo, greedy in schedule_pairs]
                output["per_training_seed_schedule"][str(seed)][condition][str(seed_base)] = {
                    "matched_case_count": len(schedule_pairs),
                    "ppo_mean_burden": mean(ppo["cumulative_resistance_burden"] for ppo, _ in schedule_pairs),
                    "greedy_mean_burden": mean(greedy["cumulative_resistance_burden"] for _, greedy in schedule_pairs),
                    "mean_greedy_minus_ppo_burden": mean(schedule_differences),
                }
    return output


def _mean_defined(values):
    data = [value for value in values if value is not None]
    return mean(data) if data else None


def _transition_sensitivity(rows, paired_conditions):
    output = {}
    for policy in POLICIES:
        selected = [row for row in paired_conditions if row["policy"] == policy]
        by_seed = defaultdict(list)
        for row in selected:
            by_seed[row["training_seed"]].append(row["transition_effect_deterministic_minus_uniform"])
        output[policy] = {
            "mean_deterministic_minus_uniform_burden": mean(row["transition_effect_deterministic_minus_uniform"] for row in selected),
            "per_training_seed_mean_effect": {str(seed): mean(values) for seed, values in sorted(by_seed.items())},
        }
    condition_differences = {
        condition: _aggregate(rows)[f"{condition}:paired_ppo_vs_greedy"]["mean_greedy_minus_ppo_burden"]
        for condition in CONDITIONS
    }
    uniform_delta = condition_differences[UNIFORM_SCENARIO_ID]
    deterministic_delta = condition_differences[DETERMINISTIC_SCENARIO_ID]
    output["ppo_vs_greedy_ranking"] = {
        "uniform_greedy_minus_ppo": uniform_delta,
        "deterministic_greedy_minus_ppo": deterministic_delta,
        "change_in_paired_burden_difference": deterministic_delta - uniform_delta,
        "ranking_preserved": (uniform_delta > 1e-12 and deterministic_delta > 1e-12)
        or (uniform_delta < -1e-12 and deterministic_delta < -1e-12)
        or (abs(uniform_delta) <= 1e-12 and abs(deterministic_delta) <= 1e-12),
        "ranking_reversed": uniform_delta * deterministic_delta < 0,
        "interpretation": "descriptive condition-level mean ranking; no inferential claim",
    }
    return output


def _unsupported_audit(rows):
    output = {}
    for condition in CONDITIONS:
        for policy in POLICIES:
            selected = [row for row in rows if row["condition"] == condition and row["policy"] == policy]
            total = sum(row["transition_count"] for row in selected)
            unsupported = sum(row["unsupported_no_candidate_count"] for row in selected)
            changing = sum(row["resistance_changing_outcome_count"] for row in selected)
            unchanged = sum(row["unchanged_state_outcome_count"] for row in selected)
            antibiotic_rows = {}
            for antibiotic in ANTIBIOTICS:
                records = []
                for row in selected:
                    trajectory = row["trajectory"]
                    records.extend(step for step in trajectory["steps"] if step["info"]["antibiotic"] == antibiotic)
                outcome_counts = Counter(step["info"]["transition_status"] for step in records)
                antibiotic_rows[antibiotic] = {
                    "action_count": len(records),
                    "unsupported_fraction": outcome_counts.get("unsupported_no_candidate", 0) / len(records) if records else None,
                    "resistance_changing_fraction": sum(outcome_counts.get(outcome, 0) for outcome in RESISTANCE_CHANGING_OUTCOMES) / len(records) if records else None,
                    "unchanged_state_fraction": sum(tuple(step["observation"][:7]) == tuple(step["next_observation"][:7]) for step in records) / len(records) if records else None,
                    "outcome_counts": dict(outcome_counts),
                }
            output[f"{condition}:{policy}"] = {
                "action_count": total,
                "unsupported_no_candidate_fraction": unsupported / total if total else None,
                "resistance_changing_outcome_fraction": changing / total if total else None,
                "unchanged_state_outcome_fraction": unchanged / total if total else None,
                "outcome_counts_by_antibiotic": antibiotic_rows,
                "gentamicin": antibiotic_rows["GENTAMICIN"],
                "interpretation": "unsupported_no_candidate is an unchanged computational outcome, not a biological benefit",
            }
    return output


def _first_divergence(rows):
    indexed = {(row["condition"], row["training_seed"], row["evaluation_seed_base"], row["profile_index"], row["policy"]): row for row in rows}
    output = {}
    for policy in POLICIES:
        counts = Counter()
        for key in sorted({(row["training_seed"], row["evaluation_seed_base"], row["profile_index"]) for row in rows}):
            uniform = indexed[(UNIFORM_SCENARIO_ID, *key, policy)]["trajectory"]
            deterministic = indexed[(DETERMINISTIC_SCENARIO_ID, *key, policy)]["trajectory"]
            for step_index, (u_step, d_step) in enumerate(zip(uniform["steps"], deterministic["steps"])):
                u_state = tuple(u_step["observation"][:7])
                d_state = tuple(d_step["observation"][:7])
                if u_state != d_state:
                    counts["prior_trajectory_divergence"] += 1
                    break
                if u_step["action"] != d_step["action"]:
                    counts["policy_action_divergence_on_shared_state"] += 1
                    break
                if u_step["info"]["transition_status"] != d_step["info"]["transition_status"] or tuple(u_step["next_observation"][:7]) != tuple(d_step["next_observation"][:7]):
                    counts["first_divergence_at_candidate_selection"] += 1
                    break
            else:
                if len(uniform["steps"]) != len(deterministic["steps"]):
                    counts["episode_length_divergence_after_shared_steps"] += 1
                else:
                    counts["no_trajectory_divergence"] += 1
        output[policy] = dict(counts)
    return output


def _write_csv(path: Path, rows):
    import csv

    if not rows:
        raise ValueError(f"Refusing to write empty table: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, allow_nan=False) if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def _report(compatibility, summary, sensitivity, audit, first_divergence, rows, profile_rows, plots):
    lines = [
        "# Transition-Selection Sensitivity: PPO vs Greedy", "",
        "This is a policy-transfer and computational sensitivity analysis of frozen policies. It tests sensitivity to the supported-candidate selection rule, not biological uncertainty or stochastic optimality.", "",
        "## Compatibility", "",
        "| Contract | Verified |", "|---|---:|",
    ]
    lines.extend(f"| {name.replace('_', ' ')} | {'yes' if passed else 'no'} |" for name, passed in compatibility["contract_checks"].items())
    lines.extend(["", "| Condition | Selection semantics | Transition seed |", "|---|---|---|"])
    for condition, details in compatibility["conditions"].items():
        lines.append(f"| `{condition}` | {details['selection']} | {details['transition_randomness']} |")
    lines.extend([
        "", "All 128 canonical initial profiles, horizon 8, reward definition, mask rule, and saved per-checkpoint evaluation/Greedy policy-seed schedules are identical across conditions. Uniform candidates are sampled after deduplication; deterministic-first selects the lexicographically smallest `(target_drug, outcome)`. No additional scenario was introduced.",
        "", "## PPO vs Greedy", "",
        "Positive `Greedy - PPO` burden means PPO has lower burden. Counts classify matched trajectory differences using the existing $10^{-12}$ tie convention; percentages use matched cases.",
        "", "| Condition | PPO burden | Greedy burden | Greedy - PPO | Profile directions: PPO lower / tied / Greedy lower | Paired cases: PPO better / tied / Greedy better | Final R: PPO / Greedy | Emergence: PPO / Greedy | Effectiveness: PPO / Greedy | Reward: PPO / Greedy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for condition in CONDITIONS:
        ppo = summary[f"{condition}:ppo"]
        greedy = summary[f"{condition}:greedy"]
        paired = summary[f"{condition}:paired_ppo_vs_greedy"]
        profile_directions = paired["profile_direction_counts"]
        count = paired["paired_case_count"]
        lines.append(
            f"| `{condition}` | {ppo['cumulative_resistance_burden']:.4f} | {greedy['cumulative_resistance_burden']:.4f} | {paired['mean_greedy_minus_ppo_burden']:+.4f} | "
            f"{profile_directions['ppo_better_profiles']} / {profile_directions['tied_profiles']} / {profile_directions['greedy_better_profiles']} of {profile_directions['profile_count']} | "
                f"{paired['ppo_better_matched_cases']} ({paired['ppo_better_matched_cases']/count:.1%}) / {paired['tied_matched_cases']} ({paired['tied_matched_cases']/count:.1%}) / "
                f"{paired['greedy_better_matched_cases']} ({paired['greedy_better_matched_cases']/count:.1%}) | "
            f"{ppo['final_resistant_count']:.3f} / {greedy['final_resistant_count']:.3f} | {ppo['resistance_emergence_rate']:.4f} / {greedy['resistance_emergence_rate']:.4f} | "
            f"{ppo['effectiveness_rate']:.4f} / {greedy['effectiveness_rate']:.4f} | {ppo['cumulative_reward']:.4f} / {greedy['cumulative_reward']:.4f} |"
        )
    lines.extend(["", "## Transition Sensitivity", "", "| Policy / contrast | Mean deterministic - uniform burden |", "|---|---:|"])
    for policy in POLICIES:
        lines.append(f"| {policy.upper()} | {sensitivity[policy]['mean_deterministic_minus_uniform_burden']:+.4f} |")
    ranking = sensitivity["ppo_vs_greedy_ranking"]
    lines.extend([
        f"\nThe paired Greedy-minus-PPO burden difference changes by {ranking['change_in_paired_burden_difference']:+.4f} between conditions. Ranking preserved: **{ranking['ranking_preserved']}**; reversed: **{ranking['ranking_reversed']}**.",
        "", "Means are descriptive over the five frozen checkpoints, five saved evaluation schedules per checkpoint, and 128 profiles. The hierarchy is retained in raw rows and per-checkpoint tables; trajectories are not treated as independent inference units. No bootstrap interval or significance test is reported.",
        "", "## Unsupported-Transition Audit", "",
        "Rates below use actions as denominator. Resistance-changing outcomes are the existing `cross_resistance` and `collateral_sensitivity` statuses; unchanged-state fraction is computed from before/after resistance vectors. Categories may overlap because a supported neutral outcome can leave state unchanged.",
        "", "| Condition | Policy | Actions | Unsupported | Resistance-changing | Unchanged-state | Gentamicin count / unsupported / resistance-changing / unchanged |", "|---|---|---:|---:|---:|---:|---|",
    ])
    for condition in CONDITIONS:
        for policy in POLICIES:
            item = audit[f"{condition}:{policy}"]
            gent = item["gentamicin"]
            lines.append(
                f"| `{condition}` | {policy.upper()} | {item['action_count']} | {item['unsupported_no_candidate_fraction']:.2%} | {item['resistance_changing_outcome_fraction']:.2%} | {item['unchanged_state_outcome_fraction']:.2%} | "
                f"{gent['action_count']} / {gent['unsupported_fraction']:.2%} / {gent['resistance_changing_fraction']:.2%} / {gent['unchanged_state_fraction']:.2%} |"
            )
    lines.extend([
        "", "`unsupported_no_candidate` means no applicable supported candidate in the computational dataset; it is not interpreted as biological benefit.",
        "", "### Gentamicin", "",
    ])
    for condition in CONDITIONS:
        for policy in POLICIES:
            gent = audit[f"{condition}:{policy}"]["gentamicin"]
            lines.append(f"- `{condition}`, {policy.upper()}: {gent['action_count']} actions; outcome counts {gent['outcome_counts']}.")
    lines.extend([
        "", "### Outcome Counts by Antibiotic", "",
        "Full status counts are in `outcome_counts_by_antibiotic.csv`; unchanged-state status is counted from the observed before/after resistance vectors.",
        "", "| Condition | Policy | Antibiotic | Actions | Unsupported | Resistance-changing | Unchanged-state | Exact outcomes |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ])
    for condition in CONDITIONS:
        for policy in POLICIES:
            for antibiotic, item in audit[f"{condition}:{policy}"]["outcome_counts_by_antibiotic"].items():
                unsupported_count = item["outcome_counts"].get("unsupported_no_candidate", 0)
                changing_count = sum(item["outcome_counts"].get(outcome, 0) for outcome in RESISTANCE_CHANGING_OUTCOMES)
                unchanged_count = sum(
                    tuple(step["observation"][:7]) == tuple(step["next_observation"][:7])
                    for row in rows
                    if row["condition"] == condition and row["policy"] == policy
                    for step in row["trajectory"]["steps"]
                    if step["info"]["antibiotic"] == antibiotic
                )
                lines.append(f"| `{condition}` | {policy.upper()} | {antibiotic} | {item['action_count']} | {unsupported_count} | {changing_count} | {unchanged_count} | {item['outcome_counts']} |")
    lines.extend([
        "", "### First Cross-Condition Divergence", "",
    ])
    for policy, counts in first_divergence.items():
        lines.append(f"- {policy.upper()}: {counts}.")
    lines.extend([
        "", "Differences at the first matched state/action transition arise from candidate-selection semantics: both conditions use the same applicability rules and candidate evidence, but select differently among supported candidates. Later action and state differences can be downstream consequences.",
        "", "## Paired Profile Comparison", "",
        "`paired_profile_means.csv` reports each profile's Greedy-minus-PPO burden averaged within condition across the checkpoint/schedule hierarchy. It is descriptive; profiles are not independent training replicates.",
        "", "| Condition | PPO lower-burden profiles | Tied profiles | Greedy lower-burden profiles |", "|---|---:|---:|---:|",
    ])
    for condition in CONDITIONS:
        profile_group = [row for row in profile_rows if row["condition"] == condition]
        by_profile = defaultdict(list)
        for row in profile_group:
            by_profile[row["profile_index"]].append(row["greedy_minus_ppo_burden"])
        means = [mean(values) for values in by_profile.values()]
        lines.append(f"| `{condition}` | {sum(value > 1e-12 for value in means)} | {sum(abs(value) <= 1e-12 for value in means)} | {sum(value < -1e-12 for value in means)} |")
    lines.extend(["", "## Plots", "", *[f"- `{plot}`" for plot in plots], "", "## Interpretation and Limits", "", "A preserved PPO-versus-Greedy burden ranking supports robustness across the two evaluated computational transition-selection conditions only; a changed or reversed ranking indicates sensitivity to the computational transition-selection rule. Neither result validates the candidate set biologically. The deterministic reference is a computational fixture, not ground truth. The PPO models remain trained under `REF_UNIFORM_SUPPORTED`; results under deterministic-first are policy transfer.", "", "No models were retrained. No PPO training, reward, transition implementation, action mask, or Value Iteration code was changed.", "", "## Artifacts", "", "`compatibility.json`; `summary.json`; `raw_results.csv`; `raw_trajectories.jsonl`; `paired_transition_effects.csv`; `paired_profile_means.csv`; `transition_sensitivity.csv`; `unsupported_transition_audit.json`; `outcome_counts_by_antibiotic.csv`; `first_divergence.json`; `plots/."])
    return "\n".join(lines) + "\n"


def run_transition_selection_sensitivity(matched_results_dir, config_path, output_dir):
    matched_results_dir, output_dir = Path(matched_results_dir), Path(output_dir)
    config = PPOConfig.from_json(config_path)
    compatibility = inspect_transition_compatibility(config)
    source_config = json.loads((matched_results_dir / "config.json").read_text(encoding="utf-8"))
    if source_config["scenario_id"] != UNIFORM_SCENARIO_ID or source_config["horizon"] != 8:
        raise ValueError("Source matched run is not the required REF_UNIFORM_SUPPORTED, H=8 evaluation.")
    expected_training_seeds = {int(Path(path).parent.name.split("_")[-1]) for path in source_config["training_models"]}
    if expected_training_seeds != {int(seed) for seed in source_config["evaluation_seed_bases_by_training_seed"]}:
        raise ValueError("Saved checkpoint list and per-checkpoint evaluation schedules differ.")
    schedule_counts = {len(bases) for bases in source_config["evaluation_seed_bases_by_training_seed"].values()}
    if schedule_counts != {5}:
        raise ValueError("Step 7 requires the five established evaluation schedules per checkpoint.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Sensitivity output directory is not empty: {output_dir}")
    profiles = canonical_initial_profiles()
    profile_vectors = tuple(profile.resistance for profile in profiles)
    if len(profiles) != 128 or len(set(profile_vectors)) != 128:
        raise RuntimeError("Canonical profile set must contain each of 128 profiles exactly once.")
    saved_profiles = tuple(tuple(profile) for profile in source_config.get("initial_profiles", ()))
    if saved_profiles != profile_vectors:
        raise ValueError("Source matched results do not contain the canonical 128-profile evaluation order.")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "compatibility.json").write_text(json.dumps(compatibility, indent=2, allow_nan=False), encoding="utf-8")
    rows, trajectories = [], []
    model_provenance = []
    immutable_digests = {}
    for training_seed_text, seed_bases in source_config["evaluation_seed_bases_by_training_seed"].items():
        training_seed = int(training_seed_text)
        model_dir = matched_results_dir / "models" / f"ppo_seed_{training_seed}"
        model_config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        model_path = Path(model_config["ppo_model_path"])
        if not model_path.is_absolute():
            model_path = Path.cwd() / model_path
        training_config_path = model_path.parent / "config.json"
        training_config_digest = _sha256(training_config_path)
        checkpoint_digest = _sha256(model_path)
        model = load_ppo_model(model_path, device=config.device)
        if model.action_space.n != len(ANTIBIOTICS) or model.observation_space.shape != (15,):
            raise ValueError(f"Checkpoint contract mismatch for training seed {training_seed}.")
        training_config = json.loads(training_config_path.read_text(encoding="utf-8"))
        training_manifest = json.loads((model_path.parent / "environment_manifest.json").read_text(encoding="utf-8"))
        current_manifest = environment_manifest(config)
        if (
            training_config.get("scenario_id") != UNIFORM_SCENARIO_ID
            or training_config.get("horizon") != 8
            or training_config.get("gamma") != 1.0
            or training_manifest.get("reward_specification") != config.reward_configuration
            or training_manifest.get("action_masking") is not True
            or training_manifest.get("interaction_data_sha256") != current_manifest.get("interaction_data_sha256")
            or training_manifest.get("action_names") != list(ANTIBIOTICS)
            or model.gamma != 1.0
            or model.action_space.start != 0
        ):
            raise ValueError(f"Checkpoint training contract mismatch for training seed {training_seed}.")
        policy_seed_pairs = model_config["policy_seed_pairs"]
        if [pair[0] for pair in policy_seed_pairs] != seed_bases:
            raise ValueError("Saved evaluation seeds and policy-seed schedule are not aligned.")
        model_provenance.append({
            "training_seed": training_seed,
            "checkpoint": str(model_path),
            "checkpoint_sha256": checkpoint_digest,
            "training_config_sha256": training_config_digest,
            "schedule_count": len(seed_bases),
        })
        immutable_digests[str(model_path)] = checkpoint_digest
        for schedule_index, (seed_base, policy_pair) in enumerate(zip(seed_bases, policy_seed_pairs)):
            if policy_pair[0] != seed_base:
                raise ValueError("Evaluation seed and Greedy policy seed schedule mismatch.")
            environment_seed_base, greedy_policy_seed_base = policy_pair
            for condition in CONDITIONS:
                environment = _environment_for_condition(condition, config)
                try:
                    for profile_index, profile in enumerate(profiles):
                        evaluation_seed = seed_base + profile_index
                        policy_seed = greedy_policy_seed_base + profile_index
                        for policy_name in POLICIES:
                            if policy_name == "ppo":
                                policy = MaskablePPOObservationPolicy(environment.action_space, model)
                            else:
                                policy = GreedyPolicy(environment.action_space, seed=policy_seed)
                            episode = _rollout(
                                environment, condition, policy, profile, profile_index,
                                evaluation_seed, policy_seed, policy_name,
                            )
                            metrics = calculate_episode_metrics(
                                episode,
                                scenario_id=condition,
                            )
                            row = _case_record(
                                episode, metrics, condition=condition, training_seed=training_seed,
                                schedule_index=schedule_index, seed_base=seed_base,
                                profile_index=profile_index,
                            )
                            row["policy"] = policy_name
                            row["trajectory"] = asdict(episode)
                            row["transition_seed_semantics"] = (
                                "per-step transition seed recorded in info"
                                if condition == UNIFORM_SCENARIO_ID
                                else "not applicable; deterministic-first has no transition RNG"
                            )
                            rows.append(row)
                            trajectories.append({
                                "condition": condition,
                                "training_seed": training_seed,
                                "evaluation_schedule_index": schedule_index,
                                "evaluation_seed_base": seed_base,
                                "profile_index": profile_index,
                                "profile": _label(profile.resistance),
                                "policy": policy_name,
                                "evaluation_seed": evaluation_seed,
                                "policy_seed": policy_seed,
                                "transition_seed_semantics": row["transition_seed_semantics"],
                                "trajectory": asdict(episode),
                            })
                finally:
                    environment.close()
        if _sha256(model_path) != checkpoint_digest or _sha256(training_config_path) != training_config_digest:
            raise RuntimeError("Frozen checkpoint or training configuration changed during evaluation.")
        del model
    expected = len(model_provenance) * len(source_config["evaluation_seed_bases_by_training_seed"][str(model_provenance[0]["training_seed"])]) * len(profiles) * len(CONDITIONS) * len(POLICIES)
    if len(rows) != expected or len({(row["condition"], row["case_id"], row["policy"]) for row in rows}) != expected:
        raise RuntimeError("Sensitivity evaluation case coverage or uniqueness check failed.")
    profile_case_index = {
        (row["condition"], row["training_seed"], row["evaluation_seed_base"], row["profile_index"], row["policy"]): row
        for row in rows
    }
    for training_seed_text, seed_bases in source_config["evaluation_seed_bases_by_training_seed"].items():
        for seed_base in seed_bases:
            for profile_index, profile in enumerate(profiles):
                for condition in CONDITIONS:
                    ppo = profile_case_index[(condition, int(training_seed_text), seed_base, profile_index, "ppo")]
                    if ppo["initial_profile"] != _label(profile.resistance):
                        raise RuntimeError("Canonical initial profile ordering changed.")
    paired_conditions = _paired_condition_rows(rows)
    summary = _aggregate(rows)
    sensitivity = _transition_sensitivity(rows, paired_conditions)
    audit = _unsupported_audit(rows)
    first_divergence = _first_divergence(rows)
    paired_profile_rows = []
    for condition in CONDITIONS:
        for training_seed_text, seed_bases in source_config["evaluation_seed_bases_by_training_seed"].items():
            training_seed = int(training_seed_text)
            for profile_index, profile in enumerate(profiles):
                matched = []
                ppo_profile_values = []
                greedy_profile_values = []
                for seed_base in seed_bases:
                    ppo = profile_case_index[(condition, training_seed, seed_base, profile_index, "ppo")]
                    greedy = profile_case_index[(condition, training_seed, seed_base, profile_index, "greedy")]
                    matched.append(greedy["cumulative_resistance_burden"] - ppo["cumulative_resistance_burden"])
                    ppo_profile_values.append(ppo["cumulative_resistance_burden"])
                    greedy_profile_values.append(greedy["cumulative_resistance_burden"])
                paired_profile_rows.append({
                    "condition": condition,
                    "training_seed": training_seed,
                    "profile_index": profile_index,
                    "initial_profile": _label(profile.resistance),
                    "schedule_count": len(matched),
                    "ppo_mean_burden": mean(ppo_profile_values),
                    "greedy_mean_burden": mean(greedy_profile_values),
                    "greedy_minus_ppo_burden": mean(matched),
                })
    outcome_rows = []
    for key, details in audit.items():
        condition, policy = key.split(":")
        for antibiotic, item in details["outcome_counts_by_antibiotic"].items():
            outcome_rows.append({"condition": condition, "policy": policy, "antibiotic": antibiotic, **item})
    paired_output = [{key: value for key, value in row.items() if key != "trajectory"} for row in paired_conditions]
    (output_dir / "summary.json").write_text(json.dumps({
        "conditions": summary,
        "transition_sensitivity": sensitivity,
        "unsupported_transition_audit": audit,
        "first_cross_condition_divergence": first_divergence,
        "model_provenance": model_provenance,
        "initial_profile_count": len(profiles),
        "evaluation_schedule_count_per_checkpoint": len(source_config["evaluation_seed_bases_by_training_seed"][str(model_provenance[0]["training_seed"])]),
        "training_checkpoint_count": len(model_provenance),
        "matched_policy_case_count_per_condition": expected // len(CONDITIONS),
        "paired_inference_unit": "no interval/testing; all summaries descriptive and checkpoint/schedule/profile hierarchy retained",
    }, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "unsupported_transition_audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "first_divergence.json").write_text(json.dumps(first_divergence, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(output_dir / "raw_results.csv", [{key: value for key, value in row.items() if key != "trajectory"} for row in rows])
    (output_dir / "raw_trajectories.jsonl").write_text(
        "".join(json.dumps(item, allow_nan=False) + "\n" for item in trajectories),
        encoding="utf-8",
    )
    _write_csv(output_dir / "paired_transition_effects.csv", paired_output)
    _write_csv(output_dir / "paired_profile_means.csv", paired_profile_rows)
    _write_csv(output_dir / "transition_sensitivity.csv", [{
        "policy": policy,
        "mean_deterministic_minus_uniform_burden": sensitivity[policy]["mean_deterministic_minus_uniform_burden"],
        **{f"training_seed_{seed}": value for seed, value in sensitivity[policy]["per_training_seed_mean_effect"].items()},
    } for policy in POLICIES])
    _write_csv(output_dir / "outcome_counts_by_antibiotic.csv", outcome_rows)
    config_record = {
        "source_matched_results_dir": str(matched_results_dir),
        "source_config_sha256": _sha256(matched_results_dir / "config.json"),
        "conditions": list(CONDITIONS),
        "evaluation_seed_bases_by_training_seed": source_config["evaluation_seed_bases_by_training_seed"],
        "profile_order": "canonical itertools.product((0,1),repeat=7), all 128 states",
        "reward": compatibility["contract_details"][UNIFORM_SCENARIO_ID]["reward_specification"],
        "action_mask": "susceptible_actions_only",
        "horizon": 8,
        "deterministic_transition_seed": "not applicable; no transition RNG used",
        "models": model_provenance,
        "no_training_or_configuration_mutation": True,
    }
    (output_dir / "config.json").write_text(json.dumps(config_record, indent=2, allow_nan=False), encoding="utf-8")
    plots = generate_transition_sensitivity_plots(rows, paired_conditions, audit, output_dir / "plots")
    (output_dir / "report.md").write_text(_report(compatibility, summary, sensitivity, audit, first_divergence, rows, paired_profile_rows, plots), encoding="utf-8")
    return json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Paired frozen-checkpoint sensitivity to supported transition selection.")
    parser.add_argument("--matched-results-dir", required=True)
    parser.add_argument("--config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run_transition_selection_sensitivity(
        arguments.matched_results_dir, arguments.config, arguments.output_dir,
    ), indent=2))


if __name__ == "__main__":
    main()