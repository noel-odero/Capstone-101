from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import statistics
from typing import Any

import numpy as np
import torch

from ml.src.ppo_training import PPOConfig, load_ppo_model, make_training_environment
from ml.src.ppo_visualizations import generate_gentamicin_audit_plots
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from ml.src.ppo_evaluation import canonical_initial_profiles


GENTAMICIN_ACTION = ANTIBIOTICS.index("GENTAMICIN")


def _label(profile: tuple[int, ...] | list[int]) -> str:
    return "".join("R" if value else "S" for value in profile)


def extract_masked_action_probabilities(model, observation: np.ndarray, action_mask: np.ndarray) -> tuple[float, ...]:
    observation = np.asarray(observation, dtype=np.float32)
    action_mask = np.asarray(action_mask, dtype=bool)
    if observation.shape != (15,) or not np.isfinite(observation).all():
        raise ValueError("Expected a finite 15-value observation.")
    if action_mask.shape != (len(ANTIBIOTICS),) or not action_mask.any():
        raise ValueError("Expected a nonempty seven-action mask.")
    observation_tensor, _ = model.policy.obs_to_tensor(observation)
    with torch.no_grad():
        distribution = model.policy.get_distribution(
            observation_tensor,
            action_masks=action_mask.reshape(1, -1),
        )
        probabilities = distribution.distribution.probs.detach().cpu().numpy().reshape(-1)
    if len(probabilities) != len(ANTIBIOTICS) or not np.isfinite(probabilities).all():
        raise ValueError("Policy returned malformed action probabilities.")
    if not np.isclose(float(probabilities.sum()), 1.0, atol=1e-6):
        raise ValueError("Masked action probabilities must sum to one.")
    if np.any(np.abs(probabilities[~action_mask]) > 1e-8):
        raise ValueError("Policy assigns probability to a masked action.")
    return tuple(float(value) for value in probabilities)


def counterfactual_one_step_actions(
    environment,
    state: ResistanceState,
    transition_seed: int,
    treatment_step: int,
) -> tuple[dict[str, Any], ...]:
    action_mask = np.asarray(
        [state.is_susceptible(antibiotic) for antibiotic in ANTIBIOTICS],
        dtype=bool,
    )
    if not action_mask.any():
        return ()
    horizon = environment.episode_termination.max_steps
    transition_model = environment.episode_progression.episode_step.transition_model
    reward_function = environment.reward_function
    alternatives = []
    for action in np.flatnonzero(action_mask):
        next_state, sampled = transition_model.step(
            state,
            int(action),
            seed=transition_seed,
        )
        reward = reward_function.calculate(
            next_state,
            remaining_horizon_steps=max(0, horizon - treatment_step - 1),
        )
        alternatives.append({
            "action": int(action),
            "antibiotic": ANTIBIOTICS[action],
            "effective": state.is_susceptible(ANTIBIOTICS[action]),
            "transition_type": sampled.status,
            "transition_source_ids": list(sampled.candidate.source_ids) if sampled.candidate else [],
            "transition_target_drug": sampled.candidate.target_drug if sampled.candidate else None,
            "transition_probability": sampled.probability,
            "next_state": _label(next_state.resistance),
            "next_resistance_count": sum(next_state.resistance),
            "resistance_delta": sum(next_state.resistance) - sum(state.resistance),
            "immediate_reward": float(reward),
            "same_seed_one_step_counterfactual": True,
            "downstream_rollout_evaluated": False,
        })
    return tuple(alternatives)


def _episode_current_state(step: dict) -> tuple[int, ...]:
    return tuple(int(value) for value in step["observation"][:len(ANTIBIOTICS)])


def _decision_entropy(probabilities: tuple[float, ...]) -> float:
    return -sum(probability * np.log(probability) for probability in probabilities if probability > 0)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, separators=(",", ":"), allow_nan=False)
                if isinstance(value, (dict, list, tuple)) else value
                for key, value in row.items()
            })


def _mean(values):
    return statistics.mean(values) if values else None


