from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Discrete
from sb3_contrib import MaskablePPO

from ml.src.multi_seed_evaluation import MultiSeedResult, run_multi_seed_evaluation
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, load_ppo_model, make_training_environment
from ml.src.ppo_visualizations import generate_matched_comparison_plots
from ml.src.statistical_comparison import match_run_pairs, paired_bootstrap_interval
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from ml.src.greedy_policy import GreedyPolicy


class MaskablePPOObservationPolicy:
    """Adapt a loaded MaskablePPO model to the existing observation-policy API."""

    def __init__(self, action_space: Discrete, model: MaskablePPO, seed: int | None = None):
        if not isinstance(action_space, Discrete):
            raise TypeError("PPO observation policy requires a Discrete action space.")
        if action_space.start != 0 or action_space.n != len(ANTIBIOTICS):
            raise ValueError("PPO action space must match the canonical seven actions.")
        self.action_space = action_space
        self.model = model

    def select_action(self, observation: np.ndarray) -> int:
        observation = np.asarray(observation, dtype=np.float32)
        if observation.shape != (15,) or not np.isfinite(observation).all():
            raise ValueError("PPO requires a finite 15-value observation.")
        action_mask = observation[:len(ANTIBIOTICS)] == 0
        if not action_mask.any():
            raise ValueError("A terminal all-resistant observation has no feasible action.")
        action, _ = self.model.predict(
            observation,
            deterministic=True,
            action_masks=action_mask,
        )
        action = int(np.asarray(action).reshape(-1)[0])
        if not self.action_space.contains(action) or not action_mask[action]:
            raise RuntimeError("MaskablePPO selected an infeasible action.")
        return action


def _case_id(evaluation_seed_base: int, profile_index: int) -> str:
    return f"seed_{evaluation_seed_base}_profile_{profile_index:03d}"


def _episode_burden(episode) -> float:
    return -episode.cumulative_reward


def _paired_difference(greedy: float | None, ppo: float | None) -> float | None:
    if greedy is None or ppo is None:
        return None
    return greedy - ppo


def _episode_record(episode) -> dict[str, Any]:
    return asdict(episode)


def _training_config_for_checkpoint(model_path: Path, config: PPOConfig) -> dict[str, Any]:
    run_directory = model_path.parent.parent if model_path.parent.name == "checkpoints" else model_path.parent
    config_path = run_directory / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Checkpoint training config is missing: {config_path}")
    with config_path.open(encoding="utf-8") as config_file:
        training_config = json.load(config_file)
    if training_config.get("scenario_id") != config.scenario_id:
        raise ValueError("Checkpoint training scenario does not match matched evaluation.")
    if training_config.get("horizon") != config.horizon:
        raise ValueError("Checkpoint training horizon does not match matched evaluation.")
    return training_config


