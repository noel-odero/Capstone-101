from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from simulation.resistance_state import ANTIBIOTICS


def _save_figure(figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def generate_decision_trace_plots(
    representatives, action_counts, state_rows, step_rows, outcome_counts, output_directory,
) -> list[str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved = []
    total = sum(action_counts.values())
    figure, axis = plt.subplots(figsize=(10, 4))
    axis.bar(ANTIBIOTICS, [action_counts[name] / total for name in ANTIBIOTICS])
    axis.set(ylabel="PPO action proportion", title="Canonical trace action distribution")
    axis.tick_params(axis="x", labelrotation=35)
    path = output_directory / "overall_action_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axes = plt.subplots(1, 3, figsize=(16, 5))
    eligible_states = [row for row in state_rows if row["gentamicin_feasible"]]
    axes[0].bar(range(len(eligible_states)), [row["gentamicin_frequency_when_feasible"] for row in eligible_states])
    axes[0].set(xlabel="Current state (sorted; mapping in CSV)", ylabel="Gentamicin fraction when feasible", ylim=(0, 1), title="By resistance profile")
    axes[1].bar([row["step"] for row in step_rows], [
        row["gentamicin_selected"] / row["gentamicin_feasible"] if row["gentamicin_feasible"] else 0
        for row in step_rows
    ])
    axes[1].set(xlabel="Treatment step", ylim=(0, 1), title="Conditional on feasibility, by step")
    axes[2].bar(range(len(outcome_counts)), list(outcome_counts.values()))
    axes[2].set_xticks(range(len(outcome_counts)))
    axes[2].set_xticklabels(list(outcome_counts), rotation=25, ha="right")
    axes[2].set(ylabel="Selected Gentamicin decisions", title="Recorded outcome category")
    path = output_directory / "gentamicin_conditional_frequencies.png"
    _save_figure(figure, path)
    saved.append(str(path))

    for category, episode in representatives.items():
        if episode is None:
            continue
        decisions = episode["decisions"]
        counts = [sum(episode["initial_profile"])] + [trace["next_resistance_count"] for trace in decisions]
        for suffix, values, ylabel in (
            ("resistance_trajectory", counts, "Resistant antibiotics"),
            ("effective_options", [7 - count for count in counts], "Feasible antibiotics"),
        ):
            figure, axis = plt.subplots()
            axis.plot(range(len(values)), values, marker="o")
            axis.set(xlabel="State time point", ylabel=ylabel, ylim=(-.2, 7.2), title=f"{category}: {episode['episode_key']}")
            path = output_directory / f"{category}_{suffix}.png"
            _save_figure(figure, path)
            saved.append(str(path))
        figure, axis = plt.subplots(figsize=(10, 3))
        chosen = [trace["selected_action"] for trace in decisions]
        axis.scatter([trace["step"] for trace in decisions], chosen, marker="s", s=120)
        axis.set(xlabel="Treatment step", yticks=range(7), yticklabels=ANTIBIOTICS, ylim=(-.5, 6.5), title=f"{category}: treatment sequence")
        path = output_directory / f"{category}_treatment_sequence.png"
        _save_figure(figure, path)
        saved.append(str(path))
        figure, axes = plt.subplots(1, 2, figsize=(13, 5))
        first = decisions[0]
        last = decisions[-1]
        for axis, trace in zip(axes, (first, last)):
            positions = np.arange(7)
            axis.bar(positions, trace["policy_action_probabilities"], color=[
                "#357c98" if feasible else "#b8b8b8" for feasible in trace["action_mask"]
            ])
            for position, feasible in enumerate(trace["action_mask"]):
                if not feasible:
                    axis.text(position, .04, "masked", rotation=90, ha="center", fontsize=8)
            axis.set(xticks=positions, xticklabels=ANTIBIOTICS, ylim=(0, 1), ylabel="Policy probability", title=f"Step {trace['step']}; selected {trace['selected_antibiotic_name']}")
            axis.tick_params(axis="x", labelrotation=70)
        path = output_directory / f"{category}_policy_distributions.png"
        _save_figure(figure, path)
        saved.append(str(path))
    return saved


def generate_transition_sensitivity_plots(rows, paired_conditions, audit, output_directory) -> list[str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved = []
    condition_labels = ["Uniform supported", "Deterministic first"]
    condition_ids = ["REF_UNIFORM_SUPPORTED", "REF_DETERMINISTIC_FIRST_SUPPORTED"]
    means = {}
    for condition in condition_ids:
        for policy in ("ppo", "greedy"):
            values = [row["cumulative_resistance_burden"] for row in rows if row["condition"] == condition and row["policy"] == policy]
            means[(condition, policy)] = float(np.mean(values))

    figure, axis = plt.subplots()
    positions = np.arange(len(condition_ids))
    width = .34
    axis.bar(positions - width / 2, [means[(condition, "ppo")] for condition in condition_ids], width, label="PPO")
    axis.bar(positions + width / 2, [means[(condition, "greedy")] for condition in condition_ids], width, label="Greedy")
    axis.set(xticks=positions, xticklabels=condition_labels, ylabel="Mean cumulative normalized resistance burden", title="PPO and Greedy by transition-selection rule")
    axis.legend()
    path = output_directory / "burden_by_condition.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    for condition_index, condition in enumerate(condition_ids):
        by_key = {}
        for row in rows:
            if row["condition"] == condition:
                by_key.setdefault((row["training_seed"], row["evaluation_seed_base"], row["profile_index"]), {})[row["policy"]] = row["cumulative_resistance_burden"]
        delta = [value["greedy"] - value["ppo"] for value in by_key.values()]
        axis.bar(condition_index, float(np.mean(delta)), width=.55, color=("#46798f", "#bf6d4b")[condition_index])
        axis.scatter(np.full(len(delta), condition_index) + np.linspace(-.22, .22, len(delta)), delta, alpha=.08, s=7)
    axis.axhline(0, color="#444444", linewidth=.8)
    axis.set(xticks=positions, xticklabels=condition_labels, ylabel="Greedy minus PPO burden", title="Matched PPO-Greedy burden difference")
    path = output_directory / "ppo_greedy_difference_by_condition.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    for condition_index, condition in enumerate(condition_ids):
        by_key = {}
        for row in rows:
            if row["condition"] == condition:
                by_key.setdefault((row["training_seed"], row["evaluation_seed_base"], row["profile_index"]), {})[row["policy"]] = row["cumulative_resistance_burden"]
        gaps = [pair["greedy"] - pair["ppo"] for pair in by_key.values()]
        axis.hist(gaps, bins=30, alpha=.5, label=condition_labels[condition_index])
    axis.set(xlabel="Greedy minus PPO burden per matched case", ylabel="Matched trajectories", title="Paired case-level burden differences")
    axis.legend()
    path = output_directory / "paired_burden_difference_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots(figsize=(11, 4))
    x = np.arange(len(ANTIBIOTICS))
    width = .2
    styles = ((condition_ids[0], "ppo"), (condition_ids[0], "greedy"), (condition_ids[1], "ppo"), (condition_ids[1], "greedy"))
    for index, (condition, policy) in enumerate(styles):
        item = audit[f"{condition}:{policy}"]["outcome_counts_by_antibiotic"]
        rates = [item[name]["unsupported_fraction"] or 0.0 for name in ANTIBIOTICS]
        axis.bar(x + (index - 1.5) * width, rates, width, label=f"{condition_labels[condition_ids.index(condition)]}, {policy.upper()}")
    axis.set(xticks=x, xticklabels=ANTIBIOTICS, ylabel="Unsupported no-candidate fraction", ylim=(0, 1), title="Unsupported outcomes by antibiotic")
    axis.tick_params(axis="x", labelrotation=35)
    axis.legend()
    path = output_directory / "unsupported_rate_by_antibiotic.png"
    _save_figure(figure, path)
    saved.append(str(path))
    return saved


def generate_reference_benchmark_plots(rows, examples, output_directory) -> list[str]:
    from collections import Counter, defaultdict

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved = []
    groups = defaultdict(list)
    for row in rows:
        groups[row["step"]].append(row)
    steps = sorted(groups)
    figure, axis = plt.subplots()
    axis.bar(steps, [np.mean([row["selects_exact_optimal_action"] for row in groups[step]]) for step in steps])
    axis.set(xlabel="Elapsed treatment step", ylabel="Exact-optimal action proportion", ylim=(0, 1), title="Common-reference action agreement (ties included)")
    path = output_directory / "agreement_by_step.png"
    _save_figure(figure, path)
    saved.append(str(path))

    states = sorted({row["state"] for row in rows})
    figure, axis = plt.subplots(figsize=(13, 4))
    axis.bar(range(len(states)), [np.mean([row["selects_exact_optimal_action"] for row in rows if row["state"] == state]) for state in states])
    axis.set(xlabel="Resistance profile (lexicographic order; mapping in CSV)", ylabel="Exact-optimal action proportion", ylim=(0, 1), title="Agreement by resistance profile")
    path = output_directory / "agreement_by_state.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    gaps = [row["reference_action_value_gap"] for row in rows]
    axis.hist(gaps, bins=35)
    axis.set(xlabel="V*(s) - Q*(s, PPO action)", ylabel="Observation contexts", title="Deterministic-reference action gaps")
    path = output_directory / "reference_gap_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    axis.plot(steps, [np.mean([row["reference_action_value_gap"] for row in groups[step]]) for step in steps], marker="o", label="Mean")
    axis.plot(steps, [max(row["reference_action_value_gap"] for row in groups[step]) for step in steps], marker="s", label="Maximum")
    axis.set(xlabel="Elapsed treatment step", ylabel="Reference action gap", title="Reference gap by elapsed step")
    axis.legend()
    path = output_directory / "reference_gap_by_step.png"
    _save_figure(figure, path)
    saved.append(str(path))

    gentamicin = [row for row in rows if row["ppo_action"] == 4]
    figure, axis = plt.subplots()
    axis.scatter([row["ppo_gentamicin_probability"] for row in gentamicin], [row["reference_action_value_gap"] for row in gentamicin], alpha=.25, s=8)
    axis.set(xlabel="Masked PPO Gentamicin probability", ylabel="Reference action gap", title="Selected Gentamicin: preference versus reference optimality")
    path = output_directory / "gentamicin_probability_vs_gap.png"
    _save_figure(figure, path)
    saved.append(str(path))

    traces = {name: example["trace"] if example is not None else None for name, example in examples.items()}
    action_counts = Counter(row["ppo_antibiotic"] for row in rows)
    step_rows = [{
        "step": step,
        "gentamicin_feasible": sum("GENTAMICIN" in row["feasible_actions"] for row in group),
        "gentamicin_selected": sum(row["ppo_action"] == 4 for row in group),
    } for step, group in sorted(groups.items())]
    state_rows = []
    for state in states:
        group = [row for row in rows if row["state"] == state]
        feasible = sum("GENTAMICIN" in row["feasible_actions"] for row in group)
        state_rows.append({
            "gentamicin_feasible": feasible,
            "gentamicin_frequency_when_feasible": sum(row["ppo_action"] == 4 for row in group) / feasible if feasible else 0,
        })
    saved.extend(generate_decision_trace_plots(
        traces, action_counts, state_rows, step_rows,
        Counter(row["ppo_reference_transition_type"] for row in gentamicin), output_directory,
    ))
    return saved


def generate_training_plots(
    training_episode_path: str | Path,
    output_directory: str | Path,
) -> list[str]:
    training_episode_path = Path(training_episode_path)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    if not training_episode_path.exists():
        return []
    with training_episode_path.open(encoding="utf-8") as episode_file:
        episodes = json.load(episode_file)
    if not episodes:
        return []

    saved = []
    timesteps = [episode["timesteps"] for episode in episodes]
    rewards = [episode["cumulative_reward"] for episode in episodes]
    burdens = [episode["cumulative_resistance_burden"] for episode in episodes]
    window = min(10, len(episodes))
    reward_smooth = np.convolve(rewards, np.ones(window) / window, mode="valid")
    burden_smooth = np.convolve(burdens, np.ones(window) / window, mode="valid")
    smooth_steps = timesteps[window - 1:]

    figure, axis = plt.subplots()
    axis.scatter(timesteps, rewards, alpha=0.35, label="Episode return")
    axis.plot(smooth_steps, reward_smooth, linewidth=2, label=f"Rolling mean ({window})")
    axis.set(xlabel="Training timesteps", ylabel="Episode return", title="PPO training return")
    axis.legend()
    path = output_directory / "training_reward.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    axis.scatter(timesteps, burdens, alpha=0.35, label="Episode burden")
    axis.plot(smooth_steps, burden_smooth, linewidth=2, label=f"Rolling mean ({window})")
    axis.set(xlabel="Training timesteps", ylabel="Cumulative resistance burden", title="Training resistance burden")
    axis.legend()
    path = output_directory / "training_resistance_burden.png"
    _save_figure(figure, path)
    saved.append(str(path))

    action_counts = np.asarray([episode["action_counts"] for episode in episodes], dtype=float).sum(axis=0)
    figure, axis = plt.subplots(figsize=(9, 4))
    axis.bar(ANTIBIOTICS, action_counts)
    axis.set(xlabel="Antibiotic", ylabel="Actions selected", title="Training action distribution")
    axis.tick_params(axis="x", labelrotation=35)
    path = output_directory / "training_action_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    figure, axis = plt.subplots()
    axis.plot(timesteps, [episode["treatment_steps"] for episode in episodes], marker="o")
    axis.set(xlabel="Training timesteps", ylabel="Treatment steps", title="Training episode lengths")
    path = output_directory / "training_episode_length.png"
    _save_figure(figure, path)
    saved.append(str(path))
    return saved


def generate_evaluation_plots(result: dict[str, Any], output_directory: str | Path) -> list[str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    episodes = result["episodes"]
    saved = []

    counts = result["summary"]["final_resistant_count_distribution"]
    figure, axis = plt.subplots()
    values = list(range(len(ANTIBIOTICS) + 1))
    axis.bar(values, [counts[str(value)] for value in values])
    axis.set(xticks=values, xlabel="Resistant antibiotics at episode end", ylabel="Episodes", title="Final resistance distribution")
    path = output_directory / "final_resistance_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    action_counts = result["summary"]["action_counts"]
    figure, axis = plt.subplots(figsize=(9, 4))
    axis.bar(list(action_counts), list(action_counts.values()))
    axis.set(xlabel="Antibiotic", ylabel="Actions selected", title="Evaluation action distribution")
    axis.tick_params(axis="x", labelrotation=35)
    path = output_directory / "evaluation_action_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    nonempty = [episode for episode in episodes if episode["steps"]]
    if not nonempty:
        return saved
    ranked = sorted(nonempty, key=lambda episode: episode["cumulative_resistance_burden"])
    chosen = [ranked[0]]
    if len(ranked) > 2:
        chosen.append(ranked[len(ranked) // 2])
    if len(ranked) > 1:
        chosen.append(ranked[-1])

    figure, axis = plt.subplots()
    for episode in chosen:
        resistance_counts = [
            sum(episode["initial_resistance_profile"])
        ] + [step["next_resistance_count"] for step in episode["steps"]]
        axis.plot(range(len(resistance_counts)), resistance_counts, marker="o", label=f"Episode {episode['episode_id']}")
    axis.set(xlabel="Treatment step", ylabel="Resistant antibiotics", title="Example resistance trajectories", ylim=(-0.2, 7.2))
    axis.legend()
    path = output_directory / "example_resistance_trajectories.png"
    _save_figure(figure, path)
    saved.append(str(path))

    heatmap_episode = max(nonempty, key=lambda episode: len(episode["steps"]))
    profiles = [heatmap_episode["initial_resistance_profile"]] + [
        [int(value == "R") for value in step["next_state"]]
        for step in heatmap_episode["steps"]
    ]
    matrix = np.asarray(profiles, dtype=int).T
    figure, axis = plt.subplots(figsize=(max(7, matrix.shape[1]), 5))
    axis.imshow(matrix, aspect="auto", interpolation="nearest", cmap=ListedColormap(["#4b9b73", "#c95050"]), vmin=0, vmax=1)
    axis.set(
        yticks=range(len(ANTIBIOTICS)),
        yticklabels=ANTIBIOTICS,
        xticks=range(matrix.shape[1]),
        xticklabels=range(matrix.shape[1]),
        xlabel="State time point",
        title=f"Resistance-state heatmap, episode {heatmap_episode['episode_id']} (green=S, red=R)",
    )
    path = output_directory / "resistance_state_heatmap.png"
    _save_figure(figure, path)
    saved.append(str(path))
    return saved


def generate_matched_comparison_plots(
    case_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
    output_directory: str | Path,
) -> list[str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved = []

    ppo_burden = [row["ppo_cumulative_resistance_burden"] for row in case_rows]
    greedy_burden = [row["greedy_cumulative_resistance_burden"] for row in case_rows]
    low = min(ppo_burden + greedy_burden)
    high = max(ppo_burden + greedy_burden)
    figure, axis = plt.subplots()
    axis.scatter(ppo_burden, greedy_burden, alpha=0.35, s=12)
    axis.plot([low, high], [low, high], linestyle="--", color="black", linewidth=1)
    axis.set(
        xlabel="PPO cumulative resistance burden",
        ylabel="Greedy cumulative resistance burden",
        title="Matched resistance burden by case",
    )
    path = output_directory / "matched_burden_scatter.png"
    _save_figure(figure, path)
    saved.append(str(path))

    profile_indices = [row["profile_index"] for row in profile_rows]
    profile_differences = [row["greedy_minus_ppo_burden"] for row in profile_rows]
    figure, axis = plt.subplots(figsize=(12, 4))
    axis.axhline(0.0, color="black", linewidth=1)
    axis.plot(profile_indices, profile_differences, marker=".", linewidth=1)
    axis.set(
        xlabel="Canonical initial-profile index",
        ylabel="Greedy burden - PPO burden",
        title="Matched mean burden difference by initial profile (positive favors PPO)",
    )
    path = output_directory / "matched_burden_by_profile.png"
    _save_figure(figure, path)
    saved.append(str(path))

    paired_differences = [row["greedy_minus_ppo_burden"] for row in case_rows]
    figure, axis = plt.subplots()
    axis.hist(paired_differences, bins=25, edgecolor="white")
    axis.axvline(0.0, color="black", linewidth=1)
    axis.axvline(float(np.mean(paired_differences)), color="#c95050", linewidth=2, label="Mean")
    axis.set(
        xlabel="Greedy burden - PPO burden",
        ylabel="Matched cases",
        title="Distribution of paired resistance-burden differences",
    )
    axis.legend()
    path = output_directory / "matched_burden_difference_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))
    return saved


def generate_gentamicin_audit_plots(
    *,
    overall_action_frequencies: dict[str, dict[str, float]],
    state_rows: list[dict],
    representative_traces: dict,
    action_names: tuple[str, ...],
    output_directory: str | Path,
) -> list[str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved = []

    positions = np.arange(len(action_names))
    width = 0.38
    figure, axis = plt.subplots(figsize=(11, 5))
    axis.bar(
        positions - width / 2,
        [overall_action_frequencies["ppo"][name] for name in action_names],
        width,
        label="PPO",
    )
    axis.bar(
        positions + width / 2,
        [overall_action_frequencies["greedy"][name] for name in action_names],
        width,
        label="Greedy",
    )
    axis.set(
        xticks=positions,
        xticklabels=action_names,
        xlabel="Antibiotic",
        ylabel="Action proportion",
        title="Overall action-selection distribution",
    )
    axis.tick_params(axis="x", labelrotation=35)
    axis.legend()
    path = output_directory / "gentamicin_overall_action_distribution.png"
    _save_figure(figure, path)
    saved.append(str(path))

    state_by_index = {row["profile_index"]: row for row in state_rows}
    x_values = []
    y_values = []
    counts = []
    for profile_index in range(2**len(action_names)):
        row = state_by_index.get(profile_index)
        if row is None or row["gentamicin_feasible_count"] == 0:
            continue
        x_values.append(profile_index)
        y_values.append(row["gentamicin_selection_frequency_when_feasible"])
        counts.append(row["gentamicin_feasible_count"])
    figure, axis = plt.subplots(figsize=(13, 5))
    scatter = axis.scatter(x_values, y_values, c=counts, cmap="viridis", s=28)
    axis.set(
        xlabel="Current resistance-profile index (canonical binary order)",
        ylabel="Gentamicin selection frequency when feasible",
        title="Gentamicin frequency by current resistance state",
        ylim=(-0.03, 1.03),
    )
    figure.colorbar(scatter, ax=axis, label="PPO decisions in this state")
    path = output_directory / "gentamicin_frequency_by_state.png"
    _save_figure(figure, path)
    saved.append(str(path))

    selected = representative_traces["gentamicin_selected"]
    not_selected = representative_traces["gentamicin_feasible_but_not_selected"]
    examples = [
        ("Gentamicin selected", row)
        for row in selected[:3]
    ] + [
        ("Gentamicin feasible, not selected", row)
        for row in not_selected[:3]
    ]
    if examples:
        figure, axes = plt.subplots(2, 3, figsize=(16, 8), squeeze=False)
        flat_axes = axes.ravel()
        for axis, (category, row) in zip(flat_axes, examples):
            probabilities = [row["action_probabilities"][name] for name in action_names]
            colors = ["#c95050" if name == "GENTAMICIN" else "#4b789b" for name in action_names]
            axis.bar(range(len(action_names)), probabilities, color=colors)
            axis.set_xticks(range(len(action_names)))
            axis.set_xticklabels([name[:3] for name in action_names], rotation=35)
            axis.set_ylim(0, 1)
            axis.set_ylabel("Policy probability")
            axis.set_title(
                f"{category}\n{row['current_state']} step {row['treatment_step']} "
                f"P(GEN)={row['action_probabilities']['GENTAMICIN']:.2f}\n"
                f"{row['selected_antibiotic']} -> {row['next_state']} ({row['actual_transition_type']})"
            )
        for axis in flat_axes[len(examples):]:
            axis.set_visible(False)
        path = output_directory / "gentamicin_representative_decisions.png"
        _save_figure(figure, path)
        saved.append(str(path))
    return saved
