import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

import numpy as np
import torch

from ml.src.decision_traces import build_decision_trace
from ml.src.gentamicin_audit import extract_masked_action_probabilities
from ml.src.ppo_training import PPOConfig, environment_manifest, load_ppo_model, make_training_environment
from ml.src.ppo_vi_reference import (
    compare_reference_action, planning_state_from_observation,
    reference_observation, reference_predecessor_histories,
)
from ml.src.ppo_visualizations import generate_reference_benchmark_plots
from ml.src.value_iteration import value_iteration
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.episode import EpisodeState
from simulation.resistance_state import ANTIBIOTICS


def label(profile):
    return "".join("R" if value else "S" for value in profile)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        if not rows:
            return
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({
            key: json.dumps(value, allow_nan=False) if isinstance(value, (dict, list, tuple)) else value
            for key, value in row.items()
        } for row in rows)


def inspect_compatibility(config, reference):
    stochastic = make_training_environment(config)
    try:
        action_mapping_same = stochastic.action_space_config.actions == reference._action_config.actions
        observation_shape_same = stochastic.observation_space.shape == reference.observation_space.shape
        horizon_same = stochastic.episode_termination.max_steps == reference.max_steps == 8
        reward_same = stochastic.episode_progression.episode_step.reward_function.specification == reference._reward.specification
        terminal_same = all(
            stochastic.episode_termination.is_terminated(state) == reference.is_terminal(state)
            for state in reference.states()
        )
        if not (action_mapping_same and observation_shape_same and horizon_same and reward_same and terminal_same and config.gamma == 1):
            raise ValueError("State/action/reward/horizon/terminal compatibility check failed.")
        return {
            "state_representation": "same seven binary indicators plus elapsed time; PPO also observes one-hot last action",
            "action_ids": "identical canonical seven action IDs; checked",
            "action_availability": "same susceptible-only constraint; terminal states take no action; raw transition APIs still accept diagnostic actions",
            "reward": "same normalized post-transition resistance burden and all-resistant terminal-tail accounting",
            "horizon": 8, "gamma": 1.0,
            "terminal_handling": "same horizon/all-resistant conditions; initially all-resistant return is -remaining horizon, no action",
            "transition_semantics": {
                "ppo_training": config.scenario_id,
                "reference": "REF_DETERMINISTIC_FIRST_SUPPORTED",
                "difference": "stochastic candidate sampling versus lexicographically first supported candidate",
            },
            "observation_bounds": {
                "ppo": stochastic.observation_space.low.tolist(),
                "reference": reference.observation_space.low.tolist(),
                "interpretation": "PPO schema permits unknown (-1) susceptibility; reference supplies binary known values within PPO bounds",
            },
            "history_contexts": "step 0 uses empty history; later steps enumerate last-action IDs with a feasible one-step predecessor in the deterministic reference. Missing histories are flagged, not synthesized.",
            "value_scope": "exact optimum under the deterministic computational reference, not stochastic, biological, or clinical truth",
            "direct_evaluation": "existing fixed PPO checkpoints are evaluated under unchanged deterministic reference transitions; stochastic PPO returns are not compared with VI values",
            "critic_scope": "PPO exposes a stochastic-trained state-value estimate, not an action-Q estimate. It is recorded separately without calibrating it against exact VI.",
            "numerical_convention": "exact Q equality defines optimal ties, matching VI; positive gaps <=1e-12 are additionally flagged but not merged into exact agreement",
        }
    finally:
        stochastic.close()


def inspect_policy(model, observation):
    mask = observation[:7] == 0
    probabilities = extract_masked_action_probabilities(model, observation, mask)
    action_value, _ = model.predict(observation, deterministic=True, action_masks=mask)
    action = int(np.asarray(action_value).reshape(-1)[0])
    if not mask[action]:
        raise ValueError("PPO action is outside reference feasibility mask.")
    tensor, _ = model.policy.obs_to_tensor(observation)
    with torch.no_grad():
        critic = float(model.policy.predict_values(tensor).detach().cpu().reshape(-1)[0])
    if not np.isfinite(critic):
        raise ValueError("PPO critic estimate is nonfinite.")
    return action, probabilities, critic


