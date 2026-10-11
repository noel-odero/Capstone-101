"""Generate study-level figures from verified ppo_step9a_multiseed outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats as scipy_stats  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "experiments" / "results" / "ppo_step9a_multiseed"
PRIMARY_KEY = "cumulative_resistance_burden_greedy_minus_ppo"
PROFILE_CELL_COLUMN = "greedy_minus_ppo_burden"
SEED_COLUMN = "ppo_training_seed"
PROFILE_COLUMN = "profile_index"
EXPECTED_SEEDS = 20
EXPECTED_PROFILES = 128
EXPECTED_BASES_PER_CELL = 5
DPI = 160


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_t_interval(values: Sequence[float], interval: dict[str, Any]) -> None:
    arr = np.asarray(values, dtype=float)
    n = arr.size
    if n != interval["sample_count"]:
        raise ValueError("t-interval sample count does not match per-seed values")
    mean = arr.mean()
    half_width = scipy_stats.t.ppf(0.975, n - 1) * arr.std(ddof=1) / np.sqrt(n)
    expected = (mean - half_width, mean, mean + half_width)
    reported = (interval["lower_bound"], interval["mean"], interval["upper_bound"])
    if not np.allclose(expected, reported, rtol=0, atol=1e-9):
        raise ValueError("statistics.json t-interval does not match per-seed values")


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)


def _plot_primary_interval(stats: dict[str, Any], path: Path) -> None:
    primary = stats["primary_metric"]
    t_interval = primary["primary_t_interval"]
    boot = primary["bootstrap_sensitivity"]
    center = t_interval["mean"]
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.axhline(0, color="black", linewidth=1)
    ax.errorbar(
        0,
        center,
        yerr=[[center - t_interval["lower_bound"]], [t_interval["upper_bound"] - center]],
        fmt="o",
        capsize=8,
        label="Mean, 95% t-interval (df 19)",
    )
    ax.errorbar(
        1,
        center,
        yerr=[[center - boot["mean_lower"]], [boot["mean_upper"] - center]],
        fmt="s",
        capsize=8,
        label="Mean, 95% paired bootstrap (10,000 resamples)",
    )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["t-interval", "paired bootstrap"])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylabel("Greedy minus PPO cumulative resistance burden")
    ax.set_title("Primary outcome, 20 training seeds (positive favors PPO)")
    ax.legend(loc="lower left", fontsize=8)
    fig.text(
        0.5,
        0.01,
        "t-interval limitation reported in statistics.json: strong sample skew may make it unreliable.",
        ha="center",
        fontsize=7,
    )
    _save(fig, path)


def _plot_per_seed(rows: list[dict[str, Any]], path: Path) -> None:
    seeds = [row["training_seed"] for row in rows]
    values = np.array([row[PRIMARY_KEY] for row in rows], dtype=float)
    mean = values.mean()
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(range(len(seeds)), values, color="C0")
    ax.axhline(0, color="black", linewidth=1, label="Zero (no difference)")
    ax.axhline(mean, color="C3", linestyle="--", linewidth=1, label=f"Mean = {mean:.4f}")
    ax.set_xticks(range(len(seeds)))
    ax.set_xticklabels([str(seed) for seed in seeds], rotation=90, fontsize=7)
    ax.set_xlabel("Training seed")
    ax.set_ylabel("Greedy minus PPO cumulative resistance burden")
    ax.set_title(f"Paired difference per training seed: {int((values > 0).sum())} of {len(values)} positive")
    ax.legend(loc="upper right", fontsize=8)
    _save(fig, path)


def _plot_secondary(stats: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    names = list(stats["secondary_metrics"].keys())
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.axhline(0, color="black", linewidth=1)
    rng = np.random.default_rng(0)
    for index, name in enumerate(names):
        interval = stats["secondary_metrics"][name]["primary_t_interval"]
        values = np.array([row[f"{name}_greedy_minus_ppo"] for row in rows], dtype=float)
        _check_t_interval(values, interval)
        jitter = rng.uniform(-0.12, 0.12, size=values.size)
        ax.scatter(np.full(values.size, index) + jitter, values, color="C0", alpha=0.35, s=14)
        center = interval["mean"]
        ax.errorbar(
            index,
            center,
            yerr=[[center - interval["lower_bound"]], [interval["upper_bound"] - center]],
            fmt="o",
            color="C3",
            capsize=8,
            label="Mean with 95% t-interval" if index == 0 else None,
        )
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([name.replace("_", " ") for name in names], fontsize=8)
    ax.set_ylabel("Greedy minus PPO (per training seed)")
    ax.set_title("Secondary outcomes (positive favors PPO)")
    ax.legend(loc="best", fontsize=8)
    _save(fig, path)


def _load_profile_matrix(root: Path) -> tuple[list[int], list[int], np.ndarray]:
    cells: dict[tuple[int, int], list[float]] = {}
    with (root / "evaluation" / "raw_results.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (int(row[SEED_COLUMN]), int(row[PROFILE_COLUMN]))
            cells.setdefault(key, []).append(float(row[PROFILE_CELL_COLUMN]))
    seeds = sorted({seed for seed, _ in cells})
    profiles = sorted({profile for _, profile in cells})
    if len(seeds) != EXPECTED_SEEDS or len(profiles) != EXPECTED_PROFILES:
        raise ValueError("raw_results.csv seed or profile count does not match the protocol")
    matrix = np.empty((len(seeds), len(profiles)), dtype=float)
    for i, seed in enumerate(seeds):
        for j, profile in enumerate(profiles):
            values = cells[(seed, profile)]
            if len(values) != EXPECTED_BASES_PER_CELL:
                raise ValueError("raw_results.csv cell does not hold five evaluation seed bases")
            matrix[i, j] = np.mean(values)
    return seeds, profiles, matrix


def _plot_heatmap(seeds: list[int], matrix: np.ndarray, path: Path) -> None:
    limit = float(np.abs(matrix).max())
    fig, ax = plt.subplots(figsize=(10, 4.8))
    image = ax.imshow(matrix, aspect="auto", cmap="RdBu", vmin=-limit, vmax=limit, interpolation="nearest")
    ax.set_yticks(range(len(seeds)))
    ax.set_yticklabels([str(seed) for seed in seeds], fontsize=7)
    ax.set_xticks(range(0, matrix.shape[1], 16))
    ax.set_xlabel("Initial resistance profile index")
    ax.set_ylabel("Training seed")
    ax.set_title("Greedy minus PPO burden by seed and profile (mean of 5 evaluation seed bases; blue favors PPO)")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Greedy minus PPO cumulative burden")
    _save(fig, path)


def generate(root: Path = STUDY_ROOT) -> list[Path]:
    plots = root / "evaluation" / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    stats = json.loads((root / "statistics.json").read_text(encoding="utf-8"))
    rows = stats["per_training_seed"]
    if len(rows) != EXPECTED_SEEDS:
        raise ValueError("statistics.json does not contain 20 training seeds")
    _check_t_interval([row[PRIMARY_KEY] for row in rows], stats["primary_metric"]["primary_t_interval"])

    outputs = {
        "primary_burden_interval.png": lambda p: _plot_primary_interval(stats, p),
        "per_seed_paired_difference.png": lambda p: _plot_per_seed(rows, p),
        "secondary_outcomes_interval.png": lambda p: _plot_secondary(stats, rows, p),
    }
    seeds, _, matrix = _load_profile_matrix(root)
    outputs["seed_profile_difference_heatmap.png"] = lambda p: _plot_heatmap(seeds, matrix, p)

    written: list[Path] = []
    for name, render in outputs.items():
        path = plots / name
        render(path)
        written.append(path)

    inputs = [
        root / "statistics.json",
        root / "evaluation" / "raw_results.csv",
        root / "evaluation" / "config.json",
        root / "evaluation" / "summary.json",
        Path(__file__).resolve(),
    ]
    provenance = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs_sha256": {str(path.relative_to(REPO_ROOT)): _sha256(path) for path in inputs},
        "outputs_sha256": {path.name: _sha256(path) for path in written},
        "notes": [
            "Heatmap is seed by profile mean difference from raw_results.csv; trajectory heatmap not available from canonical outputs.",
            "Intervals verified against per-seed values before plotting.",
        ],
    }
    (plots / "study_figures_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return written


if __name__ == "__main__":
    for output in generate():
        print(output)
