from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

from ml.src.ppo_evaluation import canonical_initial_profiles
from simulation.resistance_state import ANTIBIOTICS
from simulation.transition_sampler import REFERENCE_SCENARIO_ID


OBJECTIVES = ("A_normalized_burden", "B_unnormalized_burden", "C_emergence_only", "D_terminal_resistance")
OBJECTIVE_DEFINITIONS = {
    "A_normalized_burden": {
        "formula": "r_t = -N_R(s_{t+1}) / 7; all-resistant terminal-tail convention as implemented",
        "class": "current baseline",
        "learning_interpretation": "existing frozen policy evaluated under its trained objective",
    },
    "B_unnormalized_burden": {
        "formula": "r_t = -N_R(s_{t+1}); same all-resistant terminal-tail convention",
        "class": "reward-scale equivalent to A by positive factor 7",
        "learning_interpretation": "evaluation-only; PPO optimization response to scale would require retraining",
    },
    "C_emergence_only": {
        "formula": "r_t = -max(0, N_R(s_{t+1}) - N_R(s_t))",
        "class": "objective-changing; penalizes increases only and not existing resistance",
        "learning_interpretation": "policy evaluation under an alternative objective; training response requires retraining",
    },
    "D_terminal_resistance": {
        "formula": "R = -N_R(s_T) / 7 at episode end; zero at all earlier steps",
        "class": "objective-changing; terminal-state only",
        "learning_interpretation": "policy evaluation under an alternative objective; training response requires retraining",
    },
}
TIE_TOLERANCE = 1e-12


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resistance_profile(values, *, label: str) -> tuple[int, ...]:
    if not isinstance(values, (tuple, list)) or len(values) != len(ANTIBIOTICS):
        raise ValueError(f"{label} must contain seven resistance values.")
    if any(isinstance(value, bool) or value not in (0, 1) for value in values):
        raise ValueError(f"{label} values must be binary integers.")
    return tuple(int(value) for value in values)