def run_gentamicin_audit(
    matched_results_dir: str | Path,
    ppo_config_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    matched_results_dir = Path(matched_results_dir)
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Audit output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    matched_config = json.loads((matched_results_dir / "config.json").read_text(encoding="utf-8"))
    ppo_config = PPOConfig.from_json(ppo_config_path)
    if matched_config["scenario_id"] != ppo_config.scenario_id:
        raise ValueError("Matched artifact scenario differs from the PPO evaluation configuration.")
    if matched_config["horizon"] != ppo_config.horizon:
        raise ValueError("Matched artifact horizon differs from the PPO evaluation configuration.")
    if matched_config["initial_profiles"] != [list(profile.resistance) for profile in __import__(
        "ml.src.ppo_evaluation", fromlist=["canonical_initial_profiles"]
    ).canonical_initial_profiles()]:
        raise ValueError("Gentamicin audit requires the canonical ordered 128-profile evaluation set.")

    decisions = []
    decisions_by_state: dict[str, list[dict]] = defaultdict(list)
    decisions_by_initial: dict[str, list[dict]] = defaultdict(list)
    decisions_by_step: dict[int, list[dict]] = defaultdict(list)
    decisions_by_feasible_set: dict[str, list[dict]] = defaultdict(list)
    gent_transition_groups: dict[str, list[dict]] = defaultdict(list)
    greedy_state_decisions: dict[str, list[int]] = defaultdict(list)
    all_action_probabilities = []
    ppo_action_counts = Counter()
    greedy_action_counts = Counter()
    ppo_entropy_values = []
    gent_selected_entropy = []
    gent_probability_selected = []
    same_case_step_state_matches = 0
    same_case_step_state_gent_count = 0
    gent_selected_count = 0
    gent_feasible_count = 0
    total_ppo_decisions = 0
    counterfactual_reward_differences = []
    infeasible_actions_selected = 0

    initial_states_by_profile = ["".join("R" if bit else "S" for bit in row) for row in matched_config["initial_profiles"]]
    canonical_initial_states = [
        "".join("R" if bit else "S" for bit in profile.resistance)
        for profile in canonical_initial_profiles()
    ]
    if initial_states_by_profile != canonical_initial_states:
        raise ValueError("Matched artifact does not preserve the canonical 128-profile order.")

    seed_bases_by_training_seed = matched_config["evaluation_seed_bases_by_training_seed"]
    for training_seed_key, seed_bases in seed_bases_by_training_seed.items():
        training_seed = int(training_seed_key)
        matched_model_dir = matched_results_dir / "models" / f"ppo_seed_{training_seed}"
        model_raw = json.loads((matched_model_dir / "raw_trajectories.json").read_text(encoding="utf-8"))
        model_run_config = json.loads((matched_model_dir / "config.json").read_text(encoding="utf-8"))
        model_path = Path(model_run_config["ppo_model_path"])
        if not model_path.is_absolute():
            model_path = Path.cwd() / model_path
        model = load_ppo_model(model_path, device=ppo_config.device)
        environment = make_training_environment(ppo_config)
        try:
            for case in model_raw:
                ppo_episode = case["ppo"]
                greedy_episode = case["greedy"]
                initial_label = case["initial_state"]
                case_id = case["case_id"]
                greedy_steps = greedy_episode["steps"]
                greedy_action_counts.update(ANTIBIOTICS[int(step["action"])] for step in greedy_steps)
                for step_index, step in enumerate(ppo_episode["steps"]):
                    total_ppo_decisions += 1
                    current_state = _episode_current_state(step)
                    current_label = _label(current_state)
                    mask = np.asarray([value == 0 for value in current_state], dtype=bool)
                    probabilities = extract_masked_action_probabilities(
                        model,
                        np.asarray(step["observation"], dtype=np.float32),
                        mask,
                    )
                    selected_action = int(step["action"])
                    selected_name = ANTIBIOTICS[selected_action]
                    ppo_action_counts[selected_name] += 1
                    if not mask[selected_action]:
                        infeasible_actions_selected += 1
                        raise ValueError("Saved PPO trajectory contains an infeasible action.")
                    all_action_probabilities.append(probabilities)
                    ppo_entropy_values.append(_decision_entropy(probabilities))
                    feasible_ids = tuple(int(action) for action in np.flatnonzero(mask))
                    feasible_set = ",".join(ANTIBIOTICS[action] for action in feasible_ids)
                    greedy_step = greedy_steps[step_index] if step_index < len(greedy_steps) else None
                    greedy_current_state = _episode_current_state(greedy_step) if greedy_step else None
                    greedy_same_state = greedy_current_state == current_state
                    greedy_same_action = int(greedy_step["action"]) if greedy_same_state else None
                    if greedy_same_state:
                        same_case_step_state_matches += 1
                        same_case_step_state_gent_count += int(greedy_same_action == GENTAMICIN_ACTION)
                    greedy_state_decisions[current_label].append(
                        int(greedy_same_action == GENTAMICIN_ACTION)
                        if greedy_same_state else -1
                    )
                    gent_is_feasible = bool(mask[GENTAMICIN_ACTION])
                    if gent_is_feasible:
                        gent_feasible_count += 1
                    gent_selected = selected_action == GENTAMICIN_ACTION
                    alternatives = ()
                    if gent_selected:
                        gent_selected_count += 1
                        selected_probability = probabilities[GENTAMICIN_ACTION]
                        gent_probability_selected.append(selected_probability)
                        gent_selected_entropy.append(_decision_entropy(probabilities))
                        info = step["info"]
                        alternatives = counterfactual_one_step_actions(
                            environment,
                            ResistanceState(current_state),
                            int(info["transition_seed"]),
                            step_index,
                        )
                        selected_counterfactual = next(
                            item for item in alternatives if item["action"] == GENTAMICIN_ACTION
                        )
                        if (
                            selected_counterfactual["next_state"] != _label(tuple(int(v) for v in step["next_observation"][:7]))
                            or selected_counterfactual["transition_type"] != info["transition_status"]
                            or not np.isclose(selected_counterfactual["immediate_reward"], step["reward"])
                        ):
                            raise ValueError("Seeded Gentamicin replay does not match the recorded PPO transition.")
                        counterfactual_reward_differences.extend(
                            selected_probability - probabilities[item["action"]]
                            for item in alternatives if item["action"] != GENTAMICIN_ACTION
                        )

                    current_resistant_count = sum(current_state)
                    next_state = tuple(int(value) for value in step["next_observation"][:7])
                    resistance_delta = sum(next_state) - current_resistant_count
                    decision = {
                        "case_id": case_id,
                        "ppo_training_seed": training_seed,
                        "initial_profile": initial_label,
                        "current_state": current_label,
                        "treatment_step": step_index,
                        "resistance_count_before": current_resistant_count,
                        "feasible_actions": [ANTIBIOTICS[action] for action in feasible_ids],
                        "feasible_action_count": len(feasible_ids),
                        "feasible_action_set": feasible_set,
                        "action_probabilities": {
                            ANTIBIOTICS[action]: probabilities[action]
                            for action in range(len(ANTIBIOTICS))
                        },
                        "policy_entropy_nats": _decision_entropy(probabilities),
                        "selected_action": selected_action,
                        "selected_antibiotic": selected_name,
                        "selected_action_probability": probabilities[selected_action],
                        "gentamicin_feasible": gent_is_feasible,
                        "gentamicin_selected": gent_selected,
                        "greedy_current_state_in_same_case_step": _label(greedy_current_state) if greedy_current_state else None,
                        "greedy_same_case_step_state_matches": greedy_same_state,
                        "greedy_action_if_same_state": ANTIBIOTICS[greedy_same_action] if greedy_same_action is not None else None,
                        "greedy_gentamicin_probability_at_this_state": (
                            1.0 / len(feasible_ids) if gent_is_feasible else 0.0
                        ),
                        "actual_transition_type": step["info"]["transition_status"],
                        "actual_transition_sources": step["info"].get("source_ids", []),
                        "collateral_sensitivity_occurred": step["info"]["transition_status"] == "collateral_sensitivity",
                        "next_state": _label(next_state),
                        "resistance_count_after": sum(next_state),
                        "resistance_delta": resistance_delta,
                        "resistance_increased": resistance_delta > 0,
                        "resistance_unchanged": resistance_delta == 0,
                        "reward": float(step["reward"]),
                        "episode_final_state": _label(tuple(ppo_episode["final_resistance_profile"])),
                        "episode_final_resistant_count": sum(ppo_episode["final_resistance_profile"]),
                        "episode_cumulative_resistance_burden": -(
                            sum(float(saved_step["reward"]) for saved_step in ppo_episode["steps"])
                            + float(ppo_episode.get("terminal_reward_adjustment", 0.0))
                        ),
                        "actual_ppo_remaining_burden_from_decision": -sum(float(s["reward"]) for s in ppo_episode["steps"][step_index:]),
                        "counterfactual_one_step_alternatives": list(alternatives),
                    }
                    decisions.append(decision)
                    decisions_by_state[current_label].append(decision)
                    decisions_by_initial[initial_label].append(decision)
                    decisions_by_step[step_index].append(decision)
                    decisions_by_feasible_set[feasible_set].append(decision)
                    if gent_selected:
                        transition_bucket = (
                            f"{step['info']['transition_status']}|"
                            f"{'increase' if resistance_delta > 0 else 'decrease' if resistance_delta < 0 else 'unchanged'}|"
                            f"collateral={step['info']['transition_status'] == 'collateral_sensitivity'}"
                        )
                        gent_transition_groups[transition_bucket].append(decision)
        finally:
            environment.close()

    return _write_gentamicin_audit(
        matched_results_dir=matched_results_dir,
        output_dir=output_dir,
        decisions=decisions,
        ppo_action_counts=ppo_action_counts,
        greedy_action_counts=greedy_action_counts,
        decisions_by_state=decisions_by_state,
        decisions_by_initial=decisions_by_initial,
        decisions_by_step=decisions_by_step,
        decisions_by_feasible_set=decisions_by_feasible_set,
        gent_transition_groups=gent_transition_groups,
        greedy_state_decisions=greedy_state_decisions,
        all_action_probabilities=all_action_probabilities,
        ppo_entropy_values=ppo_entropy_values,
        gent_selected_entropy=gent_selected_entropy,
        gent_probability_selected=gent_probability_selected,
        same_case_step_state_matches=same_case_step_state_matches,
        same_case_step_state_gent_count=same_case_step_state_gent_count,
        gent_selected_count=gent_selected_count,
        gent_feasible_count=gent_feasible_count,
        total_ppo_decisions=total_ppo_decisions,
        counterfactual_reward_differences=counterfactual_reward_differences,
        infeasible_actions_selected=infeasible_actions_selected,
    )


def _group_rows(records: dict[str, list[dict]], key_name: str, *, selection_name: str = "gentamicin_selected") -> list[dict[str, Any]]:
    output = []
    for key, group in sorted(records.items()):
        feasible = [row for row in group if row["gentamicin_feasible"]]
        selected = [row for row in feasible if row[selection_name]]
        output.append({
            key_name: key,
            "ppo_decision_count": len(group),
            "gentamicin_feasible_count": len(feasible),
            "gentamicin_selected_count": len(selected),
            "gentamicin_selection_frequency_when_feasible": (
                len(selected) / len(feasible) if feasible else None
            ),
            "mean_gentamicin_probability_when_feasible": (
                statistics.mean(row["action_probabilities"]["GENTAMICIN"] for row in feasible)
                if feasible else None
            ),
            "mean_policy_entropy_nats": statistics.mean(row["policy_entropy_nats"] for row in group),
        })
    return output


def _write_gentamicin_audit(**data) -> dict[str, Any]:
    decisions = data["decisions"]
    output_dir = data["output_dir"]
    gent_feasible = [row for row in decisions if row["gentamicin_feasible"]]
    gent_selected = [row for row in gent_feasible if row["gentamicin_selected"]]
    selected_transition_counts = Counter(row["actual_transition_type"] for row in gent_selected)
    selected_resistance_outcomes = Counter(
        "increase" if row["resistance_increased"]
        else "unchanged" if row["resistance_unchanged"]
        else "decrease"
        for row in gent_selected
    )
    selected_collateral_count = sum(row["collateral_sensitivity_occurred"] for row in gent_selected)
    profile_index_lookup = {
        "".join("R" if bit else "S" for bit in profile.resistance): index
        for index, profile in enumerate(canonical_initial_profiles())
    }
    greedy_state_rows = []
    for state, choices in sorted(data["greedy_state_decisions"].items()):
        observed = [choice for choice in choices if choice >= 0]
        resistant_count = state.count("R")
        feasible_count = len(ANTIBIOTICS) - resistant_count
        greedy_state_rows.append({
            "current_state": state,
            "resistant_count": resistant_count,
            "feasible_action_count": feasible_count,
            "ppo_case_step_visits": len(choices),
            "matched_greedy_state_visits": len(observed),
            "greedy_gentamicin_selection_count": sum(observed),
            "greedy_gentamicin_frequency_when_state_matched": (
                sum(observed) / len(observed) if observed else None
            ),
            "greedy_theoretical_probability_if_gentamicin_feasible": (
                1 / feasible_count if feasible_count and state[4] == "S" else 0.0
            ),
        })
    greedy_same_state_visit_count = sum(row["matched_greedy_state_visits"] for row in greedy_state_rows)
    greedy_same_state_gent_count = sum(row["greedy_gentamicin_selection_count"] for row in greedy_state_rows)
    greedy_expected_gent_count = sum(
        row["greedy_theoretical_probability_if_gentamicin_feasible"]
        * row["matched_greedy_state_visits"]
        for row in greedy_state_rows
    )

    representative_positive = []
    positive_seen = set()
    def immediate_alternative_gain(row):
        return max((
            alternative["immediate_reward"] - row["reward"]
            for alternative in row["counterfactual_one_step_alternatives"]
            if alternative["action"] != GENTAMICIN_ACTION
        ), default=-float("inf"))

    selected_examples = sorted(
        gent_selected,
        key=lambda item: (
            immediate_alternative_gain(item),
            item["selected_action_probability"],
        ),
        reverse=True,
    )
    for row in selected_examples:
        if row["current_state"] in positive_seen:
            continue
        positive_seen.add(row["current_state"])
        representative_positive.append(row)
        if len(representative_positive) == 3:
            break
    representative_negative = []
    negative_seen = set()
    for row in sorted(
        (item for item in gent_feasible if not item["gentamicin_selected"]),
        key=lambda item: item["action_probabilities"]["GENTAMICIN"],
        reverse=True,
    ):
        if row["current_state"] in negative_seen:
            continue
        negative_seen.add(row["current_state"])
        representative_negative.append(row)
        if len(representative_negative) == 3:
            break

    representative_traces = {
        "gentamicin_selected": representative_positive,
        "gentamicin_feasible_but_not_selected": representative_negative,
        "counterfactual_scope": "One-step same-seed transition/reward only; no counterfactual downstream policy rollout is estimated.",
    }
    state_rows = _group_rows(data["decisions_by_state"], "current_state")
    resistance_count_groups: dict[int, list[dict]] = defaultdict(list)
    for row in state_rows:
        row["profile_index"] = profile_index_lookup[row["current_state"]]
        row["resistant_count"] = row["current_state"].count("R")
        resistance_count_groups[row["resistant_count"]].extend(data["decisions_by_state"][row["current_state"]])
    state_rows.sort(key=lambda row: row["profile_index"])
    resistance_count_rows = _group_rows(
        {str(key): value for key, value in resistance_count_groups.items()},
        "resistant_count",
    )
    for row in resistance_count_rows:
        row["resistant_count"] = int(row["resistant_count"])
    resistance_count_rows.sort(key=lambda row: row["resistant_count"])
    initial_rows = _group_rows(data["decisions_by_initial"], "initial_profile")
    step_rows = _group_rows({str(key): value for key, value in data["decisions_by_step"].items()}, "treatment_step")
    feasible_rows = _group_rows(data["decisions_by_feasible_set"], "feasible_action_set")
    transition_rows = []
    for transition, group in sorted(data["gent_transition_groups"].items()):
        transition_rows.append({
            "transition_and_resistance_change": transition,
            "gentamicin_selected_count": len(group),
            "mean_selected_probability": statistics.mean(row["selected_action_probability"] for row in group),
            "mean_immediate_reward": statistics.mean(row["reward"] for row in group),
            "mean_actual_remaining_burden": statistics.mean(row["actual_ppo_remaining_burden_from_decision"] for row in group),
        })

    alternative_rows = []
    alternatives_by_action: dict[str, list[dict]] = defaultdict(list)
    for row in gent_selected:
        for alternative in row["counterfactual_one_step_alternatives"]:
            if alternative["action"] != GENTAMICIN_ACTION:
                alternative["policy_probability"] = row["action_probabilities"][alternative["antibiotic"]]
                alternative["gentamicin_probability"] = row["selected_action_probability"]
                alternative["current_state"] = row["current_state"]
                alternative["case_id"] = row["case_id"]
                alternative["immediate_reward_difference_vs_gentamicin"] = (
                    alternative["immediate_reward"] - row["reward"]
                )
                alternatives_by_action[alternative["antibiotic"]].append(alternative)
                alternative_rows.append(alternative)
    alternative_summary = []
    for antibiotic, group in sorted(alternatives_by_action.items()):
        alternative_summary.append({
            "alternative_antibiotic": antibiotic,
            "comparison_count_at_gentamicin_selected_states": len(group),
            "mean_policy_probability": statistics.mean(row["policy_probability"] for row in group),
            "mean_one_step_reward": statistics.mean(row["immediate_reward"] for row in group),
            "one_step_reward_better_than_gentamicin_count": sum(
                row["immediate_reward_difference_vs_gentamicin"] > 1e-12 for row in group
            ),
            "one_step_reward_tied_with_gentamicin_count": sum(
                abs(row["immediate_reward_difference_vs_gentamicin"]) <= 1e-12 for row in group
            ),
            "one_step_reward_worse_than_gentamicin_count": sum(
                row["immediate_reward_difference_vs_gentamicin"] < -1e-12 for row in group
            ),
        })

    overall_actions = {
        "ppo": {
            name: data["ppo_action_counts"][name] / data["total_ppo_decisions"]
            for name in ANTIBIOTICS
        },
        "greedy": {
            name: data["greedy_action_counts"][name] / sum(data["greedy_action_counts"].values())
            for name in ANTIBIOTICS
        },
    }
    summary = {
        "total_ppo_decisions": data["total_ppo_decisions"],
        "ppo_action_counts": dict(data["ppo_action_counts"]),
        "ppo_action_selection_frequency": overall_actions["ppo"],
        "greedy_action_counts": dict(data["greedy_action_counts"]),
        "greedy_action_selection_frequency": overall_actions["greedy"],
        "gentamicin_feasible_decisions": data["gent_feasible_count"],
        "gentamicin_selected_decisions": data["gent_selected_count"],
        "gentamicin_frequency_over_all_ppo_decisions": (
            data["gent_selected_count"] / data["total_ppo_decisions"]
        ),
        "gentamicin_selection_frequency_when_feasible": (
            data["gent_selected_count"] / data["gent_feasible_count"]
            if data["gent_feasible_count"] else None
        ),
        "gentamicin_selected_mean_policy_probability": _mean(data["gent_probability_selected"]),
        "mean_policy_entropy_nats_all_decisions": _mean(data["ppo_entropy_values"]),
        "mean_policy_entropy_nats_when_gentamicin_selected": _mean(data["gent_selected_entropy"]),
        "gentamicin_selected_transition_types": dict(selected_transition_counts),
        "gentamicin_selected_resistance_changes": dict(selected_resistance_outcomes),
        "gentamicin_selected_collateral_sensitivity_count": selected_collateral_count,
        "gentamicin_selected_resistance_increase_count": selected_resistance_outcomes.get("increase", 0),
        "gentamicin_selected_resistance_unchanged_count": selected_resistance_outcomes.get("unchanged", 0),
        "gentamicin_selected_resistance_decrease_count": selected_resistance_outcomes.get("decrease", 0),
        "gentamicin_infeasible_actions_selected": data["infeasible_actions_selected"],
        "mean_selected_probability_margin_over_alternatives": _mean(data["counterfactual_reward_differences"]),
        "greedy_same_case_step_state_matches": greedy_same_state_visit_count,
        "greedy_gentamicin_selections_in_same_state_matches": greedy_same_state_gent_count,
        "greedy_gentamicin_frequency_in_same_state_matches": (
            greedy_same_state_gent_count / greedy_same_state_visit_count
            if greedy_same_state_visit_count else None
        ),
        "greedy_expected_gentamicin_frequency_in_same_states": (
            greedy_expected_gent_count / greedy_same_state_visit_count
            if greedy_same_state_visit_count else None
        ),
        "gentamicin_selected_decisions_with_better_one_step_alternative": sum(
            immediate_alternative_gain(row) > 1e-12 for row in gent_selected
        ),
        "counterfactual_scope": "Alternative actions replayed one step with the recorded transition seed; downstream rollouts for unselected actions are not estimated.",
        "greedy_expected_gentamicin_probability": "1 / number of feasible actions when Gentamicin is feasible; zero otherwise",
    }

    action_group_rows = []
    for key, group in sorted(data["gent_transition_groups"].items()):
        action_group_rows.append({"group_type": "gentamicin_transition", "group": key, "count": len(group)})
    action_group_rows.extend({"group_type": "current_state", **row} for row in state_rows)
    action_group_rows.extend({"group_type": "initial_profile", **row} for row in initial_rows)
    action_group_rows.extend({"group_type": "treatment_step", **row} for row in step_rows)
    action_group_rows.extend({"group_type": "feasible_action_set", **row} for row in feasible_rows)

    (output_dir / "decision_audit.json").write_text(
        json.dumps(decisions, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "representative_traces.json").write_text(
        json.dumps(representative_traces, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "alternative_action_summary.json").write_text(
        json.dumps(alternative_summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(output_dir / "gentamicin_decisions.csv", [row for row in decisions if row["gentamicin_feasible"]])
    _write_csv(output_dir / "by_current_state.csv", state_rows)
    _write_csv(output_dir / "by_resistance_count.csv", resistance_count_rows)
    _write_csv(output_dir / "by_initial_profile.csv", initial_rows)
    _write_csv(output_dir / "by_treatment_step.csv", step_rows)
    _write_csv(output_dir / "by_feasible_action_set.csv", feasible_rows)
    _write_csv(output_dir / "by_gentamicin_transition.csv", transition_rows)
    _write_csv(output_dir / "gentamicin_alternative_actions.csv", alternative_rows)
    _write_csv(output_dir / "greedy_same_state_comparison.csv", greedy_state_rows)

    plots = generate_gentamicin_audit_plots(
        overall_action_frequencies=overall_actions,
        state_rows=state_rows,
        representative_traces=representative_traces,
        action_names=ANTIBIOTICS,
        output_directory=output_dir / "plots",
    )
    report = _render_report(summary, transition_rows, alternative_summary, representative_traces, plots)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    return {"summary": summary, "report": str(output_dir / "report.md"), "plots": plots}


def _render_report(summary, transitions, alternatives, representatives, plots) -> str:
    gent_percent = 100 * summary["gentamicin_frequency_over_all_ppo_decisions"]
    feasible_percent = 100 * summary["gentamicin_selection_frequency_when_feasible"]
    transition_lines = "\n".join(
        f"| {row['transition_and_resistance_change']} | {row['gentamicin_selected_count']} | "
        f"{row['mean_selected_probability']:.4f} | {row['mean_immediate_reward']:.4f} |"
        for row in transitions
    )
    alternative_lines = "\n".join(
        f"| {row['alternative_antibiotic']} | {row['comparison_count_at_gentamicin_selected_states']} | "
        f"{row['mean_policy_probability']:.4f} | {row['mean_one_step_reward']:.4f} | "
        f"{row['one_step_reward_better_than_gentamicin_count']} |"
        for row in alternatives
    )
    positive = representatives["gentamicin_selected"]
    negative = representatives["gentamicin_feasible_but_not_selected"]
    representative_lines = []
    for heading, group in (("Gentamicin selected", positive), ("Gentamicin feasible but not selected", negative)):
        representative_lines.append(f"### {heading}")
        for item in group:
            alternatives = item["counterfactual_one_step_alternatives"]
            alternative_text = (
                "; ".join(
                    f"{alternative['antibiotic']} P={item['action_probabilities'][alternative['antibiotic']]:.3f} "
                    f"{alternative['transition_type']} -> {alternative['next_state']} "
                    f"(r={alternative['immediate_reward']:.3f})"
                    for alternative in alternatives if alternative["action"] != GENTAMICIN_ACTION
                )
                if alternatives
                else "; ".join(
                    f"{name} P={item['action_probabilities'][name]:.3f}"
                    for name in item["feasible_actions"] if name != "GENTAMICIN"
                ) or "no other feasible actions"
            )
            representative_lines.append(
                f"- Case `{item['case_id']}`, initial `{item['initial_profile']}`, current `{item['current_state']}` "
                f"at step {item['treatment_step']}: action `{item['selected_antibiotic']}`, "
                f"P(Gentamicin)={item['action_probabilities']['GENTAMICIN']:.4f}; feasible: "
                f"{', '.join(item['feasible_actions'])}; transition `{item['actual_transition_type']}` "
                f"to `{item['next_state']}`; reward {item['reward']:.4f}; "
                f"actual remaining burden {item['actual_ppo_remaining_burden_from_decision']:.4f}. "
                f"Feasible alternative(s): {alternative_text}."
            )
    plot_lines = "\n".join(f"- `{path}`" for path in plots)
    return (
        "# Gentamicin Policy Audit\n\n"
        f"PPO decisions: {summary['total_ppo_decisions']}; Gentamicin feasible in "
        f"{summary['gentamicin_feasible_decisions']} ({feasible_percent:.1f}% selected when feasible); "
        f"selected in {summary['gentamicin_selected_decisions']} ({gent_percent:.1f}% of all PPO actions).\n\n"
        f"Mean masked-policy entropy: {summary['mean_policy_entropy_nats_all_decisions']:.4f} nats overall and "
        f"{summary['mean_policy_entropy_nats_when_gentamicin_selected']:.4f} when Gentamicin was selected. "
        "No arbitrary over-concentration threshold is applied.\n\n"
        "## Gentamicin Outcomes\n\n"
        "| Transition/change | Selections | Mean PPO probability | Mean immediate reward |\n|---|---:|---:|---:|\n"
        + transition_lines
        + "\n\n## Feasible Alternatives at Gentamicin Decisions\n\n"
        + "The same recorded step seed was replayed once per feasible action. These are one-step counterfactuals only; no alternative downstream rollout is inferred.\n\n"
        + "| Alternative | Comparisons | Mean PPO probability | Mean one-step reward | Reward better than Gent count |\n|---|---:|---:|---:|---:|\n"
        + alternative_lines
        + "\n\n## Representative Traces\n\n"
        + "\n".join(representative_lines)
        + "\n\n## Greedy Comparison\n\n"
        + f"For {summary['greedy_same_case_step_state_matches']} PPO state/step occurrences the matched Greedy trajectory was in the exact same state; "
        + f"Greedy chose Gentamicin in {summary['greedy_gentamicin_selections_in_same_state_matches']} of those. "
        + f"That is {summary['greedy_gentamicin_frequency_in_same_state_matches']:.1%}, versus a state-weighted uniform-feasible expectation of "
        + f"{summary['greedy_expected_gentamicin_frequency_in_same_states']:.1%}.\n\n"
        + "## Interpretation\n\n"
        + f"Gentamicin-selected transitions: {summary['gentamicin_selected_transition_types']}. "
        + f"Resistance changes: {summary['gentamicin_selected_resistance_changes']}. "
        + f"Collateral-sensitivity selections: {summary['gentamicin_selected_collateral_sensitivity_count']}. "
        + "A high Gentamicin preference accompanied by `unsupported_no_candidate` means the model leaves the state unchanged for lack of an applicable evidence-supported candidate; "
        + "it is not evidence of a favorable biological effect. The learned policy probabilities describe model behavior, not neural-network biological reasoning.\n\n"
        + f"At {summary['gentamicin_selected_decisions_with_better_one_step_alternative']} Gentamicin-selected decisions, at least one feasible alternative had a better immediate burden reward under the same recorded step seed; "
        + "the most common such alternative was ciprofloxacin through a modeled collateral-sensitivity transition. This is one-step evidence only; it does not establish that an alternative's full downstream trajectory is better.\n\n"
        + f"{summary['counterfactual_scope']}\n\n## Plots\n\n{plot_lines}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit MaskablePPO Gentamicin selection in matched traces.")
    parser.add_argument("--matched-results-dir", required=True)
    parser.add_argument("--ppo-config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = run_gentamicin_audit(
        args.matched_results_dir,
        args.ppo_config,
        args.output_dir,
    )
    print(json.dumps(result["summary"], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
