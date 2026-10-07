import argparse
from dataclasses import asdict, fields, is_dataclass
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import platform

import numpy as np
import scipy

from ml.src.confidence_intervals import calculate_confidence_intervals
from ml.src.evaluation_runner import EpisodeResult, EvaluationResult, StepResult
from ml.src.greedy_policy import GreedyPolicy
from ml.src.metrics import calculate_metrics
from ml.src.multi_seed_evaluation import run_multi_seed_evaluation
from ml.src.random_policy import RandomPolicy
from ml.src.statistical_comparison import ComparisonConfig, compare_strategies
from ml.src.value_iteration import value_iteration
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.deterministic_reference import REFERENCE_SCENARIO_ID as EXACT_SCENARIO
from simulation.environment import AntibioticEnvironment
from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.reward import RewardSpecification
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_sampler import REFERENCE_SCENARIO_ID, SENSITIVITY_SCENARIOS, TransitionSampler


def _validate_plan(plan: dict) -> tuple[tuple[int, ...], ...]:
    for name, minimum in (("run_count", 1), ("horizon", 1), ("environment_seed_start", 0), ("policy_seed_start", 0)):
        value = plan[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}.")
    if plan["gamma"] != 1.0 or isinstance(plan["gamma"], bool):
        raise ValueError("This baseline checkpoint uses the approved gamma=1.")
    if plan["initial_profile_design"] == "all_binary":
        profiles = tuple(product((0, 1), repeat=len(ANTIBIOTICS)))
    elif plan["initial_profile_design"] == "explicit":
        profiles = tuple(ResistanceState(tuple(profile)).resistance for profile in plan["initial_profiles"])
    else:
        raise ValueError("Unknown initial-profile design.")
    if not profiles or len(set(profiles)) != len(profiles):
        raise ValueError("Initial profiles must be nonempty and unique.")
    scenarios = plan["scenarios"]
    if not isinstance(scenarios, list) or not scenarios or len(set(scenarios)) != len(scenarios):
        raise ValueError("Scenarios must be a nonempty unique list.")
    if any(scenario != REFERENCE_SCENARIO_ID and scenario not in SENSITIVITY_SCENARIOS for scenario in scenarios):
        raise ValueError("Unknown stochastic scenario.")
    ComparisonConfig(
        independent_runs_assumed=plan["independent_runs_assumed"],
        symmetric_differences_assumed=plan["symmetric_differences_assumed"],
        confidence_level=plan["confidence_level"],
        bootstrap_resamples=plan["bootstrap_resamples"],
        bootstrap_seed=plan["bootstrap_seed"], permutation_seed=plan["permutation_seed"],
    )
    return profiles


def _exact_reference(profiles, horizon):
    environment = DeterministicReferenceEnvironment(max_steps=horizon)
    solution = value_iteration(environment, gamma=1.0)
    episodes = []
    values = []
    try:
        for episode_id, profile in enumerate(profiles):
            state = EpisodeState(ResistanceState(profile))
            initial = state
            initial_observation = profile + (0,) * 7 + (0,)
            observation = initial_observation
            steps = []
            while not environment.is_terminal(state):
                action = solution.policy[state]
                if action is None:
                    raise RuntimeError("Exact policy unexpectedly has no nonterminal action.")
                next_state, reward, terminated, info = environment.transition(state, action)
                next_observation = next_state.resistance_state.resistance + tuple(
                    int(index == action) for index in range(7)
                ) + (next_state.treatment_step,)
                steps.append(StepResult(observation, action, next_observation, reward, terminated, False, info))
                state = next_state
                observation = next_observation
            reason = "no_effective_antibiotic" if all(state.resistance_state.resistance) else "maximum_horizon"
            episode = EpisodeResult(
                episode_id, 0, 0, "exact_reference_value_iteration", profile,
                state.resistance_state.resistance, initial_observation, {}, tuple(steps),
                True, False, reason,
                terminal_reward_adjustment=(
                    solution.state_values[initial] if not steps else 0.0
                ),
            )
            if not math.isclose(episode.cumulative_reward, solution.state_values[initial], abs_tol=1e-10):
                raise RuntimeError("Exact rollout reward does not match its Bellman value.")
            episodes.append(episode)
            values.append({"initial_profile": profile, "optimal_value": solution.state_values[initial],
                           "first_action": solution.policy[initial]})
        evaluation = EvaluationResult(
            EXACT_SCENARIO,
            horizon,
            asdict(RewardSpecification()),
            tuple(episodes),
        )
        return {
            "scenario_id": EXACT_SCENARIO, "gamma": 1.0,
            "planning_state_count": len(solution.state_values),
            "tie_rule": "lowest_action_id_exact_ties",
            "seed_information": "No RNG used; episode seed fields are deterministic placeholders.",
            "metrics": calculate_metrics(evaluation).to_dict(),
            "trajectories": asdict(evaluation), "initial_state_values": values,
            "uncertainty": "No seed-based interval: exact values for a fixed computational reference.",
        }
    finally:
        environment.close()


