import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

import numpy as np

from ml.src.decision_traces import build_decision_trace
from ml.src.gentamicin_audit import counterfactual_one_step_actions, extract_masked_action_probabilities
from ml.src.ppo_training import PPOConfig, load_ppo_model, make_training_environment
from ml.src.ppo_visualizations import generate_decision_trace_plots
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def state_label(profile):
    return "".join("R" if value else "S" for value in profile)


def select_representatives(episodes):
    eligible = sorted((item for item in episodes if item["decisions"]), key=lambda item: item["episode_key"])
    if not eligible:
        return {}
    median_burden = median(item["cumulative_resistance_burden"] for item in eligible)
    result = {
        "typical": min(eligible, key=lambda item: abs(item["cumulative_resistance_burden"] - median_burden)),
        "gentamicin_heavy": min(eligible, key=lambda item: -sum(
            trace["selected_action"] == 4 for trace in item["decisions"]
        )),
    }
    for category, predicate in (
        ("ppo_greedy_disagreement", lambda item: any(
            trace["greedy_comparison"]["same_state"]
            and trace["greedy_comparison"]["selected_action"] != trace["selected_action"]
            for trace in item["decisions"]
        )),
        ("resistance_increasing", lambda item: any(
            trace["next_resistance_count"] > trace["current_resistance_count"] for trace in item["decisions"]
        )),
        ("resistance_reducing", lambda item: any(
            trace["next_resistance_count"] < trace["current_resistance_count"] for trace in item["decisions"]
        )),
    ):
        result[category] = next((item for item in eligible if predicate(item)), None)
    return result


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_trace_report(matched_directory, config_path, output_directory):
    matched_directory, output_directory = Path(matched_directory), Path(output_directory)
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"Trace output directory is not empty: {output_directory}")
    config = PPOConfig.from_json(config_path)
    source = json.loads((matched_directory / "config.json").read_text(encoding="utf-8"))
    if (source["scenario_id"], source["horizon"]) != (config.scenario_id, config.horizon):
        raise ValueError("Trace configuration must match the saved evaluation scenario and horizon.")
    output_directory.mkdir(parents=True, exist_ok=True)
    episodes, better_cipro, selected_gentamicin = [], [], []
    probability_cache = {}
    model_provenance = []
    state_groups = defaultdict(list)
    action_counts, step_groups, outcome_counts = Counter(), defaultdict(list), Counter()
    eligible_count = 0
    with (output_directory / "canonical_decisions.jsonl").open("w", encoding="utf-8") as trace_stream:
        for seed in source["evaluation_seed_bases_by_training_seed"]:
            seed = int(seed)
            directory = matched_directory / "models" / f"ppo_seed_{seed}"
            model_config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
            checkpoint = Path(model_config["ppo_model_path"])
            model = load_ppo_model(checkpoint, device=config.device)
            model_provenance.append({
                "training_seed": seed, "checkpoint": str(checkpoint),
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "trajectory_sha256": hashlib.sha256((directory / "raw_trajectories.json").read_bytes()).hexdigest(),
            })
            environment = make_training_environment(config)
            try:
                cases = json.loads((directory / "raw_trajectories.json").read_text(encoding="utf-8"))
                for case in cases:
                    episode, greedy = case["ppo"], case["greedy"]
                    live_observation, _ = environment.reset(
                        seed=episode["environment_seed"],
                        options={"initial_resistance_state": episode["initial_resistance_profile"]},
                    )
                    decision_rows = []
                    for step_index, step in enumerate(episode["steps"]):
                        observation = np.asarray(step["observation"], dtype=np.float32)
                        if not np.array_equal(live_observation, observation):
                            raise ValueError("Saved observations differ from full-episode replay.")
                        mask = environment.action_masks()
                        key = (seed, tuple(observation))
                        if key not in probability_cache:
                            probability_cache[key] = extract_masked_action_probabilities(model, observation, mask)
                        trace = build_decision_trace(
                            episode, step_index, probability_cache[key], environment,
                            case_id=case["case_id"], training_seed=seed,
                            checkpoint_identifier=str(checkpoint),
                        )
                        if trace["action_mask"] != mask.tolist():
                            raise ValueError("Canonical mask differs from the live environment mask.")
                        greedy_step = greedy["steps"][step_index] if step_index < len(greedy["steps"]) else None
                        same_state = bool(greedy_step and greedy_step["observation"][:7] == step["observation"][:7])
                        trace["greedy_comparison"] = {
                            "same_state": same_state,
                            "selected_action": greedy_step["action"] if same_state else None,
                            "selected_antibiotic_name": ANTIBIOTICS[greedy_step["action"]] if same_state else None,
                            "action_probabilities": [
                                (1 / sum(mask) if valid else 0.0) for valid in mask
                            ] if same_state else None,
                            "probability_kind": "uniform feasible-action selection, not learned scores",
                        }
                        trace["actual_remaining_burden"] = -sum(item["reward"] for item in episode["steps"][step_index:])
                        action_counts[trace["selected_antibiotic_name"]] += 1
                        state_groups[state_label(trace["current_state"])].append(trace)
                        step_groups[step_index].append(trace)
                        if mask[4]:
                            eligible_count += 1
                        if trace["selected_action"] == 4:
                            alternatives = counterfactual_one_step_actions(
                                environment, ResistanceState(tuple(trace["current_state"])),
                                step["info"]["transition_seed"], step_index,
                            )
                            for alternative in alternatives:
                                alternative["policy_probability"] = trace["policy_action_probabilities"][alternative["action"]]
                                alternative["remaining_feasible_actions"] = [
                                    ANTIBIOTICS[index] for index, value in enumerate(alternative["next_state"])
                                    if value == "S"
                                ]
                            trace["one_step_alternatives"] = alternatives
                            trace["gentamicin_category"] = (
                                "unchanged_unsupported_no_candidate"
                                if trace["transition_type"] == "unsupported_no_candidate" and trace["next_state"] == trace["current_state"]
                                else "resistance_increase" if trace["next_resistance_count"] > trace["current_resistance_count"]
                                else "resistance_decrease" if trace["next_resistance_count"] < trace["current_resistance_count"]
                                else "other_supported_transition"
                            )
                            outcome_counts[trace["gentamicin_category"]] += 1
                            selected_gentamicin.append(trace)
                            cipro = next((item for item in alternatives if item["action"] == 0), None)
                            if cipro and cipro["immediate_reward"] > trace["reward"] + 1e-12:
                                better_cipro.append({
                                    "decision": trace,
                                    "ciprofloxacin_alternative": cipro,
                                    "immediate_reward_difference_cipro_minus_gentamicin": cipro["immediate_reward"] - trace["reward"],
                                    "downstream_comparison": "not available: current evaluator has no same-state remaining-horizon counterfactual rollout API",
                                })
                        live_observation, reward, terminated, truncated, info = environment.step(step["action"])
                        if (
                            not np.array_equal(live_observation, np.asarray(step["next_observation"], dtype=np.float32))
                            or not np.isclose(reward, trace["reward"], atol=1e-10, rtol=0)
                            or terminated != step["terminated"] or truncated != step["truncated"]
                            or info != step["info"]
                        ):
                            raise ValueError("Trace instrumentation changed or disagrees with the original rollout.")
                        trace_stream.write(json.dumps(trace, allow_nan=False) + "\n")
                        decision_rows.append(trace)
                    episodes.append({
                        "episode_key": f"{seed}:{case['case_id']}", "case_id": case["case_id"],
                        "training_seed": seed, "initial_profile": episode["initial_resistance_profile"],
                        "evaluation_seed": episode["environment_seed"], "decisions": decision_rows,
                        "cumulative_resistance_burden": -(
                            sum(step["reward"] for step in episode["steps"])
                            + episode.get("terminal_reward_adjustment", 0.0)
                        ),
                    })
            finally:
                environment.close()
    representatives = select_representatives(episodes)
    state_rows = []
    for state, group in sorted(state_groups.items()):
        counts = Counter(trace["selected_antibiotic_name"] for trace in group)
        eligible = sum(trace["action_mask"][4] for trace in group)
        state_rows.append({
            "current_state": state, "visits": len(group), "gentamicin_feasible": eligible,
            "gentamicin_selected": counts["GENTAMICIN"],
            "gentamicin_frequency_when_feasible": counts["GENTAMICIN"] / eligible if eligible else None,
            **{f"selected_{name}": counts[name] for name in ANTIBIOTICS},
        })
    step_rows = [{
        "step": step, "decisions": len(group),
        "gentamicin_feasible": sum(trace["action_mask"][4] for trace in group),
        "gentamicin_selected": sum(trace["selected_action"] == 4 for trace in group),
    } for step, group in sorted(step_groups.items())]
    total = sum(action_counts.values())
    summary = {
        "decisions": total, "episodes": len(episodes), "action_counts": dict(action_counts),
        "gentamicin_selected": len(selected_gentamicin), "gentamicin_feasible": eligible_count,
        "gentamicin_overall_frequency": len(selected_gentamicin) / total,
        "gentamicin_frequency_when_feasible": len(selected_gentamicin) / eligible_count,
        "gentamicin_categories": dict(outcome_counts), "better_immediate_ciprofloxacin_decisions": len(better_cipro),
        "mean_policy_probability_when_gentamicin_selected": float(np.mean([
            trace["policy_action_probabilities"][4] for trace in selected_gentamicin
        ])),
        "representative_selection_rules": {
            "typical": "closest to median nonzero-length episode burden; episode_key breaks ties",
            "gentamicin_heavy": "highest Gentamicin action count; episode_key breaks ties",
            "ppo_greedy_disagreement": "first episode_key with a different action in the same matched state/step",
            "resistance_increasing": "first episode_key containing an increase",
            "resistance_reducing": "first episode_key containing a reduction",
        },
        "representatives": {name: item["episode_key"] if item else None for name, item in representatives.items()},
        "gentamicin_by_step": step_rows,
        "counterfactual_scope": "one-step only; no alternative continuation is inferred",
        "model_provenance": model_provenance,
    }
    for filename, data in (
        ("summary.json", summary), ("representative_trajectories.json", representatives),
        ("ciprofloxacin_immediate_advantage.json", better_cipro),
    ):
        (output_directory / filename).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    with (output_directory / "gentamicin_decisions.jsonl").open("w", encoding="utf-8") as stream:
        for trace in selected_gentamicin:
            stream.write(json.dumps(trace, allow_nan=False) + "\n")
    write_csv(output_directory / "state_action_distribution.csv", state_rows)
    write_csv(output_directory / "gentamicin_by_step.csv", step_rows)
    plots = generate_decision_trace_plots(representatives, action_counts, state_rows, step_rows, outcome_counts, output_directory / "plots")
    report = render_report(summary, representatives, better_cipro, plots)
    (output_directory / "report.md").write_text(report, encoding="utf-8")
    return summary