def grouped_results(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return [{
        key: group_key, "evaluated_observation_contexts": len(group),
        "exact_optimal_contexts": sum(row["selects_exact_optimal_action"] for row in group),
        "exact_optimal_action_agreement": mean(row["selects_exact_optimal_action"] for row in group),
        "mean_reference_action_gap": mean(row["reference_action_value_gap"] for row in group),
        "max_reference_action_gap": max(row["reference_action_value_gap"] for row in group),
    } for group_key, group in sorted(groups.items())]


def comparison_summary(rows):
    positive = [row["reference_action_value_gap"] for row in rows if row["reference_action_value_gap"] > 0]
    gentamicin = [row for row in rows if row["ppo_action"] == 4]
    state_groups = grouped_results(rows, "state_step_key")
    return {
        "evaluated_observation_contexts": len(rows),
        "evaluated_minimal_state_steps": len(state_groups),
        "exact_optimal_action_agreement": mean(row["selects_exact_optimal_action"] for row in rows),
        "minimal_state_balanced_agreement": mean(row["exact_optimal_action_agreement"] for row in state_groups),
        "agreement_categories": dict(Counter(row["agreement_category"] for row in rows)),
        "mean_reference_action_gap": mean(row["reference_action_value_gap"] for row in rows),
        "mean_positive_reference_action_gap": mean(positive) if positive else 0.0,
        "max_reference_action_gap": max(positive, default=0.0),
        "gentamicin_selected_contexts": len(gentamicin),
        "gentamicin_exact_optimal_action_agreement": mean(row["selects_exact_optimal_action"] for row in gentamicin) if gentamicin else None,
        "gentamicin_mean_reference_action_gap": mean(row["reference_action_value_gap"] for row in gentamicin) if gentamicin else None,
        "immediate_disadvantage_exact_long_horizon_tie_count": sum(
            row["immediate_disadvantage_vs_vi_action"] and row["reference_action_value_gap"] == 0 for row in rows
        ),
    }


def reference_rollout(model, reference, solution, start, last_action, seed, checkpoint, case_id):
    state, history = start, last_action
    steps, probabilities = [], []
    while not reference.is_terminal(state):
        observation = reference_observation(state, history)
        action, policy_probabilities, _ = inspect_policy(model, observation)
        next_state, reward, terminal, info = reference.transition(state, action)
        steps.append({
            "observation": observation.tolist(), "action": action,
            "next_observation": reference_observation(next_state, action).tolist(),
            "reward": reward, "terminated": terminal, "truncated": False, "info": info,
        })
        probabilities.append(policy_probabilities)
        state, history = next_state, action
    terminal_adjustment = solution.state_values[start] if not steps else 0.0
    episode = {
        "episode_id": 0, "environment_seed": None,
        "initial_resistance_profile": list(start.resistance_state.resistance),
        "steps": steps, "terminal_reward_adjustment": terminal_adjustment,
    }
    decisions = [build_decision_trace(
        episode, index, probabilities[index], reference, case_id=case_id,
        training_seed=seed, checkpoint_identifier=checkpoint,
        initial_treatment_step=start.treatment_step,
    ) for index in range(len(steps))]
    for decision in decisions:
        state_at_decision = planning_state_from_observation(decision["observation"])
        decision["exact_reference_comparison"] = compare_reference_action(
            reference, solution, state_at_decision, decision["selected_action"],
        )
    total_return = sum(step["reward"] for step in steps) + terminal_adjustment
    return {
        "episode_key": case_id, "initial_profile": list(start.resistance_state.resistance),
        "initial_treatment_step": start.treatment_step, "last_action_at_start": last_action,
        "training_seed": seed, "decisions": decisions,
        "cumulative_resistance_burden": -total_return,
        "ppo_reference_return": total_return,
        "vi_optimal_reference_return": solution.state_values[start],
        "full_policy_reference_value_gap": solution.state_values[start] - total_return,
    }


def classify_ciprofloxacin_reference(diagnostic, cipro_q):
    ppo_q = diagnostic["vi_q_value_of_ppo_action"]
    optimal = diagnostic["vi_optimal_state_value"]
    neither_optimal = ppo_q != optimal and cipro_q != optimal
    return (
        "C_neither_action_exact_optimal" if neither_optimal
        else "A_ciprofloxacin_higher_exact_reference_q" if cipro_q > ppo_q
        else "B_ppo_action_equal_or_higher_exact_reference_q"
    )


def run_reference_benchmark(matched_directory, traces_directory, config_path, output_directory):
    config = PPOConfig.from_json(config_path)
    matched_directory, traces_directory, output_directory = map(Path, (matched_directory, traces_directory, output_directory))
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"Benchmark directory is not empty: {output_directory}")
    source_config = json.loads((matched_directory / "config.json").read_text(encoding="utf-8"))
    if source_config["scenario_id"] != config.scenario_id or source_config["horizon"] != config.horizon:
        raise ValueError("Saved matched evaluation contract differs from the requested configuration.")
    step4_summary = json.loads((traces_directory / "summary.json").read_text(encoding="utf-8"))
    comparisons = json.loads((traces_directory / "ciprofloxacin_immediate_advantage.json").read_text(encoding="utf-8"))
    reference = DeterministicReferenceEnvironment(max_steps=config.horizon)
    compatibility = inspect_compatibility(config, reference)
    solution = value_iteration(reference, gamma=1.0)
    histories = reference_predecessor_histories(reference)
    episode_before = reference.episode
    random_before = deepcopy(reference.np_random.bit_generator.state)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "compatibility.json").write_text(json.dumps(compatibility, indent=2), encoding="utf-8")
    (output_directory / "compatibility.md").write_text(
        "# PPO / VI Compatibility\n\n" + "\n\n".join(
            f"## {key}\n\n{json.dumps(value) if isinstance(value, dict) else value}" for key, value in compatibility.items()
        ) + "\n", encoding="utf-8",
    )
    rows, flagged_states, rollout_rows, cipro_rows, examples = [], [], [], [], {}
    per_seed = {}
    model_provenance = []
    current_manifest = environment_manifest(config)
    try:
        for provenance in sorted(step4_summary["model_provenance"], key=lambda item: item["training_seed"]):
            seed = provenance["training_seed"]
            checkpoint = Path(provenance["checkpoint"])
            checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            if checkpoint_hash != provenance["checkpoint_sha256"]:
                raise ValueError("Checkpoint changed since Step 4; probabilities cannot be attributed to saved decisions.")
            training_config = PPOConfig.from_json(checkpoint.parent / "config.json")
            for field in ("horizon", "gamma", "scenario_id", "reward_configuration", "action_mask_configuration"):
                if getattr(training_config, field) != getattr(config, field):
                    raise ValueError(f"Checkpoint training {field} is incompatible.")
            training_manifest = json.loads((checkpoint.parent / "environment_manifest.json").read_text(encoding="utf-8"))
            if training_manifest["interaction_data_sha256"] != current_manifest["interaction_data_sha256"]:
                raise ValueError("Interaction evidence differs from the checkpoint training environment.")
            model = load_ppo_model(checkpoint, device=config.device)
            if model.gamma != 1 or model.action_space != reference.action_space:
                raise ValueError("Checkpoint gamma or action space is incompatible.")
            if model.observation_space.shape != reference.observation_space.shape:
                raise ValueError("Checkpoint observation shape is incompatible.")
            model_provenance.append({"training_seed": seed, "checkpoint": str(checkpoint), "sha256": checkpoint_hash})
            policy_values, seed_rows = {}, []
            for state in sorted(reference.states(), key=lambda item: (
                -item.treatment_step, item.resistance_state.resistance,
            )):
                profile = state.resistance_state.resistance
                state_key = f"{label(profile)}:{state.treatment_step}"
                if reference.is_terminal(state):
                    flagged_states.append({
                        "training_seed": seed, "state": label(profile), "step": state.treatment_step,
                        "classification": "terminal_no_action_excluded_from_agreement",
                        "vi_state_value": solution.state_values[state],
                    })
                    continue
                last_actions = (None,) if state.treatment_step == 0 else histories.get(profile, ())
                if not last_actions:
                    flagged_states.append({
                        "training_seed": seed, "state": label(profile), "step": state.treatment_step,
                        "classification": "D_no_feasible_reference_predecessor_history",
                        "vi_state_value": solution.state_values[state],
                    })
                for last_action in last_actions:
                    observation = reference_observation(state, last_action)
                    if not model.observation_space.contains(observation):
                        raise ValueError("Reference observation outside checkpoint input bounds.")
                    action, probabilities, critic = inspect_policy(model, observation)
                    diagnostic = compare_reference_action(reference, solution, state, action)
                    next_state, reward, terminal, _ = reference.transition(state, action)
                    repeated_ppo_return = reward + (0.0 if terminal else policy_values[(
                        next_state.resistance_state.resistance, next_state.treatment_step, action,
                    )])
                    policy_values[(profile, state.treatment_step, last_action)] = repeated_ppo_return
                    row = {
                        "training_seed": seed, "state": label(profile), "resistant_count": sum(profile),
                        "step": state.treatment_step, "last_action": last_action, "state_step_key": state_key,
                        "observation": observation.tolist(), "policy_action_probabilities": list(probabilities),
                        "ppo_selected_action_probability": probabilities[action],
                        "ppo_gentamicin_probability": probabilities[4],
                        "reference_gentamicin_q": diagnostic["vi_feasible_q_values"].get("GENTAMICIN"),
                        "ppo_critic_stochastic_trained_state_return_estimate": critic,
                        "ppo_action_q_estimate": None,
                        "ppo_exact_repeated_policy_reference_return": repeated_ppo_return,
                        "full_policy_reference_value_gap": solution.state_values[state] - repeated_ppo_return,
                        **diagnostic,
                    }
                    seed_rows.append(row)
            rows.extend(seed_rows)
            per_seed[str(seed)] = comparison_summary(seed_rows)
            for state in reference.states():
                if state.treatment_step != 0:
                    continue
                rollout = reference_rollout(model, reference, solution, state, None, seed, str(checkpoint), f"{seed}:initial:{label(state.resistance_state.resistance)}")
                if not reference.is_terminal(state):
                    expected = policy_values[(state.resistance_state.resistance, 0, None)]
                    if not np.isclose(rollout["ppo_reference_return"], expected, atol=1e-10, rtol=0):
                        raise ValueError("Repeated-policy dynamic return does not match deterministic rollout.")
                rollout_rows.append(rollout)
            candidate_rules = {
                "exact_agreement": lambda item: item["ppo_action"] == item["vi_optimal_action"],
                "different_action_exact_tie": lambda item: item["agreement_category"] == "different_action_exact_optimal_tie",
                "immediate_disadvantage_long_horizon_equivalent": lambda item: item["immediate_disadvantage_vs_vi_action"] and item["reference_action_value_gap"] == 0,
                "immediate_disadvantage_numerical_tolerance_only": lambda item: item["immediate_disadvantage_vs_vi_action"] and 0 < item["reference_action_value_gap"] <= 1e-12,
                "positive_reference_gap": lambda item: item["reference_action_value_gap"] > 1e-12,
                "gentamicin_selected": lambda item: item["ppo_action"] == 4,
            }
            ordered_rows = sorted(seed_rows, key=lambda item: (tuple(item["observation"][:7]), item["step"], -1 if item["last_action"] is None else item["last_action"]))
            for category, predicate in candidate_rules.items():
                if category in examples:
                    continue
                chosen = next((row for row in ordered_rows if predicate(row)), None)
                if chosen:
                    state = planning_state_from_observation(chosen["observation"])
                    examples[category] = {
                        "decision": chosen,
                        "trace": reference_rollout(model, reference, solution, state, chosen["last_action"], seed, str(checkpoint), f"{seed}:example:{category}"),
                    }
            for comparison in comparisons:
                saved = comparison["decision"]
                if saved["training_seed"] != seed:
                    continue
                observation = np.asarray(saved["observation"], dtype=np.float32)
                state = planning_state_from_observation(observation)
                if state not in solution.state_values or reference.is_terminal(state):
                    cipro_rows.append({"training_seed": seed, "case_id": saved["case_id"], "step": saved["step"], "category": "D_incompatible_state"})
                    continue
                action, probabilities, critic = inspect_policy(model, observation)
                if action != saved["selected_action"]:
                    raise ValueError("Checkpoint inference differs from the recorded Step 4 decision.")
                diagnostic = compare_reference_action(reference, solution, state, action)
                cipro_q = solution.action_values[state][0]
                cipro_next, cipro_reward, _, cipro_info = reference.transition(state, 0)
                last_history = next((index for index, value in enumerate(observation[7:14]) if value), None)
                original_history_supported = state.treatment_step == 0 or last_history in histories.get(state.resistance_state.resistance, ())
                category = classify_ciprofloxacin_reference(diagnostic, cipro_q)
                row = {
                    "training_seed": seed, "case_id": saved["case_id"], "state": label(state.resistance_state.resistance),
                    "step": saved["step"], "observation": observation.tolist(), "policy_action_probabilities": list(probabilities),
                    "stochastic_gentamicin_reward": saved["reward"],
                    "stochastic_ciprofloxacin_replay_reward": comparison["ciprofloxacin_alternative"]["immediate_reward"],
                    "reference_ciprofloxacin_reward": cipro_reward,
                    "reference_ciprofloxacin_transition": cipro_info["transition_status"],
                    "reference_ciprofloxacin_next_state": label(cipro_next.resistance_state.resistance),
                    "reference_ciprofloxacin_q": cipro_q,
                    "reference_cipro_q_minus_ppo_action_q": cipro_q - diagnostic["vi_q_value_of_ppo_action"],
                    "reference_immediate_cipro_advantage_preserved": cipro_reward > diagnostic["ppo_immediate_reference_reward"],
                    "original_history_has_reference_predecessor": original_history_supported,
                    "category": category, **diagnostic,
                    "scope": "reference Q diagnostic at the original stochastic observation; not the stochastic action value",
                }
                cipro_rows.append(row)
                if "previous_ciprofloxacin_case" not in examples:
                    examples["previous_ciprofloxacin_case"] = {
                        "decision": row,
                        "trace": reference_rollout(model, reference, solution, state, last_history, seed, str(checkpoint), f"{seed}:example:previous_ciprofloxacin_case"),
                    }
            del model
    finally:
        if reference.episode is not episode_before or reference.np_random.bit_generator.state != random_before:
            raise RuntimeError("Benchmark mutated the interactive reference environment.")
        reference.close()
    for category in (
        "exact_agreement", "different_action_exact_tie", "immediate_disadvantage_long_horizon_equivalent",
        "immediate_disadvantage_numerical_tolerance_only",
        "positive_reference_gap", "gentamicin_selected", "previous_ciprofloxacin_case",
    ):
        examples.setdefault(category, None)
    valid_cipro = [row for row in cipro_rows if "reference_ciprofloxacin_q" in row]
    summary = {
        "compatibility": compatibility,
        "planning_states_per_model": len(solution.state_values), "terminal_and_missing_history_records": len(flagged_states),
        "state_context_comparison": comparison_summary(rows), "per_training_seed": per_seed,
        "initial_profile_count_per_model": 128,
        "common_reference_rollouts": {
            "ppo_mean_return": mean(item["ppo_reference_return"] for item in rollout_rows),
            "vi_mean_return": mean(item["vi_optimal_reference_return"] for item in rollout_rows),
            "mean_full_policy_reference_gap": mean(item["full_policy_reference_value_gap"] for item in rollout_rows),
        },
        "ciprofloxacin_cases": {
            "decision_count": len(cipro_rows), "categories": dict(Counter(row["category"] for row in cipro_rows)),
            "cipro_higher_reference_q": sum(row["reference_cipro_q_minus_ppo_action_q"] > 0 for row in valid_cipro),
            "cipro_exact_equal_reference_q": sum(row["reference_cipro_q_minus_ppo_action_q"] == 0 for row in valid_cipro),
            "cipro_lower_reference_q": sum(row["reference_cipro_q_minus_ppo_action_q"] < 0 for row in valid_cipro),
            "reference_immediate_cipro_advantage_preserved": sum(row["reference_immediate_cipro_advantage_preserved"] for row in valid_cipro),
            "original_histories_without_reference_predecessor": sum(not row["original_history_has_reference_predecessor"] for row in valid_cipro),
        },
        "model_provenance": model_provenance,
        "interaction_data_sha256": current_manifest["interaction_data_sha256"],
        "source_ciprofloxacin_cases_sha256": hashlib.sha256((traces_directory / "ciprofloxacin_immediate_advantage.json").read_bytes()).hexdigest(),
        "representative_selection_rule": "first qualifying row in ascending training seed, binary profile, elapsed step, last-action ID; actual 446-case examples preserve their recorded observation history",
        "examples_present": {name: item is not None for name, item in examples.items()},
    }
    write_csv(output_directory / "raw_state_contexts.csv", rows)
    write_csv(output_directory / "terminal_and_unrepresented_states.csv", flagged_states)
    write_csv(output_directory / "gentamicin_reference_comparison.csv", [row for row in rows if row["ppo_action"] == 4])
    write_csv(output_directory / "ciprofloxacin_446_reference.csv", cipro_rows)
    for key in ("step", "resistant_count", "state"):
        write_csv(output_directory / f"agreement_by_{key}.csv", grouped_results(rows, key))
    for filename, value in (
        ("summary.json", summary), ("example_decisions.json", examples),
        ("deterministic_reference_rollouts.json", rollout_rows),
    ):
        (output_directory / filename).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    generate_reference_benchmark_plots(rows, examples, output_directory / "plots")
    (output_directory / "report.md").write_text(render_reference_report(summary, rows, examples), encoding="utf-8")
    return summary


