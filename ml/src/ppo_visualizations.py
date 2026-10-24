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