def score_episode_objectives(episode: dict, *, horizon: int = 8) -> dict:
    """Re-score one stored trajectory without mutating it or an environment."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("Horizon must be a positive integer.")
    initial = _resistance_profile(episode["initial_resistance_profile"], label="Initial profile")
    steps = episode["steps"]
    if len(steps) > horizon:
        raise ValueError("Trajectory exceeds the specified horizon.")
    if all(initial) and steps:
        raise ValueError("An initially all-resistant episode cannot contain policy actions.")
    current = initial
    normalized_return = -float(horizon) if all(initial) else 0.0
    positive_increases = 0
    resistant_count_path = [sum(initial)]
    normalized_reward_sequence = []
    emergence_reward_sequence = []
    for step_index, step in enumerate(steps):
        before = _resistance_profile(step["observation"][:7], label="Step observation")
        after = _resistance_profile(step["next_observation"][:7], label="Next observation")
        if before != current:
            raise ValueError("Trajectory resistance states are discontinuous.")
        action = step["action"]
        if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < len(ANTIBIOTICS):
            raise ValueError("Trajectory action ID is invalid.")
        if before[action] != 0 or step["info"].get("effective") is not True:
            raise ValueError("Trajectory contains an infeasible or ineffective selected action.")
        if step["info"].get("antibiotic") != ANTIBIOTICS[action]:
            raise ValueError("Transition antibiotic does not match the canonical action ID.")
        if step["info"].get("scenario_id") != REFERENCE_SCENARIO_ID:
            raise ValueError("Reward sensitivity input must use REF_UNIFORM_SUPPORTED.")
        before_count, after_count = sum(before), sum(after)
        remaining_steps = horizon - step_index - 1
        step_return = -after_count / 7
        if after_count == 7:
            step_return -= remaining_steps
        normalized_return += step_return
        positive_increases += max(0, after_count - before_count)
        normalized_reward_sequence.append(step_return)
        emergence_reward_sequence.append(-max(0, after_count - before_count))
        resistant_count_path.append(after_count)
        current = after
        if after_count == 7 and step_index != len(steps) - 1:
            raise ValueError("All-resistant terminal state must end the recorded trajectory.")
    final = _resistance_profile(episode["final_resistance_profile"], label="Final profile")
    if final != current:
        raise ValueError("Recorded final profile disagrees with the trajectory.")
    stored_return = sum(float(step["reward"]) for step in steps) + float(episode.get("terminal_reward_adjustment", 0.0))
    if not math.isclose(normalized_return, stored_return, rel_tol=0, abs_tol=1e-10):
        raise ValueError("Re-scored baseline return differs from the stored canonical rewards.")
    unnormalized_return = 7.0 * normalized_return
    terminal_return = -sum(final) / 7
    terminal_reward_sequence = [0.0] * len(steps)
    terminal_reward_adjustment = terminal_return if not steps else 0.0
    if terminal_reward_sequence:
        terminal_reward_sequence[-1] = terminal_return
    return {
        "A_normalized_burden": normalized_return,
        "B_unnormalized_burden": unnormalized_return,
        "C_emergence_only": -float(positive_increases),
        "D_terminal_resistance": terminal_return,
        "A_reward_sequence": normalized_reward_sequence,
        "B_reward_sequence": [7.0 * reward for reward in normalized_reward_sequence],
        "C_reward_sequence": emergence_reward_sequence,
        "D_reward_sequence": terminal_reward_sequence,
        "A_terminal_reward_adjustment": -float(horizon) if all(initial) else 0.0,
        "B_terminal_reward_adjustment": -7.0 * float(horizon) if all(initial) else 0.0,
        "C_terminal_reward_adjustment": 0.0,
        "D_terminal_reward_adjustment": terminal_reward_adjustment,
        "positive_resistance_increases": positive_increases,
        "final_resistant_count": sum(final),
        "resistance_count_path": resistant_count_path,
        "transition_count": len(steps),
    }


def _episode_metrics(episode: dict) -> dict:
    steps = episode["steps"]
    initial = _resistance_profile(episode["initial_resistance_profile"], label="Initial profile")
    previous = initial
    emergence_events = 0
    effective_steps = 0
    for step in steps:
        current = _resistance_profile(step["observation"][:7], label="Step observation")
        next_state = _resistance_profile(step["next_observation"][:7], label="Next observation")
        if current != previous:
            raise ValueError("Episode metric trajectory states are discontinuous.")
        emergence_events += int(sum(next_state) > sum(current))
        effective_steps += int(step["info"].get("effective") is True)
        previous = next_state
    final = _resistance_profile(episode["final_resistance_profile"], label="Final profile")
    if final != previous:
        raise ValueError("Episode metric final state disagrees with trajectory.")
    count = len(steps)
    return {
        "cumulative_resistance_burden": -(
            sum(float(step["reward"]) for step in steps)
            + float(episode.get("terminal_reward_adjustment", 0.0))
        ),
        "final_resistant_antibiotics": sum(final),
        "resistance_emergence_events": emergence_events,
        "resistance_emergence_rate": emergence_events / count if count else None,
        "treatment_effectiveness_rate": effective_steps / count if count else None,
        "cumulative_antibiotic_exposure": count,
        "treatment_steps": count,
        "cumulative_reward": sum(float(step["reward"]) for step in steps) + float(episode.get("terminal_reward_adjustment", 0.0)),
    }


def _validate_close(actual, expected, field, case_id):
    if expected == "":
        expected = None
    if actual is None or expected is None:
        if actual is not None or expected is not None:
            raise ValueError(f"{case_id}: {field} definedness differs from matched results.")
        return
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"{case_id}: {field} differs from the saved matched result.")


def _load_cases(matched_results_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    source_config = json.loads((matched_results_dir / "config.json").read_text(encoding="utf-8"))
    if source_config.get("scenario_id") != REFERENCE_SCENARIO_ID or source_config.get("horizon") != 8:
        raise ValueError("Step 8 requires the existing REF_UNIFORM_SUPPORTED, horizon-8 matched evaluation.")
    profiles = tuple(profile.resistance for profile in canonical_initial_profiles())
    if tuple(tuple(profile) for profile in source_config.get("initial_profiles", ())) != profiles:
        raise ValueError("Saved matched evaluation does not use all 128 canonical profiles in order.")
    schedule_map = source_config.get("evaluation_seed_bases_by_training_seed")
    if not isinstance(schedule_map, dict) or len(schedule_map) != 5:
        raise ValueError("Step 8 requires all five saved checkpoint schedules.")
    seeds = tuple(sorted(int(seed) for seed in schedule_map))
    if tuple(seeds) != (1000, 2000, 3000, 4000, 5000):
        raise ValueError("Unexpected checkpoint seed set in matched results.")
    if any(len(schedule_map[str(seed)]) != 5 for seed in seeds):
        raise ValueError("Each checkpoint must have the five existing evaluation schedules.")

    case_rows = []
    trajectory_rows = []
    source_provenance = []
    for training_seed in seeds:
        model_dir = matched_results_dir / "models" / f"ppo_seed_{training_seed}"
        model_config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        if model_config.get("scenario_id") != REFERENCE_SCENARIO_ID or model_config.get("horizon") != 8:
            raise ValueError(f"Training seed {training_seed} used a different scenario or horizon.")
        model_profiles = tuple(tuple(profile) for profile in model_config.get("initial_profiles", ()))
        if model_profiles != profiles:
            raise ValueError(f"Training seed {training_seed} profile order differs from canonical order.")
        seed_bases = tuple(schedule_map[str(training_seed)])
        policy_pairs = model_config.get("policy_seed_pairs", ())
        if tuple(pair[0] for pair in policy_pairs) != seed_bases:
            raise ValueError(f"Training seed {training_seed} evaluation/policy schedules do not align.")
        checkpoint_path = Path(model_config["ppo_model_path"])
        if not checkpoint_path.is_absolute():
            checkpoint_path = Path.cwd() / checkpoint_path
        training_config_path = checkpoint_path.parent / "config.json"
        training_manifest_path = checkpoint_path.parent / "environment_manifest.json"
        training_config = json.loads(training_config_path.read_text(encoding="utf-8"))
        training_manifest = json.loads(training_manifest_path.read_text(encoding="utf-8"))
        if (
            training_config.get("ppo_seed") != training_seed
            or training_config.get("scenario_id") != REFERENCE_SCENARIO_ID
            or training_config.get("horizon") != 8
            or training_config.get("gamma") != 1.0
            or training_manifest.get("reward_specification", {}).get("objective") != "normalized_resistance_burden"
            or training_manifest.get("action_masking") is not True
        ):
            raise ValueError(f"Training seed {training_seed} checkpoint contract is not the expected baseline.")
        source_provenance.append({
            "training_seed": training_seed,
            "checkpoint": str(checkpoint_path),
            "checkpoint_sha256": _sha256(checkpoint_path),
            "training_config_sha256": _sha256(training_config_path),
            "training_manifest_sha256": _sha256(training_manifest_path),
            "training_timesteps": training_config.get("total_timesteps"),
        })

        with (model_dir / "raw_results.csv").open(encoding="utf-8", newline="") as result_file:
            saved_results = list(csv.DictReader(result_file))
        trajectories = json.loads((model_dir / "raw_trajectories.json").read_text(encoding="utf-8"))
        if len(saved_results) != 640 or len(trajectories) != 640:
            raise ValueError(f"Training seed {training_seed} is missing matched cases or trajectories.")
        results_by_case = {row["case_id"]: row for row in saved_results}
        if len(results_by_case) != 640:
            raise ValueError(f"Training seed {training_seed} has duplicate case IDs.")
        for schedule_index, seed_base in enumerate(seed_bases):
            for profile_index, profile in enumerate(profiles):
                case_id = f"seed_{seed_base}_profile_{profile_index:03d}"
                result = results_by_case.get(case_id)
                if result is None:
                    raise ValueError(f"Missing matched profile case: {case_id}")
                trajectory = next((item for item in trajectories if item.get("case_id") == case_id), None)
                if trajectory is None:
                    raise ValueError(f"Missing stored trajectory: {case_id}")
                if json.loads(result["initial_resistance_profile"]) != list(profile):
                    raise ValueError(f"Saved result profile differs from expected profile: {case_id}")
                if trajectory.get("initial_state") != "".join("R" if bit else "S" for bit in profile):
                    raise ValueError(f"Saved trajectory profile differs from expected profile: {case_id}")
                policy_metrics = {}
                scored = {}
                for policy_name in ("ppo", "greedy"):
                    episode = trajectory[policy_name]
                    expected_episode_seed = seed_base + profile_index
                    expected_policy_seed = policy_pairs[schedule_index][1] + profile_index
                    if episode.get("environment_seed") != expected_episode_seed or episode.get("policy_seed") != expected_policy_seed:
                        raise ValueError(f"Seed mismatch in {case_id} for {policy_name}.")
                    if tuple(episode.get("initial_resistance_profile", ())) != profile:
                        raise ValueError(f"Initial trajectory profile mismatch in {case_id}.")
                    scored[policy_name] = score_episode_objectives(episode, horizon=8)
                    policy_metrics[policy_name] = _episode_metrics(episode)
                    prefix = f"{policy_name}_"
                    source_metric_names = {
                        "cumulative_resistance_burden": "cumulative_resistance_burden",
                        "final_resistant_antibiotics": "final_resistant_antibiotics",
                        "resistance_emergence_events": "resistance_emergence_events",
                        "resistance_emergence_rate": "resistance_emergence_rate",
                        "treatment_effectiveness_rate": "treatment_effectiveness_rate",
                        "treatment_steps": "episode_length",
                        "cumulative_reward": "cumulative_reward",
                    }
                    for field, source_field in source_metric_names.items():
                        _validate_close(
                            policy_metrics[policy_name][field],
                            result.get(prefix + source_field),
                            prefix + source_field,
                            case_id,
                        )
                    _validate_close(
                        policy_metrics[policy_name]["cumulative_resistance_burden"],
                        result.get(prefix + "cumulative_resistance_burden"),
                        prefix + "cumulative_resistance_burden", case_id,
                    )
                if trajectory.get("evaluation_seed") != seed_base + profile_index:
                    raise ValueError(f"Paired evaluation seed mismatch in {case_id}.")
                if trajectory["ppo"]["initial_resistance_profile"] != trajectory["greedy"]["initial_resistance_profile"]:
                    raise ValueError(f"PPO/Greedy initial profiles are not paired in {case_id}.")
                if trajectory["ppo"]["environment_seed"] != trajectory["greedy"]["environment_seed"]:
                    raise ValueError(f"PPO/Greedy reset seeds are not paired in {case_id}.")
                case = {
                    "training_seed": training_seed,
                    "evaluation_schedule_index": schedule_index,
                    "evaluation_seed_base": seed_base,
                    "profile_index": profile_index,
                    "case_id": case_id,
                    "initial_profile": "".join("R" if bit else "S" for bit in profile),
                    "initial_resistance_profile": list(profile),
                    "evaluation_seed": seed_base + profile_index,
                    "ppo_policy_seed": policy_pairs[schedule_index][1] + profile_index,
                    "greedy_policy_seed": policy_pairs[schedule_index][1] + profile_index,
                }
                for policy_name in ("ppo", "greedy"):
                    for objective in OBJECTIVES:
                        case[f"{policy_name}_{objective}_return"] = scored[policy_name][objective]
                    for metric, value in policy_metrics[policy_name].items():
                        case[f"{policy_name}_{metric}"] = value
                case["ppo_minus_greedy_A_return"] = case["ppo_A_normalized_burden_return"] - case["greedy_A_normalized_burden_return"]
                case["ppo_minus_greedy_B_return"] = case["ppo_B_unnormalized_burden_return"] - case["greedy_B_unnormalized_burden_return"]
                case["ppo_minus_greedy_C_return"] = case["ppo_C_emergence_only_return"] - case["greedy_C_emergence_only_return"]
                case["ppo_minus_greedy_D_return"] = case["ppo_D_terminal_resistance_return"] - case["greedy_D_terminal_resistance_return"]
                case["greedy_minus_ppo_burden"] = case["greedy_cumulative_resistance_burden"] - case["ppo_cumulative_resistance_burden"]
                case["greedy_minus_ppo_final_resistant"] = case["greedy_final_resistant_antibiotics"] - case["ppo_final_resistant_antibiotics"]
                case["source_scenario_id"] = REFERENCE_SCENARIO_ID
                case_rows.append(case)
                trajectory_rows.append({
                    "training_seed": training_seed,
                    "evaluation_schedule_index": schedule_index,
                    "evaluation_seed_base": seed_base,
                    "profile_index": profile_index,
                    "case_id": case_id,
                    "initial_profile": "".join("R" if bit else "S" for bit in profile),
                    "objective_scores": {
                        policy: dict(scored[policy])
                        for policy in ("ppo", "greedy")
                    },
                    "source_trajectories": trajectory,
                })
    if len(case_rows) != 3200 or len({row["case_id"] + f":{row['training_seed']}" for row in case_rows}) != 3200:
        raise RuntimeError("Expected exactly 3,200 unique paired cases across the frozen ensemble.")
    return source_config, case_rows, trajectory_rows, source_provenance


def _winner(delta: float) -> str:
    if delta > TIE_TOLERANCE:
        return "PPO"
    if delta < -TIE_TOLERANCE:
        return "Greedy"
    return "tied"


def _profile_means(case_rows: list[dict]) -> list[dict]:
    rows = []
    for profile_index in range(128):
        selected = [row for row in case_rows if row["profile_index"] == profile_index]
        profile = selected[0]["initial_profile"]
        for objective in OBJECTIVES:
            ppo_values = [row[f"ppo_{objective}_return"] for row in selected]
            greedy_values = [row[f"greedy_{objective}_return"] for row in selected]
            ppo_score, greedy_score = mean(ppo_values), mean(greedy_values)
            delta = ppo_score - greedy_score
            rows.append({
                "objective": objective,
                "profile_index": profile_index,
                "initial_profile": profile,
                "paired_case_count": len(selected),
                "ppo_mean_return": ppo_score,
                "greedy_mean_return": greedy_score,
                "ppo_minus_greedy_return": delta,
                "return_winner": _winner(delta),
                "ppo_mean_cumulative_resistance_burden": mean(row["ppo_cumulative_resistance_burden"] for row in selected),
                "greedy_mean_cumulative_resistance_burden": mean(row["greedy_cumulative_resistance_burden"] for row in selected),
                "greedy_minus_ppo_burden": mean(row["greedy_minus_ppo_burden"] for row in selected),
                "ppo_mean_final_resistant_count": mean(row["ppo_final_resistant_antibiotics"] for row in selected),
                "greedy_mean_final_resistant_count": mean(row["greedy_final_resistant_antibiotics"] for row in selected),
                "ppo_mean_emergence_rate": _mean_defined(row["ppo_resistance_emergence_rate"] for row in selected),
                "greedy_mean_emergence_rate": _mean_defined(row["greedy_resistance_emergence_rate"] for row in selected),
            })
    return rows


def _mean_defined(values) -> float | None:
    defined = [float(value) for value in values if value is not None]
    return mean(defined) if defined else None


def _summarize(case_rows: list[dict], profile_rows: list[dict]) -> dict:
    objectives = {}
    for objective in OBJECTIVES:
        deltas = [row[f"ppo_minus_greedy_{objective.split('_')[0]}_return"] for row in case_rows]
        profile_objectives = [row for row in profile_rows if row["objective"] == objective]
        profile_deltas = [row["ppo_minus_greedy_return"] for row in profile_objectives]
        objectives[objective] = {
            "policy_evaluation_type": "re-scoring of fixed policy trajectories; no alternative-objective training",
            "ppo_mean_return": mean(row[f"ppo_{objective}_return"] for row in case_rows),
            "greedy_mean_return": mean(row[f"greedy_{objective}_return"] for row in case_rows),
            "mean_paired_ppo_minus_greedy_return": mean(deltas),
            "median_profile_mean_ppo_minus_greedy_return": median(profile_deltas),
            "profiles_ppo_higher_return": sum(row["return_winner"] == "PPO" for row in profile_objectives),
            "profiles_tied": sum(row["return_winner"] == "tied" for row in profile_objectives),
            "profiles_greedy_higher_return": sum(row["return_winner"] == "Greedy" for row in profile_objectives),
            "matched_case_count": len(case_rows),
            "profile_count": len(profile_objectives),
            "cases_per_profile": 25,
        }
    burden_ppo = mean(row["ppo_cumulative_resistance_burden"] for row in case_rows)
    burden_greedy = mean(row["greedy_cumulative_resistance_burden"] for row in case_rows)
    primary_burden_difference = burden_greedy - burden_ppo
    for objective in OBJECTIVES:
        objectives[objective]["existing_project_metrics"] = {
            "ppo_mean_cumulative_resistance_burden": burden_ppo,
            "greedy_mean_cumulative_resistance_burden": burden_greedy,
            "greedy_minus_ppo_burden": primary_burden_difference,
            "ppo_mean_final_resistant_count": mean(row["ppo_final_resistant_antibiotics"] for row in case_rows),
            "greedy_mean_final_resistant_count": mean(row["greedy_final_resistant_antibiotics"] for row in case_rows),
            "greedy_minus_ppo_final_resistant_count": mean(row["greedy_minus_ppo_final_resistant"] for row in case_rows),
            "ppo_mean_resistance_emergence_rate": _mean_defined(row["ppo_resistance_emergence_rate"] for row in case_rows),
            "greedy_mean_resistance_emergence_rate": _mean_defined(row["greedy_resistance_emergence_rate"] for row in case_rows),
            "ppo_mean_effectiveness_rate": _mean_defined(row["ppo_treatment_effectiveness_rate"] for row in case_rows),
            "greedy_mean_effectiveness_rate": _mean_defined(row["greedy_treatment_effectiveness_rate"] for row in case_rows),
            "ppo_mean_action_count_proxy": mean(row["ppo_cumulative_antibiotic_exposure"] for row in case_rows),
            "greedy_mean_action_count_proxy": mean(row["greedy_cumulative_antibiotic_exposure"] for row in case_rows),
        }
    baseline_winners = {row["profile_index"]: row["return_winner"] for row in profile_rows if row["objective"] == OBJECTIVES[0]}
    alignment = []
    for objective in OBJECTIVES:
        current = {row["profile_index"]: row["return_winner"] for row in profile_rows if row["objective"] == objective}
        counts = Counter((baseline_winners[index], current[index]) for index in range(128))
        burden_winner_by_profile = {
            row["profile_index"]: _winner(row["greedy_minus_ppo_burden"])
            for row in profile_rows if row["objective"] == OBJECTIVES[0]
        }
        final_resistance_winner_by_profile = {
            row["profile_index"]: _winner(
                row["greedy_mean_final_resistant_count"] - row["ppo_mean_final_resistant_count"]
            )
            for row in profile_objectives
        }
        objective_burden_disagreement = sum(current[index] != burden_winner_by_profile[index] for index in range(128))
        alignment.append({
            "objective": objective,
            "baseline_objective": OBJECTIVES[0],
            "profiles_same_winner_as_baseline": sum(baseline_winners[index] == current[index] for index in range(128)),
            "profiles_any_winner_category_changed": sum(baseline_winners[index] != current[index] for index in range(128)),
            "profiles_decisive_ppo_vs_greedy_reversal": sum(
                baseline_winners[index] in {"PPO", "Greedy"}
                and current[index] in {"PPO", "Greedy"}
                and baseline_winners[index] != current[index]
                for index in range(128)
            ),
            "baseline_tied_alternative_decisive": sum(baseline_winners[index] == "tied" and current[index] != "tied" for index in range(128)),
            "baseline_decisive_alternative_tied": sum(baseline_winners[index] != "tied" and current[index] == "tied" for index in range(128)),
            "profiles_alternative_winner_disagrees_with_burden_winner": objective_burden_disagreement,
            "profiles_objective_winner_disagrees_with_final_resistance_winner": sum(
                current[index] != final_resistance_winner_by_profile[index] for index in range(128)
            ),
            "baseline_to_objective_winner_transitions": {
                f"{baseline}>{winner}": count for (baseline, winner), count in sorted(counts.items())
            },
        })
    return {
        "objective_results": objectives,
        "objective_alignment": alignment,
        "primary_burden_direction": "Greedy minus PPO; positive means PPO lower burden",
        "return_difference_direction": "PPO minus Greedy; positive means PPO higher objective return",
        "tie_tolerance": TIE_TOLERANCE,
        "inference": "descriptive only; no confidence intervals or significance tests; profile means aggregate 25 checkpoint/schedule cases per profile",
    }


def _per_hierarchy(case_rows: list[dict]) -> dict:
    result = {}
    seed_values = sorted({row["training_seed"] for row in case_rows})
    for seed in seed_values:
        result[str(seed)] = {}
        for schedule in sorted({row["evaluation_seed_base"] for row in case_rows if row["training_seed"] == seed}):
            selected = [row for row in case_rows if row["training_seed"] == seed and row["evaluation_seed_base"] == schedule]
            result[str(seed)][str(schedule)] = {
                objective: {
                    "ppo_mean_return": mean(row[f"ppo_{objective}_return"] for row in selected),
                    "greedy_mean_return": mean(row[f"greedy_{objective}_return"] for row in selected),
                    "mean_paired_ppo_minus_greedy_return": mean(row[f"ppo_minus_greedy_{objective.split('_')[0]}_return"] for row in selected),
                    "case_count": len(selected),
                } for objective in OBJECTIVES
            }
    return result


def _examples(trajectory_rows: list[dict]) -> dict:
    ordered = sorted(trajectory_rows, key=lambda item: (
        item["training_seed"], item["evaluation_seed_base"], item["profile_index"],
    ))
    examples = {"transient_increase_then_decrease": None, "persistent_resistance": None, "unchanged_resistance_state": None, "same_count_different_identity_pair": None}
    for item in ordered:
        for policy in ("ppo", "greedy"):
            episode = item["source_trajectories"][policy]
            counts = [sum(episode["initial_resistance_profile"])] + [sum(int(value) for value in step["next_observation"][:7]) for step in episode["steps"]]
            base = {
                "training_seed": item["training_seed"], "case_id": item["case_id"],
                "initial_profile": item["source_trajectories"]["initial_state"],
                "policy": policy, "resistant_count_path": counts,
            }
            if examples["transient_increase_then_decrease"] is None:
                for index in range(1, len(counts)):
                    if counts[index] > counts[index - 1] and any(later < counts[index] for later in counts[index + 1:]):
                        step = episode["steps"][index - 1]
                        examples["transient_increase_then_decrease"] = {
                            **base, "step": index - 1, "action": step["info"]["antibiotic"],
                            "outcome": step["info"]["transition_status"],
                            "count_before": counts[index - 1], "count_after": counts[index],
                            "later_count": next(value for value in counts[index + 1:] if value < counts[index]),
                        }
                        break
            if examples["persistent_resistance"] is None:
                for index in range(1, len(counts)):
                    if counts[index] > counts[index - 1] and all(value >= counts[index] for value in counts[index + 1:]):
                        examples["persistent_resistance"] = {
                            **base, "first_increase_step": index - 1,
                            "count_before": counts[index - 1], "count_after": counts[index],
                            "final_count": counts[-1],
                        }
                        break
            if examples["unchanged_resistance_state"] is None:
                for index, step in enumerate(episode["steps"]):
                    before = tuple(int(value) for value in step["observation"][:7])
                    after = tuple(int(value) for value in step["next_observation"][:7])
                    if before == after and sum(before) > 0:
                        examples["unchanged_resistance_state"] = {
                            **base, "step": index, "action": step["info"]["antibiotic"],
                            "outcome": step["info"]["transition_status"],
                            "resistant_count": sum(before),
                            "A_reward_at_step": step["reward"],
                            "C_reward_at_step": 0,
                        }
                        break
        if all(examples[name] is not None for name in examples if name != "same_count_different_identity_pair"):
            break
    by_case = {item["case_id"]: item for item in ordered}
    for item in ordered:
        ppo_episode = item["source_trajectories"]["ppo"]
        greedy_episode = item["source_trajectories"]["greedy"]
        if not ppo_episode["steps"] or not greedy_episode["steps"]:
            continue
        ppo_next = tuple(int(value) for value in ppo_episode["steps"][0]["next_observation"][:7])
        greedy_next = tuple(int(value) for value in greedy_episode["steps"][0]["next_observation"][:7])
        if sum(ppo_next) == sum(greedy_next) and ppo_next != greedy_next:
            examples["same_count_different_identity_pair"] = {
                "training_seed": item["training_seed"], "case_id": item["case_id"],
                "initial_profile": item["initial_profile"],
                "ppo_first_next_profile": "".join("R" if value else "S" for value in ppo_next),
                "greedy_first_next_profile": "".join("R" if value else "S" for value in greedy_next),
                "shared_first_step_resistance_count": sum(ppo_next),
                "ppo_total_burden": -item["objective_scores"]["ppo"]["A_normalized_burden"],
                "greedy_total_burden": -item["objective_scores"]["greedy"]["A_normalized_burden"],
                "interpretation": "illustrative matched outcomes only; action-specific stochastic transitions prevent causal attribution",
            }
            break
    return examples


def _project_objective_mapping() -> list[dict]:
    return [
        {"project_objective": "Treat effectively", "current_representation": "Hard feasibility/action-mask constraint: select a currently susceptible antibiotic when one exists.", "independent_reward_term": False, "limitation": "Susceptibility is not clinical cure or treatment success."},
        {"project_objective": "Avoid increasing resistance", "current_representation": "Indirectly penalized by cumulative post-transition resistance burden; measured separately by resistance-emergence events/rate. Condition C directly scores positive increases only.", "independent_reward_term": False, "limitation": "Current reward also penalizes persistent existing resistance at every charged step; emergence is not its own current reward term."},
        {"project_objective": "Preserve future effective antibiotics", "current_representation": "Implicitly represented through the resistance state, identity-specific transitions, and resistance burden; final susceptible count is 7 minus final resistance count.", "independent_reward_term": False, "limitation": "Not independently optimized as a separate option-value reward."},
        {"project_objective": "Avoid unnecessary antibiotic exposure", "current_representation": "Not modeled as an objective; action count is reported as an evaluation-only proxy.", "independent_reward_term": False, "limitation": "No treatment-need or recovery/clearance state and no no-treatment/stop action; unnecessary exposure cannot be identified or sensitivity-tested without changing the objective/environment."},
    ]


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty table: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, allow_nan=False) if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def run_reward_objective_sensitivity(matched_results_dir, output_dir):
    matched_results_dir, output_dir = Path(matched_results_dir), Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Reward sensitivity output directory is not empty: {output_dir}")
    source_config, case_rows, trajectory_rows, provenance = _load_cases(matched_results_dir)
    profile_rows = _profile_means(case_rows)
    summary = _summarize(case_rows, profile_rows)
    hierarchy = _per_hierarchy(case_rows)
    examples = _examples(trajectory_rows)
    objective_metric_rows = []
    for objective in OBJECTIVES:
        result = summary["objective_results"][objective]
        metrics = result["existing_project_metrics"]
        alignment = next(row for row in summary["objective_alignment"] if row["objective"] == objective)
        objective_metric_rows.append({
            "objective": objective,
            "ppo_mean_return": result["ppo_mean_return"],
            "greedy_mean_return": result["greedy_mean_return"],
            "mean_paired_ppo_minus_greedy_return": result["mean_paired_ppo_minus_greedy_return"],
            "median_profile_mean_ppo_minus_greedy_return": result["median_profile_mean_ppo_minus_greedy_return"],
            "profiles_ppo_higher_return": result["profiles_ppo_higher_return"],
            "profiles_tied": result["profiles_tied"],
            "profiles_greedy_higher_return": result["profiles_greedy_higher_return"],
            "ppo_mean_cumulative_resistance_burden": metrics["ppo_mean_cumulative_resistance_burden"],
            "greedy_mean_cumulative_resistance_burden": metrics["greedy_mean_cumulative_resistance_burden"],
            "greedy_minus_ppo_cumulative_resistance_burden": metrics["greedy_minus_ppo_burden"],
            "ppo_mean_final_resistant_count": metrics["ppo_mean_final_resistant_count"],
            "greedy_mean_final_resistant_count": metrics["greedy_mean_final_resistant_count"],
            "ppo_mean_resistance_emergence_rate": metrics["ppo_mean_resistance_emergence_rate"],
            "greedy_mean_resistance_emergence_rate": metrics["greedy_mean_resistance_emergence_rate"],
            "ppo_mean_effectiveness_rate": metrics["ppo_mean_effectiveness_rate"],
            "greedy_mean_effectiveness_rate": metrics["greedy_mean_effectiveness_rate"],
            "profiles_any_winner_category_changed_from_A": alignment["profiles_any_winner_category_changed"],
            "profiles_decisive_winner_reversed_from_A": alignment["profiles_decisive_ppo_vs_greedy_reversal"],
            "profiles_objective_winner_disagrees_with_final_resistance_winner": alignment["profiles_objective_winner_disagrees_with_final_resistance_winner"],
        })
    alignment_rows = summary["objective_alignment"]
    compatibility = {
        "current_environment_contract": {
            "transition_condition": REFERENCE_SCENARIO_ID,
            "horizon": 8,
            "gamma": 1.0,
            "action_ids": list(ANTIBIOTICS),
            "effectiveness": "susceptibility-based hard feasibility/action-mask constraint, not a reward term",
            "current_reward": "negative normalized post-transition resistant-antibiotic count, with existing all-resistant terminal-tail accounting",
            "reward_configuration": source_config.get("reward_configuration"),
        },
        "objectives": {
            objective: {
                **OBJECTIVE_DEFINITIONS[objective],
                "can_score_existing_trajectories": True,
                "evaluation_type": "policy evaluation under an alternative objective" if objective in {"B_unnormalized_burden", "C_emergence_only", "D_terminal_resistance"} else "canonical baseline reward replay",
                "requires_retraining_to_test_policy_learning_response": objective != "A_normalized_burden",
            } for objective in OBJECTIVES
        },
        "fixed_evaluation_design": {
            "source": str(matched_results_dir),
            "scenario_id": REFERENCE_SCENARIO_ID,
            "training_seeds": sorted({item["training_seed"] for item in provenance}),
            "evaluation_schedules_per_checkpoint": 5,
            "canonical_initial_profiles": 128,
            "matched_cases": len(case_rows),
            "no_policy_environment_mask_horizon_or_transition_changes": True,
            "no_retraining": True,
        },
        "unnecessary_exposure": {
            "modeled": False,
            "reason": "no treatment-need state, recovery/clearance state, or no-treatment/stop action",
            "action_count": "evaluation-only proxy; not used as a reward or alternative objective",
        },
        "project_objectives": _project_objective_mapping(),
        "source_checkpoint_provenance": provenance,
    }
    if len(case_rows) != 3200:
        raise RuntimeError("Expected five checkpoints x five schedules x 128 profiles = 3,200 cases.")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "source_matched_results_dir": str(matched_results_dir),
        "source_config_sha256": _sha256(matched_results_dir / "config.json"),
        "transition_scenario": REFERENCE_SCENARIO_ID,
        "horizon": 8,
        "gamma": 1.0,
        "training_seeds": [item["training_seed"] for item in provenance],
        "evaluation_seed_bases_by_training_seed": source_config["evaluation_seed_bases_by_training_seed"],
        "initial_profiles": source_config["initial_profiles"],
        "objective_definitions": OBJECTIVE_DEFINITIONS,
        "score_tie_tolerance": TIE_TOLERANCE,
        "resampling_or_significance_tests": "none; descriptive profile/checkpoint/schedule hierarchy preserved",
        "no_retraining_or_source_mutation": True,
        "source_checkpoint_provenance": provenance,
    }
    (output_dir / "compatibility.json").write_text(json.dumps(compatibility, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "compatibility.md").write_text(_compatibility_markdown(compatibility), encoding="utf-8")
    (output_dir / "config.json").write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps({
        **summary,
        "hierarchy": hierarchy,
        "examples": examples,
        "case_count": len(case_rows),
        "training_checkpoint_count": 5,
        "evaluation_schedules_per_checkpoint": 5,
        "profiles_per_schedule": 128,
        "paired_inference_unit": "descriptive; profile means aggregate 25 trajectories per policy/profile; no tests or confidence intervals",
    }, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(output_dir / "raw_results.csv", case_rows)
    _write_csv(output_dir / "paired_profile_means.csv", profile_rows)
    _write_csv(output_dir / "objective_alignment.csv", alignment_rows)
    _write_csv(output_dir / "objective_metric_comparison.csv", objective_metric_rows)
    (output_dir / "trajectory_objective_examples.json").write_text(json.dumps(examples, indent=2, allow_nan=False), encoding="utf-8")
    with (output_dir / "raw_trajectories.jsonl").open("w", encoding="utf-8") as stream:
        for trajectory in trajectory_rows:
            stream.write(json.dumps(trajectory, allow_nan=False) + "\n")
    return compatibility, summary, profile_rows, case_rows, trajectory_rows, hierarchy, examples


def _compatibility_markdown(compatibility: dict) -> str:
    lines = [
        "# Reward Objective Compatibility", "",
        "All four listed scores are computable from the frozen `REF_UNIFORM_SUPPORTED` trajectories. B, C, and D are evaluation-only re-scores; they do not test whether PPO would learn the same or a different policy if trained under those rewards.", "",
        "| Condition | Objective class | Existing trajectories scoreable | Alternative-reward training tested |", "|---|---|---:|---:|",
    ]
    for name, detail in compatibility["objectives"].items():
        lines.append(f"| `{name}` | {detail['class']} | yes | no |")
    lines.extend([
        "", "All cases remain under the existing horizon, action mask, transition model, profile order, and evaluation schedule. No objective condition changes policy actions or environmental transitions.",
        "", "Effectiveness is constrained by the existing susceptibility mask, not added as a reward bonus. Resistance emergence, final resistance, and action count are evaluation metrics. Unnecessary exposure is not modeled: there is no treatment-need or clearance state and no no-treatment action. The action-count metric is not used as a proxy reward.",
        "", "A and B have the same trajectory ordering and mathematical optimizer under fixed horizon and gamma=1; B is exactly 7 times A. Training-time optimization effects from that rescaling cannot be established without retraining.",
    ])
    return "\n".join(lines) + "\n"


def _write_plots(case_rows, profile_rows, output_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    labels = ["A: normalized", "B / 7: unnormalized", "C: emergence", "D: terminal"]
    objectives = list(OBJECTIVES)
    ppo_means = []
    greedy_means = []
    for objective in objectives:
        scale = 7 if objective == "B_unnormalized_burden" else 1
        ppo_means.append(mean(row[f"ppo_{objective}_return"] / scale for row in case_rows))
        greedy_means.append(mean(row[f"greedy_{objective}_return"] / scale for row in case_rows))
    figure, axis = plt.subplots(figsize=(9, 4.5))
    positions = np.arange(len(objectives))
    width = .36
    axis.bar(positions - width / 2, ppo_means, width, label="PPO", color="#347c9a")
    axis.bar(positions + width / 2, greedy_means, width, label="Greedy", color="#c26c4a")
    axis.set(xticks=positions, xticklabels=labels, ylabel="Mean return (B divided by 7 for display)", title="Frozen policies re-scored under each objective")
    axis.legend()
    figure.tight_layout()
    path = output_dir / "mean_objective_return.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    saved.append(str(path))

    figure, axis = plt.subplots(figsize=(9, 4.5))
    profile_groups = {objective: [row for row in profile_rows if row["objective"] == objective] for objective in objectives}
    for index, objective in enumerate(objectives):
        scale = 7 if objective == "B_unnormalized_burden" else 1
        values = [row["ppo_minus_greedy_return"] / scale for row in profile_groups[objective]]
        axis.scatter(np.full(len(values), index), values, alpha=.42, s=16)
        axis.plot([index - .18, index + .18], [mean(values), mean(values)], color="#222222", linewidth=2)
    axis.axhline(0, color="#777777", linewidth=.8)
    axis.set(xticks=positions, xticklabels=labels, ylabel="Profile mean PPO - Greedy return (B / 7)", title="Profile-level paired objective differences")
    figure.tight_layout()
    path = output_dir / "profile_paired_return_differences.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    saved.append(str(path))

    alignments = []
    for objective in objectives:
        by_profile = {row["profile_index"]: row["return_winner"] for row in profile_groups[objective]}
        baseline = {row["profile_index"]: row["return_winner"] for row in profile_groups[OBJECTIVES[0]]}
        alignments.append(sum(by_profile[index] != baseline[index] for index in range(128)))
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.bar(positions, alignments, color=["#4b8e70", "#4b8e70", "#bb8752", "#a65f55"])
    axis.set(xticks=positions, xticklabels=labels, ylabel="Profiles with changed winner/tie category", ylim=(0, 128), title="Profile winner changes relative to current objective A")
    figure.tight_layout()
    path = output_dir / "profile_winner_changes.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    saved.append(str(path))

    figure, axis = plt.subplots(figsize=(7, 5))
    for policy, color in (("ppo", "#347c9a"), ("greedy", "#c26c4a")):
        axis.scatter(
            [row[f"{policy}_cumulative_resistance_burden"] for row in case_rows],
            [row[f"{policy}_final_resistant_antibiotics"] for row in case_rows],
            alpha=.18, s=10, color=color, label=policy.upper(),
        )
    axis.set(xlabel="Cumulative normalized resistance burden", ylabel="Final resistant antibiotics", title="Trajectory burden versus terminal resistance")
    axis.legend()
    figure.tight_layout()
    path = output_dir / "burden_vs_final_resistance.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    saved.append(str(path))
    return saved


def _render_report(compatibility, summary, case_rows, profile_rows, examples, hierarchy, plots):
    objective_results = summary["objective_results"]
    alignment = {row["objective"]: row for row in summary["objective_alignment"]}
    lines = [
        "# Reward / Objective Sensitivity", "",
        "This is policy evaluation under alternative objective scorings of fixed `REF_UNIFORM_SUPPORTED` trajectories. No PPO was retrained; this does not establish training robustness to another reward.", "",
        "## Reward / Objective Definitions", "",
        "| Condition | Reward / score | Classification |", "|---|---|---|",
    ]
    for objective in OBJECTIVES:
        definition = OBJECTIVE_DEFINITIONS[objective]
        lines.append(f"| `{objective}` | {definition['formula']} | {definition['class']} |")
    lines.extend([
        "", r"A and B have identical trajectory rankings: $R_B=7R_A$ including the matching all-resistant terminal-tail convention. Fixed horizon and $\gamma=1$ make this a positive scalar rescaling of the same mathematical objective. Any optimizer differences under B would concern PPO's training process and reward scale, which this fixed-checkpoint analysis cannot test.",
        "C and D are genuinely different objectives. C penalizes only positive increases and gives no penalty to already-existing resistance or credit for reductions. D sees only final resistant count and ignores intermediate burden.",
        "", "## Compatibility", "",
        "All four conditions were re-scored from the same frozen policy trajectories, under the unchanged mask, transition model, horizon, canonical profiles, and evaluation schedules. B-D are policy evaluation under an alternative objective, not alternative-reward PPO training. The existing checkpoints cannot answer what policy would have been learned under C or D; no retraining was undertaken.",
        "", "The source matched trajectories were checked against the current baseline reward and secondary metrics. All 3,200 PPO/Greedy cases use `REF_UNIFORM_SUPPORTED`; no Step 7 transition condition was mixed into this analysis. See `compatibility.md/json` for the verified contracts and source hashes.",
        "", "## PPO vs Greedy", "",
        r"Objective returns use $\Delta R=R_{PPO}-R_{Greedy}$; positive favors PPO. Profile winners compare mean policy returns over 25 matched trajectories for each initial profile (five checkpoints × five schedules). No trajectory-level inferential treatment is used.",
        r"", r"| Objective | PPO mean return | Greedy mean return | Mean paired $\Delta R$ | Median profile $\Delta R$ | Profiles PPO higher / tie / Greedy higher |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for objective in OBJECTIVES:
        item = objective_results[objective]
        lines.append(
            f"| `{objective}` | {item['ppo_mean_return']:.6f} | {item['greedy_mean_return']:.6f} | {item['mean_paired_ppo_minus_greedy_return']:+.6f} | "
            f"{item['median_profile_mean_ppo_minus_greedy_return']:+.6f} | {item['profiles_ppo_higher_return']} / {item['profiles_tied']} / {item['profiles_greedy_higher_return']} |"
        )
    lines.extend([
        "", "### Existing Project Metrics", "",
        "These metrics are unchanged because the trajectories and policies are unchanged; they are repeated here to prevent a new score from replacing the project's primary burden measure.",
        "", "| Objective scoring | PPO / Greedy burden | PPO / Greedy final resistant count | PPO / Greedy emergence rate | PPO / Greedy effectiveness | PPO / Greedy action-count proxy |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for objective in OBJECTIVES:
        metrics = objective_results[objective]["existing_project_metrics"]
        lines.append(
            f"| `{objective}` | {metrics['ppo_mean_cumulative_resistance_burden']:.4f} / {metrics['greedy_mean_cumulative_resistance_burden']:.4f} | "
            f"{metrics['ppo_mean_final_resistant_count']:.4f} / {metrics['greedy_mean_final_resistant_count']:.4f} | "
            f"{metrics['ppo_mean_resistance_emergence_rate']:.4f} / {metrics['greedy_mean_resistance_emergence_rate']:.4f} | "
            f"{metrics['ppo_mean_effectiveness_rate']:.4f} / {metrics['greedy_mean_effectiveness_rate']:.4f} | "
            f"{metrics['ppo_mean_action_count_proxy']:.4f} / {metrics['greedy_mean_action_count_proxy']:.4f} |"
        )
    lines.extend([
        "", "## Primary Resistance-Burden Alignment", "",
        r"For this table, the primary burden direction is $\Delta B=B_{Greedy}-B_{PPO}$; positive favors PPO. Return winners for A-D are based on higher objective return.",
        r"", r"| Objective | Mean $\Delta B$ | Profiles same winner/tie as A | Any winner/tie category changed | Decisive reversals | Winner disagrees with burden | Winner disagrees with final resistance |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for objective in OBJECTIVES:
        row = alignment[objective]
        burden = objective_results[objective]["existing_project_metrics"]["greedy_minus_ppo_burden"]
        lines.append(
            f"| `{objective}` | {burden:+.6f} | {row['profiles_same_winner_as_baseline']} / 128 | "
            f"{row['profiles_any_winner_category_changed']} | {row['profiles_decisive_ppo_vs_greedy_reversal']} | "
            f"{row['profiles_alternative_winner_disagrees_with_burden_winner']} / 128 | "
            f"{row['profiles_objective_winner_disagrees_with_final_resistance_winner']} / 128 |"
        )
    lines.extend([
        "", "**A vs B:** exact positive scaling, so every profile winner/tie is unchanged. C/D preserve or alter the descriptive profile-level PPO/Greedy ranking as shown; this is not evidence of which objective is correct.",
        "", "## Profile-Level Changes", "",
        "`objective_alignment.csv` gives the full baseline-to-alternative winner/tie transition counts. `paired_profile_means.csv` retains the 128-profile means and the 25 contributing checkpoint/schedule cases per policy/profile.",
        "", "## Actual Trajectory Examples", "",
    ])
    example_labels = {
        "transient_increase_then_decrease": "Transient resistance increase later decreases",
        "persistent_resistance": "Resistance increase remains through the final state",
        "unchanged_resistance_state": "Unchanged resistance state with existing burden",
        "same_count_different_identity_pair": "Same count, different resistance identities in a matched pair",
    }
    for key, title in example_labels.items():
        lines.extend([f"### {title}", ""])
        example = examples.get(key)
        if example is None:
            lines.append("No qualifying recorded example found.")
        else:
            lines.append(json.dumps(example, sort_keys=True))
            if key == "same_count_different_identity_pair":
                lines.append("This pair is descriptive, not a causal counterfactual: transition outcomes depend on action-specific candidate sets and sampled transitions.")
        lines.append("")
    lines.extend([
        "The current burden score charges each post-transition resistance count across the horizon (with the existing all-resistant persistence tail). A transient increase is charged while present; later sensitivity does not erase earlier accumulated burden. Persistent resistance continues to be charged. An unchanged state with existing resistance also incurs the current burden at that step. Identity matters only through the state-dependent future transitions; equal resistance counts receive equal immediate burden, and the reward has no separate option-value bonus.",
        "C instead charges only positive count increases, so unchanged or already-existing resistance yields zero emergence penalty. D ignores transient changes when they do not affect the final state. Neither is an independently validated utility.",
        "", "## Project-Objective Mapping", "",
        "| Stated objective | Current representation |", "|---|---|",
    ])
    for item in compatibility["project_objectives"]:
        lines.append(f"| {item['project_objective']} | {item['current_representation']} {item['limitation']} |")
    lines.extend([
        "", "## Limitations", "",
        "- Alternative evaluation does not demonstrate alternative-reward training robustness. A controlled training comparison under B, C, or D would require new matched checkpoint cohorts; none were trained here.",
        "- A vs B is mathematically equivalent up to positive reward scaling. This re-score cannot measure PPO optimization sensitivity to that scale.",
        "- C and D change the target; the existing PPO did not optimize them.",
        "- Unnecessary antibiotic exposure is not currently modeled. The action-count proxy cannot identify unnecessary treatment without treatment need, clearance, and a no-treatment option.",
        "- Reward scores are computational abstractions, not clinical utility functions. The existing transition assumptions remain separate and were not varied; Step 7 addresses transition-selection sensitivity.",
        "- Results are descriptive over five checkpoints, five schedules, and 128 profiles. No confidence intervals or significance tests were added; profiles/cases are not treated as independent training replicates.",
        "", "## Plots", "",
    ])
    lines.extend(f"- `{path}`" for path in plots)
    lines.extend(["", "## Artifacts", "", "`compatibility.json/md`; `config.json`; `summary.json`; `raw_results.csv`; `raw_trajectories.jsonl`; `paired_profile_means.csv`; `objective_alignment.csv`; `objective_metric_comparison.csv`; `trajectory_objective_examples.json`; `plots/."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score frozen matched PPO/Greedy trajectories under alternative objectives.")
    parser.add_argument("--matched-results-dir", default="experiments/results/ppo_greedy_matched_five_seed_final")
    parser.add_argument("--output-dir", default="experiments/results/reward_objective_sensitivity_step8_final")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    compatibility, summary, profile_rows, case_rows, trajectory_rows, hierarchy, examples = run_reward_objective_sensitivity(
        args.matched_results_dir, output_dir,
    )
    plots = _write_plots(case_rows, profile_rows, output_dir / "plots")
    (output_dir / "report.md").write_text(_render_report(
        compatibility, summary, case_rows, profile_rows, examples, hierarchy, plots,
    ), encoding="utf-8")
    print(json.dumps({"case_count": len(case_rows), "summary": summary["objective_results"], "output_dir": str(output_dir)}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()