def _paired_rows(ppo_result: MultiSeedResult, greedy_result: MultiSeedResult) -> tuple[list[dict], list[dict]]:
    matched = match_run_pairs(ppo_result, greedy_result)
    case_rows = []
    trajectory_rows = []
    expected_profiles = ppo_result.initial_resistance_profiles

    for run_pair in matched.pairs:
        ppo_run = run_pair.run_a
        greedy_run = run_pair.run_b
        if ppo_run.environment_base_seed != greedy_run.environment_base_seed:
            raise ValueError("Matched policies have different environment seed schedules.")
        if ppo_run.policy_base_seed != greedy_run.policy_base_seed:
            raise ValueError("Matched policies have different policy seed schedules.")
        if ppo_run.evaluation.scenario_id != greedy_run.evaluation.scenario_id:
            raise ValueError("Matched policies have different transition scenarios.")
        if ppo_run.evaluation.horizon != greedy_run.evaluation.horizon:
            raise ValueError("Matched policies have different episode horizons.")

        for profile_index, (ppo_episode, greedy_episode) in enumerate(zip(
            ppo_run.evaluation.episodes,
            greedy_run.evaluation.episodes,
        )):
            if profile_index >= len(expected_profiles):
                raise ValueError("Evaluation returned more episodes than initial profiles.")
            expected_profile = expected_profiles[profile_index]
            for episode in (ppo_episode, greedy_episode):
                if episode.episode_id != profile_index:
                    raise ValueError("Episode ordering does not match the configured profile ordering.")
                if episode.initial_resistance_profile != expected_profile:
                    raise ValueError("Matched policy episode began from a different initial profile.")
            if ppo_episode.environment_seed != greedy_episode.environment_seed:
                raise ValueError("Matched policy episodes have different environment seeds.")
            common_steps = min(len(ppo_episode.steps), len(greedy_episode.steps))
            for step_index in range(common_steps):
                ppo_info = ppo_episode.steps[step_index].info
                greedy_info = greedy_episode.steps[step_index].info
                if ppo_info.get("transition_seed") != greedy_info.get("transition_seed"):
                    raise ValueError(
                        "Matched episodes do not share the same per-step transition seed stream."
                    )

            ppo_metrics = ppo_run.metrics.episodes[profile_index]
            greedy_metrics = greedy_run.metrics.episodes[profile_index]
            profile_label = "".join("R" if value else "S" for value in expected_profile)
            evaluation_seed = ppo_episode.environment_seed
            case_id = _case_id(run_pair.environment_base_seed, profile_index)
            ppo_burden = _episode_burden(ppo_episode)
            greedy_burden = _episode_burden(greedy_episode)
            ppo_final_resistant = sum(ppo_episode.final_resistance_profile)
            greedy_final_resistant = sum(greedy_episode.final_resistance_profile)

            row = {
                "case_id": case_id,
                "run_id": run_pair.run_a.run_id,
                "profile_index": profile_index,
                "initial_state": profile_label,
                "initial_resistance_profile": list(expected_profile),
                "evaluation_seed_base": run_pair.environment_base_seed,
                "evaluation_seed": evaluation_seed,
                "ppo_policy_seed": ppo_episode.policy_seed,
                "greedy_policy_seed": greedy_episode.policy_seed,
                "ppo_episode_length": ppo_metrics.treatment_steps,
                "greedy_episode_length": greedy_metrics.treatment_steps,
                "ppo_cumulative_resistance_burden": ppo_burden,
                "greedy_cumulative_resistance_burden": greedy_burden,
                "greedy_minus_ppo_burden": greedy_burden - ppo_burden,
                "ppo_final_resistant_antibiotics": ppo_final_resistant,
                "greedy_final_resistant_antibiotics": greedy_final_resistant,
                "greedy_minus_ppo_final_resistant": greedy_final_resistant - ppo_final_resistant,
                "ppo_resistance_emergence_events": ppo_metrics.resistance_emergence_events,
                "greedy_resistance_emergence_events": greedy_metrics.resistance_emergence_events,
                "greedy_minus_ppo_resistance_emergence_events": (
                    greedy_metrics.resistance_emergence_events - ppo_metrics.resistance_emergence_events
                ),
                "ppo_resistance_emergence_rate": ppo_metrics.resistance_emergence_rate,
                "greedy_resistance_emergence_rate": greedy_metrics.resistance_emergence_rate,
                "greedy_minus_ppo_resistance_emergence_rate": _paired_difference(
                    greedy_metrics.resistance_emergence_rate,
                    ppo_metrics.resistance_emergence_rate,
                ),
                "ppo_treatment_effectiveness_rate": ppo_metrics.treatment_effectiveness_rate,
                "greedy_treatment_effectiveness_rate": greedy_metrics.treatment_effectiveness_rate,
                "greedy_minus_ppo_treatment_effectiveness_rate": _paired_difference(
                    greedy_metrics.treatment_effectiveness_rate,
                    ppo_metrics.treatment_effectiveness_rate,
                ),
                "ppo_cumulative_reward": ppo_episode.cumulative_reward,
                "greedy_cumulative_reward": greedy_episode.cumulative_reward,
                "greedy_minus_ppo_reward": greedy_episode.cumulative_reward - ppo_episode.cumulative_reward,
                "ppo_termination_reason": ppo_episode.termination_reason,
                "greedy_termination_reason": greedy_episode.termination_reason,
            }
            case_rows.append(row)
            trajectory_rows.append({
                "case_id": case_id,
                "initial_state": profile_label,
                "evaluation_seed": evaluation_seed,
                "ppo": _episode_record(ppo_episode),
                "greedy": _episode_record(greedy_episode),
            })

    expected_case_count = len(ppo_result.runs) * len(expected_profiles)
    if len(case_rows) != expected_case_count:
        raise ValueError("PPO/Greedy case collections are incomplete or misaligned.")
    if len({row["case_id"] for row in case_rows}) != expected_case_count:
        raise ValueError("Matched case IDs are not unique.")
    return case_rows, trajectory_rows