def render_reference_report(summary, rows, examples):
    statistics = summary["state_context_comparison"]
    lines = [
        "# PPO vs Exact Deterministic Computational Reference", "",
        "State/action/reward/mask/horizon contracts match for known binary states. Training transitions do not match the deterministic reference. This is policy transfer and a common-reference diagnostic, not a stochastic optimality benchmark.",
        "See compatibility.md/json for the full matrix, observation/history limits, and terminal treatment.", "",
        f"Per model, VI covers {summary['planning_states_per_model']} planning states. Terminal states and missing reference predecessor histories are explicitly recorded, not scored as PPO errors.",
        "Later-time contexts retain each feasible predecessor last-action encoding; therefore multiple PPO observations map to one VI state. The context-averaged denominator is a structural diagnostic, not a clinical or visitation distribution.", "",
        f"Evaluated contexts: {statistics['evaluated_observation_contexts']}; exact-optimal/tied action agreement: {statistics['exact_optimal_action_agreement']:.2%}; minimal-state-balanced agreement: {statistics['minimal_state_balanced_agreement']:.2%}.",
        f"Mean action gap {statistics['mean_reference_action_gap']:.6f}; mean positive gap {statistics['mean_positive_reference_action_gap']:.6f}; maximum {statistics['max_reference_action_gap']:.6f}.",
        f"Gentamicin selected contexts: {statistics['gentamicin_selected_contexts']}; exact optimal/tied agreement {statistics['gentamicin_exact_optimal_action_agreement']:.2%}; mean reference action gap {statistics['gentamicin_mean_reference_action_gap']:.6f}.", "",
        "Q*(s, PPO action) assumes exact-optimal continuation after the first action. The repeated-PPO return uses the fixed PPO policy at every reference step. Neither is the stochastic-trained PPO critic estimate. PPO does not expose a valid action-Q estimate here.",
        f"Common deterministic rollouts across all 128 initial profiles per model: {summary['common_reference_rollouts']}.", "",
        "## By Treatment Step", "",
        "| Step | Contexts | Exact optimal agreement | Mean gap | Max gap |", "|---:|---:|---:|---:|---:|",
    ]
    lines.extend(f"| {row['step']} | {row['evaluated_observation_contexts']} | {row['exact_optimal_action_agreement']:.2%} | {row['mean_reference_action_gap']:.6f} | {row['max_reference_action_gap']:.6f} |" for row in grouped_results(rows, "step"))
    lines.extend([
        "", "## The 446 Stochastic Immediate-Ciprofloxacin Cases", "",
        json.dumps(summary["ciprofloxacin_cases"], indent=2), "",
        "Category C (neither action exact-optimal) takes priority; the independent higher/equal/lower reference-Q counts show the action ordering even within C. A/B refer to reference Q, not stochastic Q. D is reserved for state/action incompatibility. Original stochastic immediate superiority is not assumed to persist under the reference rule.",
        "Use reference_immediate_cipro_advantage_preserved alongside Q ordering: loss of the original immediate advantage is a transition-rule difference, not evidence that sacrificing immediate reward yields a better future. Histories without a reference predecessor remain explicitly flagged encoding-level diagnostics.",
        "The original realized stochastic advantage can disappear under lexicographic reference selection. A positive reference gap identifies a deviation from this reference optimum only, not proof of stochastic PPO suboptimality.", "",
        "## Representative Decisions", "",
    ])
    for category, example in examples.items():
        lines.extend([f"### {category}", ""])
        if example is None:
            lines.append("No qualifying example found; none fabricated.")
            continue
        row = example["decision"]
        lines.extend([
            f"Seed {row['training_seed']}; state {row['state']}; step {row['step']}. PPO {row['ppo_antibiotic']}; VI {row['vi_optimal_antibiotic']}; gap {row['reference_action_value_gap']:.17g}; category {row['agreement_category']}.",
            f"Feasible actions: {row['feasible_actions']}. Policy probabilities (canonical seven-drug order): {row['policy_action_probabilities']}.",
            f"Exact feasible Q values: {row['vi_feasible_q_values']}. PPO immediate reference reward {row['ppo_immediate_reference_reward']:.6f}; outcome {row['ppo_reference_transition_type']}; next state {label(row['ppo_next_reference_state'])}.",
            f"Repeated-PPO reference return from this context: {example['trace']['ppo_reference_return']:.6f}; exact state value {example['trace']['vi_optimal_reference_return']:.6f}.",
            "", "| Step | State | Action | Outcome | Reward | Next |", "|---:|---|---|---|---:|---|",
        ])
        lines.extend(f"| {trace['step']} | {label(trace['current_state'])} | {trace['selected_antibiotic_name']} | {trace['transition_type']} | {trace['reward']:.6f} | {label(trace['next_state'])} |" for trace in example["trace"]["decisions"])
        lines.append("")
    lines.extend([
        "## Interpretation Limits", "",
        "Exact ties are not errors. Positive gaps <=1e-12 are flagged separately without changing the solver's exact-equality tie convention. Do not infer model-training quality in the stochastic environment solely from transferred-reference gaps.",
        "Gentamicin has no supported candidate here; unchanged-state outcomes describe model assumptions, not biological advantage. Policy preference versus reference optimality is conditional on this deterministic candidate ordering.",
        "No PPO training, reward, transition, action, mask, or training configuration was changed. No significance tests were run. Stop after Step 5.", "",
        "## Artifacts", "",
        "raw_state_contexts.csv; terminal_and_unrepresented_states.csv; gentamicin_reference_comparison.csv; ciprofloxacin_446_reference.csv; agreement_by_step.csv; agreement_by_resistant_count.csv; agreement_by_state.csv; deterministic_reference_rollouts.json; example_decisions.json; summary.json; compatibility.md/json; plots/.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Benchmark fixed PPO checkpoints against exact deterministic reference values.")
    parser.add_argument("--matched-results-dir", required=True)
    parser.add_argument("--decision-traces-dir", required=True)
    parser.add_argument("--config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(run_reference_benchmark(
        args.matched_results_dir, args.decision_traces_dir, args.config, args.output_dir,
    ), indent=2))


if __name__ == "__main__":
    main()