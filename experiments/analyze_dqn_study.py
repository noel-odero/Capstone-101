"""Audit a completed benchmark and export descriptive results and a review figure."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.src.masked_dqn import MaskedDQN

from ml.src.confidence_intervals import t_confidence_interval
from ml.src.dqn_benchmark import (
    BenchmarkProtocol, METRICS, STRATEGIES, verified_replicate, write_json,
)
from simulation.resistance_state import ANTIBIOTICS


def audit_study(study: Path) -> tuple[dict, dict]:
    report_path = study / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status = json.loads((study / "status.json").read_text(encoding="utf-8"))
    if status["status"] != "completed":
        raise ValueError("Only a completed benchmark can be reviewed.")
    protocol = BenchmarkProtocol.from_dict(report["protocol"])
    if [run["training_seed"] for run in report["replicates"]] != list(protocol.training_seeds):
        raise ValueError("Training replicates are incomplete or out of order.")
    baseline = json.loads((study / "baseline_evaluation.json").read_text(encoding="utf-8"))
    action_counts = {strategy: Counter({drug: 0 for drug in ANTIBIOTICS}) for strategy in STRATEGIES}
    unsupported_counts = {strategy: Counter({drug: 0 for drug in ANTIBIOTICS}) for strategy in STRATEGIES}
    profile_values = defaultdict(lambda: defaultdict(list))
    checked_steps = 0
    checked_seed_pairs = 0

    def episodes_of(evaluation):
        return [episode for run in evaluation["runs"] for episode in run["evaluation"]["episodes"]]

    def inspect(episodes, strategy):
        nonlocal checked_steps
        for episode in episodes:
            profile = "".join(str(value) for value in episode["initial_resistance_profile"])
            burden = -sum(step["reward"] for step in episode["steps"]) - episode["terminal_reward_adjustment"]
            profile_values[profile][strategy].append(burden)
            for step in episode["steps"]:
                checked_steps += 1
                action = step["action"]
                if step["observation"][action] != 0 or not step["info"]["effective"]:
                    raise ValueError("A recorded action was infeasible.")
                name = ANTIBIOTICS[action]
                action_counts[strategy][name] += 1
                if step["info"]["transition_status"] == "unsupported_no_candidate":
                    unsupported_counts[strategy][name] += 1
                    if step["observation"][:7] != step["next_observation"][:7]:
                        raise ValueError("An unsupported transition changed the resistance profile.")

    baseline_episodes = episodes_of(baseline)
    inspect(baseline_episodes, "random_susceptible_baseline")
    for replicate in report["replicates"]:
        seed = replicate["training_seed"]
        config = protocol.shared_config(seed)
        directory = study / f"seed_{seed}"
        if verified_replicate(config, directory) != replicate:
            raise ValueError("Report and verified replicate record differ.")
        candidates = {}
        for strategy in ("dqn", "ppo"):
            data = json.loads((directory / strategy / "evaluation.json").read_text(encoding="utf-8"))
            candidates[strategy] = episodes_of(data)
            inspect(candidates[strategy], strategy)
        if any(len(episodes) != len(baseline_episodes) for episodes in candidates.values()):
            raise ValueError("Paired evaluation case counts differ.")
        for baseline_episode, dqn, ppo in zip(baseline_episodes, candidates["dqn"], candidates["ppo"]):
            for candidate in (dqn, ppo):
                for key in ("initial_resistance_profile", "environment_seed", "episode_id", "policy_seed"):
                    if candidate[key] != baseline_episode[key]:
                        raise ValueError(f"Paired case metadata differs: {key}")
                for left, right in zip(candidate["steps"], baseline_episode["steps"]):
                    checked_seed_pairs += 1
                    if left["info"]["transition_seed"] != right["info"]["transition_seed"]:
                        raise ValueError("Per-step transition seed streams differ.")
    comparisons = {}
    for a, b in (("dqn", "ppo"), ("dqn", "random_susceptible_baseline"), ("ppo", "random_susceptible_baseline")):
        comparisons[f"{a}_minus_{b}"] = {}
        for metric in METRICS:
            differences = [replicate["metrics"][a][metric] - replicate["metrics"][b][metric]
                           for replicate in report["replicates"]]
            comparisons[f"{a}_minus_{b}"][metric] = {
                "interval": asdict(t_confidence_interval(differences)),
                "negative_count": sum(value < -1e-12 for value in differences),
                "tie_count": sum(abs(value) <= 1e-12 for value in differences),
                "positive_count": sum(value > 1e-12 for value in differences),
                "per_seed": dict(zip(map(str, protocol.training_seeds), differences)),
            }
    analysis = {
        "study_id": protocol.study_id, "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_replicates": len(report["replicates"]),
        "unique_evaluation_cases_per_checkpoint": len(baseline_episodes),
        "checked_actions": checked_steps, "checked_transition_seed_pairs": checked_seed_pairs,
        "interval_scope": "Pointwise 95% Student-t intervals over paired training-replicate means, conditional on the fixed evaluation profiles and RNG seeds. Assumes independent training replicates; does not cover transition-data uncertainty or unseen profiles. No multiplicity-adjusted significance claim.",
        "comparisons": comparisons,
        "action_counts": action_counts, "unsupported_action_counts": unsupported_counts,
        "profile_mean_burden": {
            profile: {strategy: mean(values) for strategy, values in strategies.items()}
            for profile, strategies in sorted(profile_values.items())
        },
    }
    return report, analysis


def plot_review(report: dict, analysis: dict, path: Path) -> None:
    seeds = [run["training_seed"] for run in report["replicates"]]
    differences = [run["dqn_minus_ppo"]["resistance_burden"] for run in report["replicates"]]
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
        axes[0].axhline(0, color="#999999", linewidth=1)
        axes[0].scatter(range(len(seeds)), differences, color="#2263c7", s=35)
        axes[0].set_xticks(range(len(seeds)), [str(seed // 1000) for seed in seeds])
        axes[0].set(xlabel="Training seed (thousands)\nNegative values indicate lower DQN burden", ylabel="DQN minus PPO mean burden",
                    title="Each paired training replicate")
        labels = ["DQN", "PPO", "Random baseline"]
        unsupported = [report["summary"][strategy]["unsupported_steps"] / report["summary"][strategy]["antibiotic_exposure"] * 100 for strategy in STRATEGIES]
        axes[1].bar(labels, unsupported, color=["#2263c7", "#7d8191", "#c2984c"], width=.55)
        axes[1].set(ylim=(0, 100), ylabel="Actions with no candidate transition (%)",
                    title="Transition-data gaps remain substantial")
        for index, value in enumerate(unsupported):
            axes[1].text(index, value + 2, f"{value:.1f}%", ha="center")
        figure.suptitle(f"{analysis['training_replicates']}-seed offline comparison | fixed evaluation set", fontsize=13)
        figure.savefig(path, dpi=180, facecolor="white")
        plt.close(figure)


def export_candidate(study: Path, report: dict, destination: Path) -> None:
    seed = 12000
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("Candidate output directory must be empty.")
    replicate = next(run for run in report["replicates"] if run["training_seed"] == seed)
    source = study / f"seed_{seed}" / "dqn"
    checkpoint_bytes = (source / "final_model.zip").read_bytes()
    if hashlib.sha256(checkpoint_bytes).hexdigest() != replicate["checkpoints"]["dqn"]:
        raise ValueError("Candidate differs from the audited checkpoint.")
    model = MaskedDQN.load(io.BytesIO(checkpoint_bytes), device="cpu")
    profile_records = json.loads((source / "evaluation.json").read_text(encoding="utf-8"))
    profiles = profile_records["initial_resistance_profiles"]
    checked = 0
    for profile in profiles:
        if all(profile):
            continue
        observation = np.asarray([*profile, *([0] * 7), 0], dtype=np.float32)
        action, _ = model.predict(observation, deterministic=True)
        if profile[int(action)] != 0:
            raise ValueError("Candidate failed canonical-profile feasibility verification.")
        checked += 1
    destination.mkdir(parents=True, exist_ok=True)
    file_hashes = {}
    for name in ("final_model.zip", "config.json", "environment_manifest.json", "training_summary.json"):
        data = checkpoint_bytes if name == "final_model.zip" else (source / name).read_bytes()
        file_hashes[name] = hashlib.sha256(data).hexdigest()
        (destination / name).write_bytes(data)
    if file_hashes["final_model.zip"] != replicate["checkpoints"]["dqn"]:
        raise ValueError("Candidate differs from the audited checkpoint.")
    write_json(destination / "manifest.json", {
        "manifest_version": 1, "model_id": f"dqn_seed_{seed}", "algorithm": "MaskedDQN",
        "status": "offline_integration_candidate", "training_seed": seed,
        "selection_rule": "fixed seed 12000, matching the existing PPO serving seed; declared before this DQN seed's full-budget result was inspected",
        "loader": "ml.src.masked_dqn.MaskedDQN.load", "deterministic_inference": True,
        "actual_training_timesteps": replicate["actual_timesteps_per_model"],
        "file_sha256": file_hashes, "packages": report["packages"],
        "simulator": report["environment"], "action_masking": "susceptible_actions_only",
        "checked_nonterminal_profiles": checked,
        "source_sha256": report["source_sha256"], "study_id": report["protocol"]["study_id"],
        "study_report_sha256": hashlib.sha256((study / "report.json").read_bytes()).hexdigest(),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Analysis output directory must be empty.")
    report, analysis = audit_study(args.study_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "analysis.json", analysis)
    plot_review(report, analysis, args.output_dir / "comparison.png")
    (args.output_dir / "study.json").write_bytes((args.study_dir / "report.json").read_bytes())
    if args.candidate_dir:
        export_candidate(args.study_dir, report, args.candidate_dir)
    print(json.dumps({"audit": "passed", "checked_actions": analysis["checked_actions"],
                      "dqn_minus_ppo_burden": analysis["comparisons"]["dqn_minus_ppo"]["resistance_burden"]}, indent=2))


if __name__ == "__main__":
    main()