def _summary(case_rows: list[dict]) -> dict[str, Any]:
    metric_names = (
        "cumulative_resistance_burden",
        "final_resistant_antibiotics",
        "resistance_emergence_events",
        "resistance_emergence_rate",
        "treatment_effectiveness_rate",
        "episode_length",
        "cumulative_reward",
    )
    policy_summary = {}
    for policy in ("ppo", "greedy"):
        policy_summary[policy] = {}
        for metric in metric_names:
            key = f"{policy}_{metric}"
            values = [row[key] for row in case_rows if row[key] is not None]
            policy_summary[policy][metric] = mean(values) if values else None
    difference_summary = {}
    for key in (
        "greedy_minus_ppo_burden",
        "greedy_minus_ppo_final_resistant",
        "greedy_minus_ppo_resistance_emergence_events",
        "greedy_minus_ppo_resistance_emergence_rate",
        "greedy_minus_ppo_treatment_effectiveness_rate",
        "greedy_minus_ppo_reward",
    ):
        values = [row[key] for row in case_rows if row[key] is not None]
        difference_summary[key] = mean(values) if values else None
    return {
        "matched_case_count": len(case_rows),
        "policy_metrics": policy_summary,
        "paired_difference_means": difference_summary,
        "difference_direction": "Greedy minus PPO; positive burden/final-resistance/emergence differences favor PPO.",
        "statistical_tests": "not performed",
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("No matched case rows to write.")
    with path.open("w", newline="", encoding="utf-8") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: Sequence[float | int | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return mean(valid) if valid else None


def _standard_deviation(values: Sequence[float | int | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return stdev(valid) if len(valid) > 1 else None


def _metric_ensemble_summary(
    rows: list[dict[str, Any]],
    *,
    ppo_seed_means: dict[int, list[dict[str, float | None]]],
    config: PPOConfig,
) -> dict[str, Any]:
    definitions = {
        "cumulative_resistance_burden": (
            "ppo_cumulative_resistance_burden",
            "greedy_cumulative_resistance_burden",
            "greedy_minus_ppo_burden",
        ),
        "final_resistant_antibiotics": (
            "ppo_final_resistant_antibiotics",
            "greedy_final_resistant_antibiotics",
            "greedy_minus_ppo_final_resistant",
        ),
        "resistance_emergence_events": (
            "ppo_resistance_emergence_events",
            "greedy_resistance_emergence_events",
            "greedy_minus_ppo_resistance_emergence_events",
        ),
        "resistance_emergence_rate": (
            "ppo_resistance_emergence_rate",
            "greedy_resistance_emergence_rate",
            "greedy_minus_ppo_resistance_emergence_rate",
        ),
        "treatment_effectiveness_rate": (
            "ppo_treatment_effectiveness_rate",
            "greedy_treatment_effectiveness_rate",
            "greedy_minus_ppo_treatment_effectiveness_rate",
        ),
        "episode_length": (
            "ppo_episode_length",
            "greedy_episode_length",
            None,
        ),
        "cumulative_reward": (
            "ppo_cumulative_reward",
            "greedy_cumulative_reward",
            "greedy_minus_ppo_reward",
        ),
    }
    output = {}
    for metric, (ppo_key, greedy_key, difference_key) in definitions.items():
        ppo_values = [row[ppo_key] for row in rows]
        greedy_values = [row[greedy_key] for row in rows]
        ppo_seed_values = [
            seed_metrics[metric]["ppo_mean"]
            for seed_metrics in ppo_seed_means.values()
        ]
        greedy_seed_values = [
            seed_metrics[metric]["greedy_mean"]
            for seed_metrics in ppo_seed_means.values()
        ]
        differences = [row[difference_key] for row in rows] if difference_key else []
        seed_differences = [
            seed_metrics[metric]["paired_mean_difference"]
            for seed_metrics in ppo_seed_means.values()
            if seed_metrics[metric]["paired_mean_difference"] is not None
        ]
        interval = None
        if difference_key:
            interval = asdict(paired_bootstrap_interval(
                seed_differences,
                seed=31415,
                resamples=10000,
                confidence_level=0.95,
                independent_runs_assumed=config.matched_runs_independence_assumed,
            ))
        output[metric] = {
            "ppo_mean": _mean(ppo_values),
            "ppo_case_standard_deviation": _standard_deviation(ppo_values),
            "ppo_mean_across_training_seeds": _mean(ppo_seed_values),
            "ppo_standard_deviation_across_training_seeds": _standard_deviation(ppo_seed_values),
            "greedy_mean": _mean(greedy_values),
            "greedy_case_standard_deviation": _standard_deviation(greedy_values),
            "greedy_mean_across_training_seeds": _mean(greedy_seed_values),
            "greedy_standard_deviation_across_training_seeds": _standard_deviation(greedy_seed_values),
            "paired_mean_difference_greedy_minus_ppo": _mean(differences) if differences else None,
            "paired_standard_deviation_across_training_seeds": _standard_deviation(seed_differences),
            "paired_seed_level_differences": seed_differences,
            "paired_bootstrap_95_percent_interval": interval,
        }
    return output


def run_matched_ppo_seed_ensemble(
    model_paths: Sequence[str | Path],
    config: PPOConfig,
    output_dir: str | Path,
    *,
    evaluation_seed_bases: Sequence[int] | None = None,
) -> dict[str, Any]:
    config.__post_init__()
    model_paths = tuple(Path(path) for path in model_paths)
    if len(model_paths) < 2:
        raise ValueError("A seed ensemble requires at least two PPO checkpoints.")
    seed_template = tuple(config.matched_evaluation_seed_bases if evaluation_seed_bases is None else evaluation_seed_bases)
    if not seed_template:
        raise ValueError("At least one matched evaluation seed base is required.")
    profiles = canonical_initial_profiles()
    profile_count = len(profiles)
    seed_stride = max(seed_template) - min(seed_template) + profile_count + 1
    policy_stride = len(seed_template) * profile_count + 1
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Matched ensemble output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    model_output_dir = output_dir / "models"
    model_output_dir.mkdir()

    training_seeds = []
    all_rows = []
    model_summaries = {}
    model_configs = {}
    schedule_by_training_seed = {}
    for model_index, model_path in enumerate(model_paths):
        training_config = _training_config_for_checkpoint(model_path, config)
        if "ppo_seed" not in training_config:
            raise ValueError(f"Checkpoint has no saved PPO seed metadata: {model_path}")
        training_seed = int(training_config["ppo_seed"])
        if training_seed in training_seeds:
            raise ValueError(f"Duplicate PPO training seed: {training_seed}")
        training_seeds.append(training_seed)
        shifted_seed_bases = tuple(seed + model_index * seed_stride for seed in seed_template)
        policy_seed_start = config.matched_policy_seed_start + model_index * policy_stride
        schedule_by_training_seed[str(training_seed)] = list(shifted_seed_bases)
        model_dir = model_output_dir / f"ppo_seed_{training_seed}"
        result = run_matched_policy_evaluation(
            model_path,
            config,
            model_dir,
            evaluation_seed_bases=shifted_seed_bases,
            policy_seed_start=policy_seed_start,
        )
        model_configs[str(training_seed)] = result["config"]
        rows = []
        for source_row in result["raw_results"]:
            row = {**source_row, "ppo_training_seed": training_seed}
            rows.append(row)
            all_rows.append(row)
        model_summaries[str(training_seed)] = result["summary"]

    if len({row["case_id"] for row in all_rows}) != len(all_rows):
        raise ValueError("Combined ensemble case IDs are not unique.")

    metrics_by_seed: dict[int, dict[str, dict[str, float | None]]] = {}
    for training_seed in training_seeds:
        seed_rows = [row for row in all_rows if row["ppo_training_seed"] == training_seed]
        metrics_by_seed[training_seed] = {}
        for metric, (ppo_key, greedy_key, difference_key) in {
            "cumulative_resistance_burden": ("ppo_cumulative_resistance_burden", "greedy_cumulative_resistance_burden", "greedy_minus_ppo_burden"),
            "final_resistant_antibiotics": ("ppo_final_resistant_antibiotics", "greedy_final_resistant_antibiotics", "greedy_minus_ppo_final_resistant"),
            "resistance_emergence_events": ("ppo_resistance_emergence_events", "greedy_resistance_emergence_events", "greedy_minus_ppo_resistance_emergence_events"),
            "resistance_emergence_rate": ("ppo_resistance_emergence_rate", "greedy_resistance_emergence_rate", "greedy_minus_ppo_resistance_emergence_rate"),
            "treatment_effectiveness_rate": ("ppo_treatment_effectiveness_rate", "greedy_treatment_effectiveness_rate", "greedy_minus_ppo_treatment_effectiveness_rate"),
            "episode_length": ("ppo_episode_length", "greedy_episode_length", None),
            "cumulative_reward": ("ppo_cumulative_reward", "greedy_cumulative_reward", "greedy_minus_ppo_reward"),
        }.items():
            metrics_by_seed[training_seed][metric] = {
                "ppo_mean": _mean([row[ppo_key] for row in seed_rows]),
                "greedy_mean": _mean([row[greedy_key] for row in seed_rows]),
                "paired_mean_difference": _mean([row[difference_key] for row in seed_rows]) if difference_key else None,
            }

    profile_rows = []
    profile_labels = ["".join("R" if bit else "S" for bit in profile.resistance) for profile in profiles]
    for profile_index, profile_label in enumerate(profile_labels):
        rows = [row for row in all_rows if row["profile_index"] == profile_index]
        difference = _mean([row["greedy_minus_ppo_burden"] for row in rows])
        profile_rows.append({
            "profile_index": profile_index,
            "initial_state": profile_label,
            "matched_case_count": len(rows),
            "ppo_mean_burden": _mean([row["ppo_cumulative_resistance_burden"] for row in rows]),
            "greedy_mean_burden": _mean([row["greedy_cumulative_resistance_burden"] for row in rows]),
            "greedy_minus_ppo_burden": difference,
            "ppo_mean_final_resistant": _mean([row["ppo_final_resistant_antibiotics"] for row in rows]),
            "greedy_mean_final_resistant": _mean([row["greedy_final_resistant_antibiotics"] for row in rows]),
            "greedy_minus_ppo_final_resistant": _mean([row["greedy_minus_ppo_final_resistant"] for row in rows]),
            "ppo_mean_emergence_rate": _mean([row["ppo_resistance_emergence_rate"] for row in rows]),
            "greedy_mean_emergence_rate": _mean([row["greedy_resistance_emergence_rate"] for row in rows]),
            "greedy_minus_ppo_emergence_rate": _mean([row["greedy_minus_ppo_resistance_emergence_rate"] for row in rows]),
            "ppo_lower_burden_case_count": sum(row["greedy_minus_ppo_burden"] > 1e-12 for row in rows),
            "equal_burden_case_count": sum(abs(row["greedy_minus_ppo_burden"]) <= 1e-12 for row in rows),
            "greedy_lower_burden_case_count": sum(row["greedy_minus_ppo_burden"] < -1e-12 for row in rows),
            "mean_burden_direction": (
                "PPO lower" if difference > 1e-12
                else "Greedy lower" if difference < -1e-12
                else "tied within numerical tolerance"
            ),
        })

    # Reuse the project's paired-run percentile bootstrap; training-seed means are the resampling units.
    summary_metrics = _metric_ensemble_summary(
        all_rows,
        ppo_seed_means=metrics_by_seed,
        config=config,
    )
    summary = {
        "training_seed_count": len(training_seeds),
        "training_seeds": training_seeds,
        "evaluation_seed_bases_per_training_seed": len(seed_template),
        "initial_profile_count": len(profiles),
        "matched_case_count": len(all_rows),
        "policy_metrics": summary_metrics,
        "per_training_seed": model_summaries,
        "per_initial_profile_direction_counts": {
            "ppo_lower_mean_burden": sum(row["mean_burden_direction"] == "PPO lower" for row in profile_rows),
            "greedy_lower_mean_burden": sum(row["mean_burden_direction"] == "Greedy lower" for row in profile_rows),
            "tied_within_numerical_tolerance": sum(row["mean_burden_direction"] == "tied within numerical tolerance" for row in profile_rows),
        },
        "paired_run_independence_assumed": config.matched_runs_independence_assumed,
        "statistical_significance_tests": "not performed",
    }
    first_model_config = model_configs[str(training_seeds[0])]
    config_record = {
        "scenario_id": config.scenario_id,
        "horizon": config.horizon,
        "initial_profiles": [list(profile.resistance) for profile in profiles],
        "initial_profile_order": "canonical itertools.product((0, 1), repeat=7); unchanged across all policies and seeds",
        "evaluation_seed_bases_by_training_seed": schedule_by_training_seed,
        "case_seed_mapping": "case environment seed = evaluation_seed_base + profile_index",
        "training_models": [str(path) for path in model_paths],
        "reward_configuration": first_model_config["reward_configuration"],
        "action_mask_configuration": config.action_mask_configuration,
        "transition_randomness": "same per-step environment seeds for PPO and Greedy within each matched case; action-dependent candidate sets can yield different outcomes",
        "paired_run_independence_assumed": config.matched_runs_independence_assumed,
    }
    _write_csv(output_dir / "raw_results.csv", all_rows)
    _write_csv(output_dir / "per_initial_profile.csv", profile_rows)
    with (output_dir / "config.json").open("w", encoding="utf-8") as config_file:
        json.dump(config_record, config_file, indent=2, allow_nan=False)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, allow_nan=False)
    plots = generate_matched_comparison_plots(all_rows, profile_rows, output_dir / "plots")
    markdown = _render_matched_report(config_record, summary, profile_rows, plots)
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")
    return {
        "config": config_record,
        "summary": summary,
        "raw_results": all_rows,
        "per_initial_profile": profile_rows,
        "plots": plots,
    }


def _render_matched_report(config: dict, summary: dict, profiles: list[dict], plots: list[str]) -> str:
    metrics = summary["policy_metrics"]
    rows = []
    for metric in (
        "cumulative_resistance_burden",
        "final_resistant_antibiotics",
        "resistance_emergence_rate",
        "treatment_effectiveness_rate",
        "episode_length",
        "cumulative_reward",
    ):
        item = metrics[metric]
        interval = item["paired_bootstrap_95_percent_interval"]
        if interval is None:
            bounds = "not applicable"
        elif interval["mean_lower"] is None:
            bounds = "not estimated under configured independence assumption"
        else:
            bounds = f"[{interval['mean_lower']:.4f}, {interval['mean_upper']:.4f}]"
        paired_difference = item["paired_mean_difference_greedy_minus_ppo"]
        paired_sd = item["paired_standard_deviation_across_training_seeds"]
        if paired_difference is None or paired_sd is None:
            rows.append(
                f"| {metric} | {item['ppo_mean']:.4f} | {item['greedy_mean']:.4f} | N/A | N/A | {bounds} |"
            )
        else:
            rows.append(
                f"| {metric} | {item['ppo_mean']:.4f} ({item['ppo_standard_deviation_across_training_seeds']:.4f}) | "
                f"{item['greedy_mean']:.4f} ({item['greedy_standard_deviation_across_training_seeds']:.4f}) | "
                f"{paired_difference:.4f} ({paired_sd:.4f}) | {bounds} |"
            )
    profile_lines = [
        f"| {item['profile_index']} | {item['initial_state']} | {item['greedy_minus_ppo_burden']:.4f} | {item['mean_burden_direction']} |"
        for item in profiles
    ]
    plot_lines = "\n".join(f"- `{path}`" for path in plots)
    return (
        "# Matched PPO vs Greedy Evaluation\n\n"
        f"Scenario: `{config['scenario_id']}`; horizon: {config['horizon']}; "
        f"profiles: {len(config['initial_profiles'])}; PPO training seeds: {summary['training_seed_count']}; "
        f"matched cases: {summary['matched_case_count']}.\n\n"
        "Evaluation preserves canonical profile order. Every PPO/Greedy pair shares its environment seed; "
        "the same per-step seed is reused over the shared trajectory prefix. Candidate sets remain action-dependent.\n\n"
        f"Mean burden is lower for PPO on {summary['per_initial_profile_direction_counts']['ppo_lower_mean_burden']} profiles, "
        f"lower for Greedy on {summary['per_initial_profile_direction_counts']['greedy_lower_mean_burden']}, and tied within numerical tolerance on "
        f"{summary['per_initial_profile_direction_counts']['tied_within_numerical_tolerance']}.\n\n"
        f"Paired difference direction is Greedy minus PPO. Positive burden, final resistance, and emergence differences favor PPO. "
        f"Bootstrap intervals resample training-seed-level paired mean differences and are conditional on the configured computational-run independence assumption. "
        f"No hypothesis tests were performed.\n\n"
        "## Aggregate Metrics\n\n"
        "| Metric | PPO mean (SD across seeds) | Greedy mean (SD across seeds) | Paired difference (SD across seeds) | Paired 95% bootstrap CI |\n"
        "|---|---:|---:|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n\n## Per-Profile Burden Differences\n\n"
        + "Positive values mean Greedy had greater mean burden; negative values mean Greedy had lower mean burden.\n\n"
        + "| Profile index | Initial state | Greedy - PPO burden | Direction |\n|---:|---|---:|---|\n"
        + "\n".join(profile_lines)
        + "\n\n## Plots\n\n"
        + plot_lines
        + "\n\n## Artifacts\n\n"
        + "- `raw_results.csv`: all matched PPO/Greedy cases across model seeds.\n"
        + "- `per_initial_profile.csv`: profile-grouped metrics and direction counts.\n"
        + "- `summary.json`: aggregate metrics, seed-level results, and paired intervals.\n"
        + "- `config.json`: resolved profiles, seed schedules, reward, mask, and model paths.\n"
        + "- `models/`: per-checkpoint raw trajectories and configurations.\n"
    )


def run_matched_policy_evaluation(
    model_path: str | Path,
    config: PPOConfig,
    output_dir: str | Path,
    *,
    initial_profiles: Sequence[ResistanceState | Sequence[int]] | None = None,
    evaluation_seed_bases: Sequence[int] | None = None,
    policy_seed_start: int | None = None,
) -> dict[str, Any]:
    config.__post_init__()
    profiles = canonical_initial_profiles() if initial_profiles is None else tuple(
        state if isinstance(state, ResistanceState) else ResistanceState(tuple(state))
        for state in initial_profiles
    )
    if not profiles or len({profile.resistance for profile in profiles}) != len(profiles):
        raise ValueError("Matched evaluation profiles must be nonempty and unique.")
    seed_bases = tuple(
        config.matched_evaluation_seed_bases
        if evaluation_seed_bases is None
        else evaluation_seed_bases
    )
    if not seed_bases:
        raise ValueError("Matched evaluation requires at least one evaluation seed base.")
    policy_seed_start = (
        config.matched_policy_seed_start
        if policy_seed_start is None
        else policy_seed_start
    )
    if isinstance(policy_seed_start, bool) or not isinstance(policy_seed_start, int) or policy_seed_start < 0:
        raise ValueError("policy_seed_start must be a nonnegative integer.")

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Matched evaluation output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    model = load_ppo_model(model_path, device=config.device)
    ppo_policy_factory = lambda action_space, seed: MaskablePPOObservationPolicy(action_space, model, seed)
    greedy_policy_factory = GreedyPolicy
    seed_pairs = tuple(
        (
            evaluation_seed_base,
            policy_seed_start + run_index * len(profiles),
        )
        for run_index, evaluation_seed_base in enumerate(seed_bases)
    )
    environment_factory = lambda: make_training_environment(config)

    ppo_result = run_multi_seed_evaluation(
        environment_factory,
        ppo_policy_factory,
        seed_pairs,
        initial_states=profiles,
    )
    greedy_result = run_multi_seed_evaluation(
        environment_factory,
        greedy_policy_factory,
        seed_pairs,
        initial_states=profiles,
    )
    case_rows, trajectory_rows = _paired_rows(ppo_result, greedy_result)

    manifest = ppo_result.environment_configuration
    config_record = {
        "scenario_id": config.scenario_id,
        "horizon": config.horizon,
        "initial_profiles": [list(profile.resistance) for profile in profiles],
        "initial_profile_order": "preserved input order; default is itertools.product((0, 1), repeat=7)",
        "evaluation_seed_bases": list(seed_bases),
        "case_seed_mapping": "case environment seed = evaluation_seed_base + profile_index",
        "policy_seed_start": policy_seed_start,
        "policy_seed_pairs": [list(pair) for pair in seed_pairs],
        "ppo_model_path": str(model_path),
        "reward_configuration": manifest["reward_specification"],
        "action_mask_configuration": {
            **config.action_mask_configuration,
            "ppo": "MaskablePPO action_masks",
            "greedy": "GreedyPolicy uniformly samples susceptible actions",
        },
        "environment_configuration": manifest,
        "paired_randomness": "same reset seed and per-step transition_seed for both policies over their shared episode prefix; transition candidate sets remain action-dependent",
        "statistical_tests": "not performed",
    }
    with (output_dir / "config.json").open("w", encoding="utf-8") as config_file:
        json.dump(config_record, config_file, indent=2, allow_nan=False)
    _write_csv(output_dir / "raw_results.csv", case_rows)
    with (output_dir / "raw_trajectories.json").open("w", encoding="utf-8") as trajectories_file:
        json.dump(trajectory_rows, trajectories_file, indent=2, allow_nan=False)
    summary = _summary(case_rows)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, allow_nan=False)
    return {
        "config": config_record,
        "summary": summary,
        "raw_results": case_rows,
        "raw_trajectories": trajectory_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Matched, case-level MaskablePPO versus Greedy evaluation.")
    parser.add_argument("--model-path", action="append", required=True)
    parser.add_argument("--config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--evaluation-seeds",
        help="Optional comma-separated evaluation seed bases; defaults to config matched_evaluation_seed_bases.",
    )
    args = parser.parse_args()
    config = PPOConfig.from_json(args.config)
    evaluation_seed_bases = None
    if args.evaluation_seeds:
        evaluation_seed_bases = tuple(int(value) for value in args.evaluation_seeds.split(","))
    if len(args.model_path) == 1:
        result = run_matched_policy_evaluation(
            args.model_path[0],
            config,
            args.output_dir,
            evaluation_seed_bases=evaluation_seed_bases,
        )
    else:
        result = run_matched_ppo_seed_ensemble(
            args.model_path,
            config,
            args.output_dir,
            evaluation_seed_bases=evaluation_seed_bases,
        )
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