def generate_baseline_report(plan: dict) -> dict:
    """Run the predeclared baseline plan; no stochastic VI transfer or PPO work."""
    profiles = _validate_plan(plan)
    plan = json.loads(json.dumps(plan, allow_nan=False))
    seeds = tuple(
        (plan["environment_seed_start"] + index * len(profiles),
         plan["policy_seed_start"] + index * len(profiles))
        for index in range(plan["run_count"])
    )
    payload = {
        "report_contract": "sprint_4_baseline_v1", "plan": plan,
        "plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
        "initial_profiles": profiles, "seed_pairs": seeds,
        "action_order": ANTIBIOTICS,
        "software_versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "stochastic_scenarios": {},
    }
    comparison_config = ComparisonConfig(
        independent_runs_assumed=plan["independent_runs_assumed"],
        symmetric_differences_assumed=plan["symmetric_differences_assumed"],
        confidence_level=plan["confidence_level"], bootstrap_resamples=plan["bootstrap_resamples"],
        bootstrap_seed=plan["bootstrap_seed"], permutation_seed=plan["permutation_seed"],
    )
    for scenario in plan["scenarios"]:
        def environment_factory():
            model = StochasticTransitionModel(sampler=TransitionSampler(scenario))
            progression = EpisodeProgression(episode_step=EpisodeStep(transition_model=model))
            return AntibioticEnvironment(max_steps=plan["horizon"], episode_progression=progression)

        evaluations = {}
        policy_reports = {}
        for name, policy in (("random", RandomPolicy), ("greedy", GreedyPolicy)):
            evaluation = run_multi_seed_evaluation(environment_factory, policy, seeds, initial_states=profiles)
            evaluations[name] = evaluation
            intervals = calculate_confidence_intervals(evaluation, plan["confidence_level"]).to_dict()
            intervals.pop("evaluation")
            policy_reports[name] = {"evaluation": evaluation.to_dict(), "uncertainty": intervals}
        comparison_report = compare_strategies(
            evaluations, [("greedy", "random")], family_id=f"baseline_primary_{scenario}",
            config=comparison_config,
        )
        comparisons = {}
        for field in fields(comparison_report):
            if field.name == "evaluations":
                continue
            value = getattr(comparison_report, field.name)
            if is_dataclass(value):
                value = asdict(value)
            elif field.name == "comparisons":
                value = [asdict(result) for result in value]
            comparisons[field.name] = value
        comparisons["evaluation_references"] = {name: f"stochastic_scenarios/{scenario}/policies/{name}/evaluation" for name in evaluations}
        payload["stochastic_scenarios"][scenario] = {"policies": policy_reports, "comparison": comparisons}
    payload["exact_reference"] = _exact_reference(profiles, plan["horizon"])
    return payload


def _number(value):
    return "undefined" if value is None else f"{value:.4f}"


def _interval_cell(record):
    interval = record["interval"]
    return f"{_number(interval['mean'])} [{_number(interval['lower_bound'])}, {_number(interval['upper_bound'])}]; n={interval['sample_count']}"