def render_report(summary, representatives, better_cipro, plots):
    lines = [
        "# Canonical Decision Trace Report", "",
        f"Validated {summary['decisions']} decisions in {summary['episodes']} episodes by full seeded replay and checkpoint probability extraction.",
        "Masks, action feasibility, transition labels, next states, rewards, and original rollout metadata were checked. No model, reward, transition, or training settings changed.", "",
        "## Gentamicin Findings", "",
        f"Selected {summary['gentamicin_selected']} times: {summary['gentamicin_overall_frequency']:.1%} overall, {summary['gentamicin_frequency_when_feasible']:.1%} when feasible.",
        f"Mean policy probability on selected Gentamicin: {summary['mean_policy_probability_when_gentamicin_selected']:.4f}. This is policy probability, not biological probability.",
        f"Recorded transition classifications: {summary['gentamicin_categories']}.", "",
        "Current-state frequencies and all seven selected-action counts are in state_action_distribution.csv. Feasible/masked status is explicit per action in every canonical decision; masked probabilities are zero.",
        "| Step | Gentamicin feasible | Selected | Selected when feasible |",
        "|---:|---:|---:|---:|",
        *[
            f"| {row['step']} | {row['gentamicin_feasible']} | {row['gentamicin_selected']} | "
            f"{row['gentamicin_selected'] / row['gentamicin_feasible']:.1%} |"
            for row in summary["gentamicin_by_step"] if row["gentamicin_feasible"]
        ], "",
        "## Ciprofloxacin Immediate Advantage", "",
        f"Independently identified {len(better_cipro)} decision occurrences (not necessarily distinct episodes or states).",
        "Each detailed record preserves the canonical decision, all feasible-action probabilities, same-seed ciprofloxacin outcome/reward/next state, and actual PPO remaining burden.",
        "The existing evaluator does not support arbitrary-state remaining-horizon counterfactual rollouts. This report does not implement a new counterfactual model: evidence remains one-step only.",
        "A favorable realized ciprofloxacin replay is not proof of a favorable expected action value: candidate outcomes depend on state/action and the realized seed.", "",
    ]
    lines.extend([
        "Examples selected by ascending training seed, case ID, and step (first five):", "",
        "| Seed/case/step | Current state | P(Gentamicin) | P(Ciprofloxacin) | Gentamicin outcome/reward/next | Ciprofloxacin outcome/reward/next |",
        "|---|---|---:|---:|---|---|",
    ])
    for comparison in sorted(better_cipro, key=lambda item: (
        item["decision"]["training_seed"], item["decision"]["case_id"], item["decision"]["step"],
    ))[:5]:
        trace = comparison["decision"]
        cipro = comparison["ciprofloxacin_alternative"]
        lines.append(
            f"| {trace['training_seed']}/{trace['case_id']}/{trace['step']} | {state_label(trace['current_state'])} | "
            f"{trace['policy_action_probabilities'][4]:.6f} | {trace['policy_action_probabilities'][0]:.6f} | "
            f"{trace['transition_type']}/{trace['reward']:.4f}/{state_label(trace['next_state'])} | "
            f"{cipro['transition_type']}/{cipro['immediate_reward']:.4f}/{cipro['next_state']} |"
        )
    lines.extend(["", "## Reproducible Representatives", ""])
    for category, episode in representatives.items():
        lines.extend([f"### {category}", ""])
        if episode is None:
            lines.append("No qualifying trajectory exists.")
            continue
        lines.extend([
            f"Selection rule: {summary['representative_selection_rules'][category]}. Case `{episode['episode_key']}`; burden {episode['cumulative_resistance_burden']:.4f}.", "",
            "| Step | Current state | Feasible actions | PPO choice | Policy probability | Outcome | Reward | Next state | Remaining options |",
            "|---:|---|---|---|---:|---|---:|---|---|",
        ])
        for trace in episode["decisions"]:
            lines.append(
                f"| {trace['step']} | {state_label(trace['current_state'])} | {', '.join(trace['feasible_actions'])} | "
                f"{trace['selected_antibiotic_name']} | {trace['policy_action_probabilities'][trace['selected_action']]:.6f} | "
                f"{trace['transition_type']} | {trace['reward']:.4f} | {state_label(trace['next_state'])} | "
                f"{', '.join(trace['remaining_feasible_actions'])} |"
            )
        same_states = [trace for trace in episode["decisions"] if trace["greedy_comparison"]["same_state"]]
        lines.extend(["", "Same-state Greedy decisions:"])
        for trace in same_states:
            comparison = trace["greedy_comparison"]
            lines.append(
                f"- Step {trace['step']}, {state_label(trace['current_state'])}: "
                f"PPO selects {trace['selected_antibiotic_name']}; Greedy selected "
                f"{comparison['selected_antibiotic_name']}. Greedy assigns each feasible action "
                f"probability {1 / sum(trace['action_mask']):.6f}; PPO probabilities are retained in the canonical trace."
            )
        lines.append("")
    lines.extend([
        "## Interpretation", "",
        "The records demonstrate a concentrated learned preference for an unchanged-state fallback, not demonstrated biological Gentamicin benefit. Tied immediate alternatives and favorable realized ciprofloxacin outcomes are inspectable; full-horizon alternative values remain unknown.",
        "State-frequency tables pool all checkpoints and visits; the complete observation also includes last action and time. Repeated state visits are not independent scientific samples.",
        "Greedy comparisons are attached only where the original matched Greedy trajectory encountered the exact same resistance state at the same step. Its probabilities are uniform over feasible actions, not learned scores.", "",
        "## Artifacts", "",
        "Canonical schema: canonical_decisions.jsonl (one decision per line); Gentamicin subset: gentamicin_decisions.jsonl; detailed immediate comparisons: ciprofloxacin_immediate_advantage.json.",
        "Representative selection and full sequences: representative_trajectories.json. Grouped results: state_action_distribution.csv and gentamicin_by_step.csv. Checkpoint/source hashes and counts: summary.json.", "",
        "## Visualizations", "",
    ])
    lines.extend(f"- {Path(path).name}" for path in plots)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Validate and visualize canonical PPO decisions from saved matched evaluations.")
    parser.add_argument("--matched-results-dir", required=True)
    parser.add_argument("--config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(generate_trace_report(args.matched_results_dir, args.config, args.output_dir), indent=2))


if __name__ == "__main__":
    main()