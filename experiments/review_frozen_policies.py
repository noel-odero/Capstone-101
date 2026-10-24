"""Enumerate the frozen simulator to audit policy quality, ties and structural limitations."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from functools import cache
import hashlib
from itertools import product
import json
from pathlib import Path
from statistics import mean

import torch

from ml.src.ppo_inference import InferenceContext
from ml.src.ppo_training import make_training_environment
from service.runtime import load_runtime
from simulation.resistance_state import ResistanceState
from simulation.reward import RewardFunction
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_sampler import REFERENCE_SCENARIO_ID, TransitionSampler


ROOT = Path(__file__).resolve().parents[1]
PROFILES = tuple(product((0, 1), repeat=7))
SCENARIOS = (REFERENCE_SCENARIO_ID, "SENSITIVITY_Q_025", "SENSITIVITY_Q_050", "SENSITIVITY_Q_075")
METRICS = ("burden", "emergence", "remaining_options", "unsupported_steps", "repeated_selections")
STRATEGIES = ("ppo", "dqn", "random_susceptible_baseline")


class EnumeratedModel:
    def __init__(self, generator, scenario: str, horizon: int, choose):
        self.generator = generator
        self.sampler = TransitionSampler(scenario)
        self.horizon = horizon
        self.choose = choose
        self.transition = ResistanceTransitionFunction()
        self.reward = RewardFunction()

    @cache
    def outcomes(self, profile: tuple, action: int) -> tuple:
        state = ResistanceState(profile)
        sampled = self.sampler.sample(self.generator.generate(state, action), seed=0)
        if not sampled.candidates:
            return (((profile, 1.0),), True)
        distribution = Counter()
        for candidate, probability in zip(sampled.candidates, sampled.candidate_probabilities):
            if probability:
                distribution[self.transition.apply(state, candidate).resistance] += probability
        if sampled.no_transition_probability:
            distribution[profile] += sampled.no_transition_probability
        if abs(sum(distribution.values()) - 1) > 1e-12:
            raise ValueError("Transition probabilities must sum to one.")
        return (tuple(distribution.items()), False)

    @cache
    def optimal(self, profile: tuple, remaining: int) -> float:
        if remaining == 0:
            return 0.0
        if all(profile):
            return float(remaining)
        return min(self.action_value(profile, action, remaining) for action, bit in enumerate(profile) if bit == 0)

    def action_value(self, profile: tuple, action: int, remaining: int) -> float:
        outcomes, _ = self.outcomes(profile, action)
        return sum(probability * (-self.reward.calculate(ResistanceState(after)) + self.optimal(after, remaining - 1))
                   for after, probability in outcomes)

    def optimal_actions(self, profile: tuple, remaining: int) -> tuple[int, ...]:
        best = self.optimal(profile, remaining)
        return tuple(action for action, bit in enumerate(profile) if bit == 0
                     and abs(self.action_value(profile, action, remaining) - best) < 1e-10)

    @cache
    def policy(self, strategy: str, profile: tuple, previous: int | None, remaining: int) -> tuple[float, ...]:
        if remaining == 0:
            return (0.0, 0.0, float(7 - sum(profile)), 0.0, 0.0)
        if all(profile):
            return (float(remaining), 0.0, 0.0, 0.0, 0.0)
        actions = tuple(action for action, bit in enumerate(profile) if bit == 0)
        if strategy != "random_susceptible_baseline":
            action = self.choose(strategy, profile, previous, self.horizon - remaining)
            if action not in actions:
                raise ValueError("Frozen model chose a resistant action.")
            actions = (action,)
        total = [0.0] * len(METRICS)
        for action in actions:
            outcomes, unsupported = self.outcomes(profile, action)
            for after, probability in outcomes:
                following = self.policy(strategy, after, action, remaining - 1)
                immediate = (-self.reward.calculate(ResistanceState(after)), float(sum(after) > sum(profile)),
                             0.0, float(unsupported), float(previous == action))
                for index in range(len(METRICS)):
                    total[index] += probability / len(actions) * (immediate[index] + following[index])
        return tuple(total)


def review(output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Review output directory must be empty.")
    torch.set_num_threads(1)
    runtime = load_runtime()
    environment = make_training_environment(runtime.config)
    try:
        generator = environment.episode_progression.episode_step.transition_model.candidate_generator
    finally:
        environment.close()

    @cache
    def choose(strategy, profile, previous, step):
        return runtime.engine_for(strategy).recommend(InferenceContext(profile, previous, step)).action_id

    rows, scenarios = [], {}
    for scenario in SCENARIOS:
        model = EnumeratedModel(generator, scenario, runtime.config.horizon, choose)
        records = []
        for profile in PROFILES:
            optimum = model.optimal(profile, model.horizon)
            optimal_actions = () if all(profile) else model.optimal_actions(profile, model.horizon)
            for strategy in STRATEGIES:
                values = model.policy(strategy, profile, None, model.horizon)
                gap = values[0] - optimum
                if gap < -1e-9:
                    raise ValueError("Policy burden is below the exact optimum.")
                row = {"scenario": scenario, "profile": "".join(map(str, profile)),
                       "initial_resistant": sum(profile), "strategy": strategy,
                       **dict(zip(METRICS, values)), "optimal_burden": optimum, "gap_to_optimal": max(0, gap),
                       "initial_optimal_action_count": len(optimal_actions)}
                rows.append(row)
                if not all(profile):
                    records.append(row)
        scenarios[scenario] = {
            strategy: {key: mean(row[key] for row in records if row["strategy"] == strategy)
                       for key in (*METRICS, "gap_to_optimal")}
            for strategy in STRATEGIES
        }
        scenarios[scenario]["optimal_mean_burden"] = mean(model.optimal(profile, model.horizon) for profile in PROFILES if not all(profile))
        scenarios[scenario]["initial_action_audit"] = {
            "profiles_with_multiple_optimal_actions": sum(len(model.optimal_actions(profile, model.horizon)) > 1 for profile in PROFILES if not all(profile)),
            **{f"{strategy}_optimal_first_actions": sum(choose(strategy, profile, None, 0) in model.optimal_actions(profile, model.horizon)
                                                       for profile in PROFILES if not all(profile)) for strategy in ("ppo", "dqn")},
        }
        print(f"Reviewed {scenario}", flush=True)

    reference = EnumeratedModel(generator, REFERENCE_SCENARIO_ID, runtime.config.horizon, choose)
    feasible = [(profile, action) for profile in PROFILES for action, bit in enumerate(profile) if bit == 0]
    structural = {
        "feasible_state_action_pairs": len(feasible),
        "pairs_without_applicable_transition": sum(reference.outcomes(profile, action)[1] for profile, action in feasible),
        "pairs_with_forced_unchanged_profile": sum(all(after == profile for after, _ in reference.outcomes(profile, action)[0]) for profile, action in feasible),
        "selected_drug_always_remains_susceptible": all(after[action] == 0 for profile, action in feasible for after, _ in reference.outcomes(profile, action)[0]),
        "nonterminal_profiles": 127,
        "initial_action_agreement": sum(choose("ppo", profile, None, 0) == choose("dqn", profile, None, 0) for profile in PROFILES if not all(profile)),
        "initial_profiles_with_one_feasible_action": sum(sum(profile) == 6 for profile in PROFILES),
        "fully_susceptible": {strategy: dict(zip(METRICS, reference.policy(strategy, (0,) * 7, None, reference.horizon)))
                              for strategy in STRATEGIES},
    }
    report = {
        "method": "Finite-horizon backward induction and exact expectation over enumerated transition distributions. No training or checkpoint selection.",
        "models": {strategy: runtime.policy_model(strategy) for strategy in ("ppo", "dqn")},
        "interaction_data_sha256": runtime.manifest.interaction_data_sha256,
        "review_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "horizon": reference.horizon,
        "scope": "Uniform averages over all 127 nonterminal profiles; all 128 profiles retained in CSV. Known profiles, fixed frozen policies. Exact expectations are conditional on the assumed simulator, not estimates of biological performance or comparisons across training seeds.",
        "sensitivity_scope": "Only the existing occurrence weights for supported resistance-changing candidates vary. This does not stress-test unknown outcomes or self-resistance. Policies are not retrained per scenario.",
        "structural_findings": structural,
        "scenarios": scenarios,
        "critical_limitations": [
            "No modeled self-resistance, recovery, bacterial load, dosing, treatment need or stop action.",
            "The selected drug remains susceptible, so every nonterminal episode lasts the full horizon; exposure and mask compliance cannot discriminate policies.",
            "No applicable candidate is treated as an unchanged state. Low burden from repeated fallback actions does not establish biological safety.",
            "Pairwise heterogeneous MIC outcomes do not calibrate per-step transition probabilities or validate repeated clinical exposures.",
            "Agreement or a small optimality gap can demonstrate optimization of this model, not validation of its biological assumptions.",
            "A fixed exposure penalty would be constant across equal-length runs and cannot resolve repeated-action or missing-evolution behavior.",
        ],
        "references": [
            "https://doi.org/10.1073/pnas.2303165121",
            "https://jmlr.org/papers/v25/23-0183.html",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "review.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "profiles.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    strata = []
    for scenario in SCENARIOS:
        for resistant in range(8):
            for strategy in STRATEGIES:
                selected = [row for row in rows if row["scenario"] == scenario and row["initial_resistant"] == resistant and row["strategy"] == strategy]
                strata.append({"scenario": scenario, "initial_resistant": resistant, "strategy": strategy,
                               "profiles": len(selected),
                               **{key: mean(row[key] for row in selected) for key in (*METRICS, "gap_to_optimal", "optimal_burden")}})
    with (output / "strata.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(strata[0]))
        writer.writeheader()
        writer.writerows(strata)
    plot_review(report, strata, output / "review.png")
    return report


def plot_review(report: dict, strata: list[dict], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ("#347cff", "#0f766e", "#d48611")
    labels = ("PPO", "DQN", "Random baseline")
    reference = report["scenarios"][REFERENCE_SCENARIO_ID]
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        figure, axes = plt.subplots(1, 2, figsize=(11, 4.7), constrained_layout=True)
        for strategy, label, color in zip(STRATEGIES, labels, colors):
            values = [row["burden"] for row in strata if row["scenario"] == REFERENCE_SCENARIO_ID and row["strategy"] == strategy and row["initial_resistant"] < 7]
            axes[0].plot(range(7), values, label=label, color=color, marker="o", markersize=4)
        optimum = [row["optimal_burden"] for row in strata if row["scenario"] == REFERENCE_SCENARIO_ID and row["strategy"] == "ppo" and row["initial_resistant"] < 7]
        axes[0].plot(range(7), optimum, label="Exact optimum", color="#343434", linestyle="--")
        axes[0].set(xlabel="Initially resistant antibiotics", ylabel="Expected cumulative resistance burden",
                    title="Profile-stratified results | reference scenario")
        axes[0].legend(frameon=False)
        gaps = [reference[strategy]["gap_to_optimal"] for strategy in STRATEGIES]
        axes[1].bar(labels, gaps, color=colors, width=.55)
        for index, gap in enumerate(gaps):
            axes[1].text(index, gap + .015, f"{gap:.4f}", ha="center")
        axes[1].set(ylabel="Expected burden above the exact optimum", ylim=(0, max(gaps) * 1.2),
                    title="Optimization gap | 127 nonterminal profiles")
        figure.suptitle("Frozen-policy review: exact expectations within the assumed simulator", fontsize=12)
        figure.supxlabel("Known binary profiles; fixed checkpoints. No clinical validation or algorithm-level superiority claim.", fontsize=9)
        figure.savefig(output, dpi=180, facecolor="white")
        plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/results/model-review")
    args = parser.parse_args()
    result = review(args.output_dir)
    print(json.dumps({"structural_findings": result["structural_findings"], "reference": result["scenarios"][REFERENCE_SCENARIO_ID]}, indent=2))