def render_baseline_report(report: dict) -> str:
    """Render measured results without clinical claims or an arbitrary ranking."""
    plan = report["plan"]
    lines = [
        "# Sprint 4 Baseline Evaluation Report", "",
        f"Plan SHA-256: `{report['plan_sha256']}`", "",
        f"Design: {plan['run_count']} seed runs per policy/scenario; {len(report['initial_profiles'])} "
        f"equally weighted initial profiles per run; horizon {plan['horizon']}.", "",
        "Profiles are computational fixtures, not a clinical prevalence distribution. "
        "An all-resistant profile produces a zero-step episode. Defined episode rates exclude "
        "zero-step episodes; endpoint, exposure, and reward means include them.", "",
        "Intervals below are 95% Student-t intervals across run-level values (or the configured "
        "confidence level). Their coverage is conditional on the documented sampling assumptions. "
        "Distinct seeds do not establish biological independence. Matching policies' seeds means "
        "matched initialization and schedules, not perfectly paired transition draws.", "",
        "No stochastic VI adapter is used. Exact/reference results below are for a different, "
        "deterministic computational problem and are not a stochastic optimality benchmark.", "",
    ]
    fields = (
        ("TER (mean episode)", "mean_episode_treatment_effectiveness_rate"),
        ("RER (mean episode)", "mean_episode_resistance_emergence_rate"),
        ("FEA", "mean_future_effective_antibiotics"),
        ("Change FEA", "mean_change_in_future_effective_antibiotics"),
        ("Exposure", "mean_cumulative_antibiotic_exposure"),
        ("Reward", "mean_cumulative_reward"),
    )
    for scenario, section in report["stochastic_scenarios"].items():
        lines += [f"## {scenario}", "", "| Metric | Random mean [CI]; n | Greedy mean [CI]; n |", "|---|---|---|"]
        for label, field in fields:
            cells = [_interval_cell(section["policies"][name]["uncertainty"]["confidence_intervals"][field]) for name in ("random", "greedy")]
            lines.append(f"| {label} | {cells[0]} | {cells[1]} |")
        lines += ["", "### Pooled Rates (Separate Estimands)", "", "| Metric | Random | Greedy |", "|---|---|---|"]
        for field in ("pooled_treatment_effectiveness_rate", "pooled_resistance_emergence_rate"):
            cells = [_interval_cell(section["policies"][name]["uncertainty"]["confidence_intervals"][field]) for name in ("random", "greedy")]
            lines.append(f"| {field} | {cells[0]} | {cells[1]} |")
        lines += ["", "### Greedy Minus Random", "", "Paired bootstrap bounds are pointwise, not simultaneous family intervals. "
                  "Positive TER/FEA and negative RER favor greedy for that metric only. "
                  "Lower exposure must be interpreted jointly with effectiveness and resistance.", "",
                  "| Metric | Mean difference [bootstrap CI] | Median difference [bootstrap CI] | Raw p | Holm p | Test status |",
                  "|---|---|---|---|---|---|"]
        for result in section["comparison"]["comparisons"]:
            ci = result["bootstrap"]
            lines.append(
                f"| {result['metric']} | {_number(result['mean_difference'])} "
                f"[{_number(ci['mean_lower'])}, {_number(ci['mean_upper'])}] | "
                f"{_number(result['median_difference'])} [{_number(ci['median_lower'])}, {_number(ci['median_upper'])}] | "
                f"{_number(result['raw_p_value'])} | {_number(result['adjusted_p_value'])} | {result['test_status']} |"
            )
        lines += ["", "The Holm family has four primary metrics within this scenario; scenarios are not pooled.", ""]
        for name, policy in section["policies"].items():
            summaries = [run["metrics"]["summary"] for run in policy["evaluation"]["runs"]]
            counts = {"episodes": sum(item["episode_count"] for item in summaries),
                      "zero_step": sum(item["zero_step_episode_count"] for item in summaries),
                      "terminated": sum(item["terminated_episode_count"] for item in summaries),
                      "truncated": sum(item["truncated_episode_count"] for item in summaries)}
            reasons = {}
            for item in summaries:
                for reason, count in item["termination_reason_counts"].items():
                    reasons[reason] = reasons.get(reason, 0) + count
            flags = sorted({flag for record in policy["uncertainty"]["confidence_intervals"].values()
                            for flag in record["interval"]["limitations"]})
            lines.append(f"- {name}: counts `{counts}`; termination reasons `{reasons}`; interval flags `{flags}`.")
    exact = report["exact_reference"]
    summary = exact["metrics"]["summary"]
    lines += ["", "## Exact Deterministic Reference", "",
              f"Scenario `{exact['scenario_id']}`; gamma=1; {exact['planning_state_count']} planning states. "
              "Lowest action ID resolves exact ties. Every exact trajectory's cumulative reward "
              "was checked against its Bellman value.", "",
              "| Metric | Exact-policy result over the fixed profile set |", "|---|---|"]
    for label, field in fields:
        lines.append(f"| {label} | {_number(summary[field])} |")
    lines += ["", exact["uncertainty"], "", "## Interpretation and Regeneration", "",
              "The measured metrics are kept separate; no overall winner or clinical recommendation is inferred. "
              "Scenario-to-scenario differences show sensitivity to computational transition assumptions, "
              "not changes in empirically estimated biological probabilities. An unsupported/no-candidate "
              "unchanged transition is lack of modeled evidence, not proof that resistance cannot evolve.", "",
              "Symmetry is not automatically declared. Withheld p-values are not evidence of equality. "
              "No joint inferential claim is made across scenarios. PPO has not been trained or evaluated here.", "",
              "From the repository root, using the project virtual environment:", "",
              "```powershell", "python -m ml.src.baseline_report --config experiments/baseline_config.json --output-dir experiments/results/baseline", "```", "",
              "The JSON artifact contains the plan, raw trajectories, seeds, per-run metrics, uncertainty, "
              "comparison configurations, source-data fingerprints, and software versions. Preserve this "
              "artifact together with the source revision. No timestamp is included, allowing identical "
              "inputs and numerical versions to reproduce identical artifacts."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Regenerate the Sprint 4 computational baseline report.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.config.read_text(encoding="utf-8"))
    report = generate_baseline_report(plan)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "baseline_report.json"
    markdown_path = args.output_dir / "baseline_report.md"
    with json_path.open("w", encoding="utf-8") as output:
        json.dump(report, output, sort_keys=True, separators=(",", ":"), allow_nan=False)
        output.write("\n")
    markdown_path.write_text(render_baseline_report(report), encoding="utf-8")
    print(f"Generated {markdown_path} and {json_path}")


if __name__ == "__main__":
    main()