from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, environment_manifest
from simulation.resistance_state import ANTIBIOTICS
from simulation.reward import RewardSpecification
from simulation.transition_sampler import REFERENCE_SCENARIO_ID, SENSITIVITY_SCENARIOS


PROJECT = "Reinforcement Learning for Antibiotic Sequencing: A Decision-Support System for Preventing Multidrug Resistance"
EXPERIMENT_VERSION = "capstone-final-through-step-8"
FINAL_TRAINING_SEEDS = (1000, 2000, 3000, 4000, 5000)
PROFILE_ORDER = "itertools.product((0, 1), repeat=7); S=0 susceptible, R=1 resistant"
CHECKPOINT_DIRECTORIES = tuple(f"experiments/results/ppo_seed_{seed}" for seed in FINAL_TRAINING_SEEDS)
MATCHED_DIR = "experiments/results/ppo_greedy_matched_five_seed_final"
STEP4_DIR = "experiments/results/decision_traces_step4_final"
STEP5_DIR = "experiments/results/ppo_vi_reference_step5_final_v3"
STEP7_DIR = "experiments/results/transition_selection_sensitivity_step7_final"
STEP8_DIR = "experiments/results/reward_objective_sensitivity_step8_final"

SOURCE_FILES = (
    "simulation/resistance_state.py",
    "simulation/action_space.py",
    "simulation/observation.py",
    "simulation/encoder.py",
    "simulation/decoder.py",
    "simulation/environment.py",
    "simulation/episode.py",
    "simulation/episode_step.py",
    "simulation/episode_progression.py",
    "simulation/episode_termination.py",
    "simulation/reward.py",
    "simulation/treatment_action.py",
    "simulation/treatment_action_executor.py",
    "simulation/treatment_effectiveness.py",
    "simulation/candidate_transition.py",
    "simulation/transition_generator.py",
    "simulation/transition_function.py",
    "simulation/transition_sampler.py",
    "simulation/stochastic_transition_model.py",
    "simulation/deterministic_reference.py",
    "simulation/cross_resistance.py",
    "simulation/collateral_sensitivity.py",
    "simulation/unchanged_transition.py",
    "ml/src/ppo_training.py",
    "ml/src/ppo_evaluation.py",
    "ml/src/greedy_policy.py",
    "ml/src/evaluation_runner.py",
    "ml/src/metrics.py",
    "ml/src/multi_seed_evaluation.py",
    "ml/src/matched_policy_evaluation.py",
    "ml/src/value_iteration.py",
    "ml/src/decision_traces.py",
    "ml/src/decision_trace_report.py",
    "ml/src/ppo_vi_reference.py",
    "ml/src/ppo_vi_benchmark.py",
    "ml/src/transition_selection_sensitivity.py",
    "ml/src/reward_objective_sensitivity.py",
    "ml/src/reproducibility.py",
)
TRANSITION_FILES = (
    "simulation/candidate_transition.py",
    "simulation/transition_generator.py",
    "simulation/transition_function.py",
    "simulation/transition_sampler.py",
    "simulation/stochastic_transition_model.py",
    "simulation/deterministic_reference.py",
    "simulation/cross_resistance.py",
    "simulation/collateral_sensitivity.py",
    "simulation/unchanged_transition.py",
    "data/processed/empirical_interactions.csv",
    "data/processed/transition_parameters.csv",
    "data/processed/transition_uncertainty.csv",
    "data/processed/transition_sampling_config.csv",
)
ENVIRONMENT_FILES = (
    "simulation/environment.py",
    "simulation/action_space.py",
    "simulation/resistance_state.py",
    "simulation/observation.py",
    "simulation/encoder.py",
    "simulation/decoder.py",
    "simulation/episode.py",
    "simulation/episode_step.py",
    "simulation/episode_progression.py",
    "simulation/episode_termination.py",
    "simulation/reward.py",
    "simulation/treatment_action_executor.py",
    "simulation/treatment_effectiveness.py",
    "data/processed/action_space.csv",
    "data/processed/empirical_interactions.csv",
)
ARTIFACT_PATHS = (
    "experiments/ppo_baseline_config.json",
    "README.md",
    "docs/scientific-specification/reward-function.md",
    "docs/scientific-specification/evaluation-metrics.md",
    "docs/scientific-specification/resistance-transition-model.md",
    "docs/scientific-specification/deterministic-reference.md",
    "docs/scientific-specification/action-space.md",
    "ml/requirements.txt",
    "ml/requirements-lock.txt",
    "data/processed/action_space.csv",
    "data/processed/empirical_interactions.csv",
    f"{MATCHED_DIR}/config.json",
    f"{MATCHED_DIR}/summary.json",
    f"{MATCHED_DIR}/raw_results.csv",
    f"{MATCHED_DIR}/per_initial_profile.csv",
    *tuple(f"{MATCHED_DIR}/models/ppo_seed_{seed}/config.json" for seed in FINAL_TRAINING_SEEDS),
    *tuple(f"{MATCHED_DIR}/models/ppo_seed_{seed}/raw_results.csv" for seed in FINAL_TRAINING_SEEDS),
    *tuple(f"{MATCHED_DIR}/models/ppo_seed_{seed}/raw_trajectories.json" for seed in FINAL_TRAINING_SEEDS),
    "experiments/results/gentamicin_audit_five_seed_report_v3/summary.json",
    "experiments/results/gentamicin_audit_five_seed_report_v3/decision_audit.json",
    "experiments/results/gentamicin_audit_five_seed_report_v3/report.md",
    f"{STEP4_DIR}/summary.json",
    f"{STEP4_DIR}/canonical_decisions.jsonl",
    f"{STEP4_DIR}/ciprofloxacin_immediate_advantage.json",
    f"{STEP4_DIR}/report.md",
    f"{STEP5_DIR}/compatibility.json",
    f"{STEP5_DIR}/summary.json",
    f"{STEP5_DIR}/raw_state_contexts.csv",
    f"{STEP5_DIR}/ciprofloxacin_446_reference.csv",
    f"{STEP5_DIR}/report.md",
    f"{STEP7_DIR}/config.json",
    f"{STEP7_DIR}/summary.json",
    f"{STEP7_DIR}/raw_results.csv",
    f"{STEP7_DIR}/raw_trajectories.jsonl",
    f"{STEP7_DIR}/report.md",
    f"{STEP8_DIR}/config.json",
    f"{STEP8_DIR}/summary.json",
    f"{STEP8_DIR}/raw_results.csv",
    f"{STEP8_DIR}/raw_trajectories.jsonl",
    f"{STEP8_DIR}/objective_alignment.csv",
    f"{STEP8_DIR}/report.md",
    "experiments/results/gentamicin_audit_five_seed_report_v3/summary.json",
    "experiments/results/gentamicin_audit_five_seed_report_v3/decision_audit.json",
    "experiments/results/gentamicin_audit_five_seed_report_v3/report.md",
)
REQUIRED_MANIFEST_FIELDS = (
    "project", "experiment_version", "code_revision", "configuration_fingerprint",
    "environment_fingerprint", "transition_fingerprint", "reward_fingerprint",
    "action_order", "horizon", "gamma", "training_seeds", "evaluation_seeds",
    "initial_profile_order", "checkpoint_inventory", "evaluation_artifacts",
    "experiment_commands", "python_version", "dependency_lockfile",
)
_VOLATILE_KEYS = {
    "generated_at_utc", "timestamp", "created_at", "updated_at", "output_dir",
    "temporary_directory", "machine_name", "hostname",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _stable_configuration(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _stable_configuration(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in _VOLATILE_KEYS
        }
    if isinstance(value, (tuple, list)):
        return [_stable_configuration(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
    """Hash canonical scientific settings, excluding volatile metadata keys."""
    payload = canonical_json(_stable_configuration(configuration)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_stream:
        for block in iter(lambda: file_stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_relative_path(path: str | Path) -> str:
    return Path(path).as_posix().replace("\\", "/")


def validate_manifest(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest or manifest[field] is None)


def finalize_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    missing = validate_manifest(manifest)
    if missing:
        raise ValueError(f"Manifest missing required fields: {missing}")
    return json.loads(canonical_json(manifest))


def validate_seed_pairing(
    profiles: Sequence[Sequence[int]],
    schedules_by_seed: Mapping[str, Sequence[int]],
    policy_seed_pairs_by_seed: Mapping[str, Sequence[Sequence[int]]],
) -> None:
    canonical_profiles = tuple(tuple(int(bit) for bit in profile.resistance) for profile in canonical_initial_profiles())
    normalized_profiles = tuple(tuple(profile) for profile in profiles)
    if normalized_profiles != canonical_profiles:
        raise ValueError("Initial profiles must retain the canonical 128-profile order.")
    if set(schedules_by_seed) != set(policy_seed_pairs_by_seed):
        raise ValueError("Evaluation and policy seed schedule checkpoints differ.")
    expanded_eval_seeds: set[int] = set()
    expanded_policy_seeds: set[int] = set()
    for seed, bases in schedules_by_seed.items():
        pairs = policy_seed_pairs_by_seed[seed]
        if len(bases) != 5 or len(pairs) != 5:
            raise ValueError(f"Training seed {seed} must have five evaluation/policy schedules.")
        if [int(pair[0]) for pair in pairs] != [int(base) for base in bases]:
            raise ValueError(f"Training seed {seed} has mismatched evaluation and policy seed bases.")
        for base, pair in zip(bases, pairs):
            eval_range = set(range(int(base), int(base) + len(canonical_profiles)))
            policy_range = set(range(int(pair[1]), int(pair[1]) + len(canonical_profiles)))
            if expanded_eval_seeds & eval_range or expanded_policy_seeds & policy_range:
                raise ValueError("Expanded evaluation or policy seed schedules overlap.")
            expanded_eval_seeds.update(eval_range)
            expanded_policy_seeds.update(policy_range)


def verify_integrity_inventory(repository_root: str | Path, inventory: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(repository_root)
    checked, missing, mismatched = 0, [], []
    for record in inventory.get("files", ()):
        relative = canonical_relative_path(record["path"])
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        checked += 1
        actual = sha256_file(path)
        if actual != record["sha256"]:
            mismatched.append({"path": relative, "expected_sha256": record["sha256"], "actual_sha256": actual})
    return {"ok": not missing and not mismatched, "checked_files": checked, "missing": missing, "mismatched": mismatched}


def _metadata_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _hash_paths(repository_root: Path, relative_paths: Sequence[str]) -> dict[str, str]:
    output = {}
    for relative in relative_paths:
        path = repository_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required provenance input is missing: {relative}")
        output[canonical_relative_path(relative)] = sha256_file(path)
    return output


def _training_key_subset(configuration: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "scenario_id", "horizon", "total_timesteps", "learning_rate", "n_steps",
        "batch_size", "n_epochs", "gamma", "gae_lambda", "ent_coef", "clip_range",
        "policy_architecture", "training_profile_design", "evaluation_frequency",
        "evaluation_episodes", "device",
    )
    return {field: configuration.get(field) for field in fields}


def _source_revision(repository_root: Path) -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository_root,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repository_root,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        branch = subprocess.run(
            ["git", "branch", "--show-current"], cwd=repository_root,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"base_commit": None, "branch": None, "working_tree_clean": None, "dirty_path_count": None}
    return {
        "base_commit": revision,
        "branch": branch,
        "working_tree_clean": not status,
        "dirty_path_count": len(status),
        "note": "The base commit does not include the dirty working-tree experiment runners; source-file SHA-256 inventory records the audited working files.",
    }


def _resolve_training_path(repository_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repository_root / path


def _commands() -> dict[str, Any]:
    rerun_model_paths = tuple(
        f"experiments/results/reproducibility_runs/ppo_seed_{seed}/final_model.zip"
        for seed in FINAL_TRAINING_SEEDS
    )
    training = [
        f".\\.venv\\Scripts\\python.exe -m ml.src.ppo_training --config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/ppo_seed_{seed} --seed {seed} --total-timesteps 100000"
        for seed in FINAL_TRAINING_SEEDS
    ]
    return {
        "install": ["py -3.11 -m venv .venv", ".\\.venv\\Scripts\\python.exe -m pip install -r ml/requirements.txt"],
        "training": {
            "commands": training,
            "historical_budget": "100,000 requested steps; saved training summaries report 100,096 actual steps because PPO completes rollout batches",
            "note": "Re-training creates new checkpoints. The final reported analyses use the existing frozen final_model.zip files; do not rerun training to reproduce the frozen-checkpoint analyses unless intentionally reproducing the training stage.",
        },
        "ppo_evaluation": [
            f".\\.venv\\Scripts\\python.exe -m ml.src.ppo_evaluation --model-path experiments/results/reproducibility_runs/ppo_seed_{seed}/final_model.zip --config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/ppo_seed_{seed}_evaluation"
            for seed in FINAL_TRAINING_SEEDS
        ],
        "matched_ppo_vs_greedy": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.matched_policy_evaluation",
            *[f"  --model-path {path}" for path in rerun_model_paths],
            "  --config experiments/ppo_baseline_config.json",
            "  --output-dir experiments/results/reproducibility_runs/matched",
        ],
        "decision_traces": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.decision_trace_report --matched-results-dir experiments/results/reproducibility_runs/matched --config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/decision_traces",
        ],
        "gentamicin_audit": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.gentamicin_audit --matched-results-dir experiments/results/reproducibility_runs/matched --ppo-config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/gentamicin_audit",
        ],
        "step5_ppo_vs_value_iteration": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.ppo_vi_benchmark --matched-results-dir experiments/results/reproducibility_runs/matched --decision-traces-dir experiments/results/reproducibility_runs/decision_traces --config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/ppo_vi_reference",
        ],
        "step7_transition_sensitivity": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.transition_selection_sensitivity --matched-results-dir experiments/results/reproducibility_runs/matched --config experiments/ppo_baseline_config.json --output-dir experiments/results/reproducibility_runs/transition_selection_sensitivity",
        ],
        "step8_reward_objective_rescoring": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.reward_objective_sensitivity --matched-results-dir experiments/results/reproducibility_runs/matched --output-dir experiments/results/reproducibility_runs/reward_objective_sensitivity",
        ],
        "tests": [".\\.venv\\Scripts\\python.exe -m pytest -q"],
        "integrity_verification": [
            ".\\.venv\\Scripts\\python.exe -m ml.src.reproducibility --verify --repo-root . --package-dir experiments/results/reproducibility_step9_final",
        ],
    }


def _experiment_inventory(repository_root: Path) -> dict[str, Any]:
    experiments = {
        "PPO training": {
            "purpose": "Produce five frozen masked-PPO checkpoints; historical source run used 100,000 requested steps per seed.",
            "inputs": ["experiments/ppo_baseline_config.json", "ml/src/ppo_training.py", "ml/requirements-lock.txt"],
            "seeds": list(FINAL_TRAINING_SEEDS),
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "normalized resistance burden; gamma=1; H=8",
            "outputs": [f"experiments/results/ppo_seed_{seed}/final_model.zip" for seed in FINAL_TRAINING_SEEDS],
            "command_group": "training",
            "status": "training configs/checkpoints/metrics are preserved; bitwise retraining from a clean checkout was not tested",
        },
        "PPO deterministic evaluation": {
            "purpose": "Evaluate each final checkpoint deterministically over the canonical 128 initial profiles.",
            "inputs": [f"experiments/results/ppo_seed_{seed}/final_model.zip" for seed in FINAL_TRAINING_SEEDS],
            "configuration": "experiments/ppo_baseline_config.json plus saved per-checkpoint training config",
            "seeds": "evaluation reset seed base plus profile index, per saved evaluation config",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "canonical normalized resistance burden",
            "outputs": [f"experiments/results/ppo_seed_{seed}_evaluation/evaluation_results.json" for seed in FINAL_TRAINING_SEEDS],
            "command_group": "ppo_evaluation",
            "status": "existing evaluation artifacts are inventoried; main Step 2 results use matched multi-schedule evaluation",
        },
        "Step 2 matched PPO vs Greedy": {
            "purpose": "Primary matched policy comparison.",
            "inputs": [f"experiments/results/ppo_seed_{seed}/final_model.zip" for seed in FINAL_TRAINING_SEEDS],
            "configuration": MATCHED_DIR + "/config.json",
            "seeds": "five checkpoint-specific evaluation schedules and per-case paired policy seed schedules; recorded in source config and per-model configs",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "canonical normalized resistance burden",
            "outputs": [MATCHED_DIR + "/raw_results.csv", MATCHED_DIR + "/summary.json", MATCHED_DIR + "/models/ppo_seed_1000/raw_trajectories.json"],
            "command_group": "matched_ppo_vs_greedy",
            "status": "reproducible with frozen checkpoints and recorded seed schedules in the current source tree",
        },
        "Step 3 Gentamicin audit": {
            "purpose": "Audit saved Gentamicin policy probabilities and same-state one-step alternatives; no downstream counterfactual is inferred.",
            "inputs": [MATCHED_DIR + "/models/ppo_seed_1000/raw_trajectories.json", "frozen checkpoints listed in checkpoint_inventory.json"],
            "configuration": "experiments/ppo_baseline_config.json and matched case transition metadata",
            "seeds": "recorded matched evaluation and per-step transition seeds",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "one-step diagnostic under canonical reward; audit only",
            "outputs": ["experiments/results/gentamicin_audit_five_seed_report_v3/summary.json", "experiments/results/gentamicin_audit_five_seed_report_v3/decision_audit.json"],
            "command_group": "gentamicin_audit",
            "status": "re-runnable from saved matched trajectories and frozen checkpoints",
        },
        "Step 4 decision traces": {
            "purpose": "Validated canonical decision traces and representative trajectory audit.",
            "inputs": [MATCHED_DIR + "/models/ppo_seed_1000/raw_trajectories.json", "frozen checkpoints listed in checkpoint_inventory.json"],
            "configuration": MATCHED_DIR + "/config.json",
            "seeds": "inherited matched case seeds",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "canonical reward replay",
            "outputs": [STEP4_DIR + "/canonical_decisions.jsonl", STEP4_DIR + "/summary.json"],
            "command_group": "decision_traces",
            "status": "re-runnable from matched trajectories and frozen checkpoints",
        },
        "Step 5 PPO vs VI": {
            "purpose": "Compare transferred frozen policies with exact deterministic-reference values.",
            "inputs": [MATCHED_DIR + "/config.json", STEP4_DIR + "/ciprofloxacin_immediate_advantage.json", "frozen checkpoints listed in checkpoint_inventory.json"],
            "configuration": STEP5_DIR + "/compatibility.json (the Step 5 output has no top-level config.json)",
            "seeds": "inherited frozen model seeds and saved profiles; deterministic-reference transitions use no transition RNG",
            "transition": "REF_DETERMINISTIC_FIRST_SUPPORTED versus PPO training scenario REF_UNIFORM_SUPPORTED",
            "objective": "canonical normalized resistance burden; exact VI requires gamma=1",
            "outputs": [STEP5_DIR + "/summary.json", STEP5_DIR + "/raw_state_contexts.csv", STEP5_DIR + "/report.md"],
            "command_group": "step5_ppo_vs_value_iteration",
            "status": "re-runnable with frozen checkpoints and Step 4 cases; existing Step 5 artifact does not store a standalone configuration fingerprint",
        },
        "Step 6 held-out-state generalization": {
            "purpose": "Assess whether an unseen-state evaluation can be certified under the existing training design.",
            "inputs": ["saved PPO training configs and episode-level training summaries"],
            "configuration": "training_profile_design=cycle_all_nonterminal_profiles",
            "seeds": "existing checkpoint seeds",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": "not an experiment",
            "outputs": [],
            "command_group": None,
            "status": "not performed as a held-out experiment; all 127 nonterminal profiles were training starts and logged artifacts cannot certify never-seen observation contexts",
        },
        "Step 7 transition-selection sensitivity": {
            "purpose": "Compare the result under two existing candidate-selection modes.",
            "inputs": [MATCHED_DIR + "/config.json", "frozen checkpoints listed in checkpoint_inventory.json"],
            "configuration": STEP7_DIR + "/config.json",
            "seeds": "same saved per-checkpoint five schedules and policy seed pairs",
            "transition": ["REF_UNIFORM_SUPPORTED", "REF_DETERMINISTIC_FIRST_SUPPORTED"],
            "objective": "canonical normalized resistance burden",
            "outputs": [STEP7_DIR + "/raw_results.csv", STEP7_DIR + "/raw_trajectories.jsonl", STEP7_DIR + "/report.md"],
            "command_group": "step7_transition_sensitivity",
            "status": "re-runnable from frozen checkpoints; deterministic-first uses no transition RNG",
        },
        "Step 8 objective sensitivity": {
            "purpose": "Re-score the same frozen PPO/Greedy trajectories under four objective definitions.",
            "inputs": [MATCHED_DIR + "/models/ppo_seed_1000/raw_trajectories.json (and corresponding four other seeds)"],
            "configuration": STEP8_DIR + "/config.json",
            "seeds": "same 3,200 matched cases; five checkpoints x five schedules x 128 profiles",
            "transition": REFERENCE_SCENARIO_ID,
            "objective": ["A normalized burden", "B unnormalized burden", "C positive resistance increase only", "D final resistance only"],
            "outputs": [STEP8_DIR + "/raw_results.csv", STEP8_DIR + "/raw_trajectories.jsonl", STEP8_DIR + "/report.md"],
            "command_group": "step8_reward_objective_rescoring",
            "status": "evaluation/re-scoring of frozen trajectories only; no alternative-reward training",
        },
    }
    results_root = repository_root / "experiments/results"
    existing_directories = sorted(
        path.relative_to(repository_root).as_posix()
        for path in results_root.iterdir()
        if path.is_dir() and not path.name.startswith("reproducibility_step9_")
    )
    return {
        "experiments": experiments,
        "reproduction_commands": _commands(),
        "existing_result_directories": existing_directories,
    }


def _experiment_artifacts() -> list[str]:
    paths = set(ARTIFACT_PATHS)
    paths.update(f"experiments/results/ppo_seed_{seed}/config.json" for seed in FINAL_TRAINING_SEEDS)
    paths.update(f"experiments/results/ppo_seed_{seed}/environment_manifest.json" for seed in FINAL_TRAINING_SEEDS)
    paths.update(f"experiments/results/ppo_seed_{seed}/training_summary.json" for seed in FINAL_TRAINING_SEEDS)
    paths.update(f"experiments/results/ppo_seed_{seed}/final_model.zip" for seed in FINAL_TRAINING_SEEDS)
    paths.update(f"experiments/results/ppo_seed_{seed}/checkpoints/best_model.zip" for seed in FINAL_TRAINING_SEEDS)
    return sorted(paths)


def build_reproducibility_package(repository_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    if not output.is_absolute():
        output = root / output
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Reproducibility package directory is not empty: {output}")

    baseline_path = root / "experiments/ppo_baseline_config.json"
    baseline_raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = PPOConfig.from_json(baseline_path)
    live_environment = environment_manifest(baseline)
    matched_dir = root / MATCHED_DIR
    matched_config_path = matched_dir / "config.json"
    matched_config = json.loads(matched_config_path.read_text(encoding="utf-8"))
    matched_config_sha = sha256_file(matched_config_path)
    profiles = [list(profile.resistance) for profile in canonical_initial_profiles()]
    if matched_config.get("initial_profiles") != profiles or len(profiles) != 128:
        raise ValueError("Matched results must contain the canonical 128 profiles in order.")
    if matched_config.get("scenario_id") != REFERENCE_SCENARIO_ID or matched_config.get("horizon") != 8:
        raise ValueError("Matched source scenario or horizon differs from the final scientific contract.")
    if matched_config.get("reward_configuration") != RewardSpecification().to_dict():
        raise ValueError("Matched source reward differs from the canonical reward specification.")
    if matched_config.get("action_mask_configuration", {}).get("rule") != "susceptible_actions_only":
        raise ValueError("Matched source action mask differs from the canonical feasibility contract.")

    training_seeds = {}
    training_configs = {}
    evaluation_pairs = {}
    checkpoint_records = []
    for seed in FINAL_TRAINING_SEEDS:
        run_relative = f"experiments/results/ppo_seed_{seed}"
        run_dir = root / run_relative
        training_config_path = run_dir / "config.json"
        training_manifest_path = run_dir / "environment_manifest.json"
        training_summary_path = run_dir / "training_summary.json"
        training_config = json.loads(training_config_path.read_text(encoding="utf-8"))
        training_manifest = json.loads(training_manifest_path.read_text(encoding="utf-8"))
        training_summary = json.loads(training_summary_path.read_text(encoding="utf-8"))
        if training_config.get("ppo_seed") != seed:
            raise ValueError(f"Training configuration seed mismatch: {run_relative}")
        if training_config.get("scenario_id") != REFERENCE_SCENARIO_ID or training_config.get("horizon") != 8 or training_config.get("gamma") != 1.0:
            raise ValueError(f"Training scientific contract mismatch: {run_relative}")
        for field in (
            "scenario_id", "horizon", "action_names", "action_count", "observation_shape",
            "observation_low", "observation_high", "observation_dtype", "interaction_data_sha256",
            "reward_specification", "action_masking", "training_profile_design", "training_profile_count",
        ):
            if training_manifest.get(field) != live_environment.get(field):
                raise ValueError(f"Current environment differs from seed {seed} manifest field {field}.")
        training_seeds[str(seed)] = {
            "ppo_seed": training_config["ppo_seed"],
            "environment_seed": training_config["environment_seed"],
            "validation_seed": training_config["evaluation_seed"],
            "requested_timesteps": training_config["total_timesteps"],
            "actual_timesteps": training_summary["total_timesteps"],
            "training_software_versions": training_summary.get("software_versions"),
            "training_config": canonical_relative_path(training_config_path.relative_to(root)),
            "training_config_sha256": sha256_file(training_config_path),
            "environment_manifest": canonical_relative_path(training_manifest_path.relative_to(root)),
            "environment_manifest_sha256": sha256_file(training_manifest_path),
        }
        training_configs[str(seed)] = _training_key_subset(training_config)
        model_result_dir = matched_dir / "models" / f"ppo_seed_{seed}"
        model_result_config_path = model_result_dir / "config.json"
        model_result_config = json.loads(model_result_config_path.read_text(encoding="utf-8"))
        schedule_bases = matched_config["evaluation_seed_bases_by_training_seed"][str(seed)]
        policy_pairs = model_result_config["policy_seed_pairs"]
        evaluation_pairs[str(seed)] = policy_pairs
        if tuple(pair[0] for pair in policy_pairs) != tuple(schedule_bases):
            raise ValueError(f"Matched evaluation/policy seed schedule differs for training seed {seed}.")
        final_path = run_dir / "final_model.zip"
        best_path = run_dir / "checkpoints" / "best_model.zip"
        for path, kind, selected in (
            (final_path, "final", True),
            (best_path, "best_evaluation_checkpoint", False),
        ):
            if not path.is_file():
                raise FileNotFoundError(f"Checkpoint missing: {path.relative_to(root)}")
            checkpoint_records.append({
                "logical_name": f"ppo_seed_{seed}_{kind}",
                "path": canonical_relative_path(path.relative_to(root)),
                "training_seed": seed,
                "checkpoint_type": kind,
                "selected_for_final_comparisons": selected,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "training_config": training_seeds[str(seed)]["training_config"],
                "training_config_sha256": training_seeds[str(seed)]["training_config_sha256"],
                "environment_manifest": training_seeds[str(seed)]["environment_manifest"],
                "matched_evaluation_config": canonical_relative_path(model_result_config_path.relative_to(root)),
                "matched_evaluation_config_sha256": sha256_file(model_result_config_path),
            })

    validate_seed_pairing(
        profiles,
        matched_config["evaluation_seed_bases_by_training_seed"],
        evaluation_pairs,
    )

    action_order = list(ANTIBIOTICS)
    reward_spec = RewardSpecification().to_dict()
    action_space_sha = sha256_file(root / "data/processed/action_space.csv")
    raw_interaction_sha = sha256_file(root / "data/processed/empirical_interactions.csv")
    transition_source_hashes = _hash_paths(root, TRANSITION_FILES)
    environment_source_hashes = _hash_paths(root, ENVIRONMENT_FILES)
    source_hashes = _hash_paths(root, SOURCE_FILES)
    lock_path = root / "ml/requirements-lock.txt"
    requirements_path = root / "ml/requirements.txt"
    lock_bytes = lock_path.read_bytes()
    lock_encoding = "UTF-16LE with BOM" if lock_bytes.startswith(b"\xff\xfe") else "UTF-8/other"

    transition_semantics = {
        "training_and_primary_evaluation": {
            "scenario_id": REFERENCE_SCENARIO_ID,
            "candidate_handling": "deduplicate by target_drug/outcome; uniform choice among supported candidates",
            "unsupported": "unsupported_no_candidate leaves resistance unchanged",
            "per_step_random_seed": "drawn from environment RNG; recorded in transition metadata",
        },
        "step7_sensitivity": [
            {"scenario_id": REFERENCE_SCENARIO_ID, "selection": "uniform over deduplicated candidates"},
            {"scenario_id": "REF_DETERMINISTIC_FIRST_SUPPORTED", "selection": "lexicographically smallest (target_drug, outcome); no transition RNG"},
        ],
        "other_explicit_sampler_scenarios": dict(sorted(SENSITIVITY_SCENARIOS.items())),
        "step7_additional_modes_evaluated": False,
    }
    environment_contract = {
        "state": "7 binary resistance values; 128 resistance profiles; elapsed treatment step included in state/observation",
        "observation": "15 float32 values: 7 resistance/susceptibility entries, 7 one-hot last-action entries, elapsed step",
        "action_count": 7,
        "action_order": action_order,
        "horizon": 8,
        "terminal_behavior": "episode ends at step 8 or all seven resistant; initially all-resistant is a zero-action terminal episode with the existing terminal reward adjustment",
        "action_mask": "susceptible actions only when a feasible action exists",
        "gamma": 1.0,
        "transition_data": {
            "environment_manifest_interaction_payload_sha256": live_environment["interaction_data_sha256"],
            "empirical_interactions_csv_sha256": raw_interaction_sha,
            "action_space_csv_sha256": action_space_sha,
        },
    }
    reward_contract = {
        "specification": reward_spec,
        "per_transition": "r_t = -N_R(s_{t+1}) / 7",
        "terminal_accounting": "if all seven become resistant before H, charge the all-resistant state through the remaining horizon; zero-step initially all-resistant returns -H",
        "effectiveness": "hard feasibility constraint; no independent reward bonus",
        "future_antibiotic_preservation": "implicit through resistance burden/state transitions; no separate reward term",
        "unnecessary_exposure": "not modeled; no treatment-need/clearance state and no no-treatment action",
    }
    ppo_contract = {
        "algorithm": "sb3_contrib.MaskablePPO",
        "policy": "MlpPolicy",
        "architecture": [64, 64],
        "action_masking": "sb3-contrib action_masks; susceptible-only",
        "gamma": 1.0,
        "training_hyperparameters_by_seed": training_configs,
        "checkpoint_selection": "final_model.zip for each of seeds 1000, 2000, 3000, 4000, 5000; best_model.zip separately inventoried but not used in reported matched comparisons",
    }
    greedy_contract = {
        "implementation": "ml/src/greedy_policy.py: GreedyPolicy",
        "selection": "decode the seven susceptibility entries; collect canonical action IDs with susceptibility 0; choose one uniformly using a private random.Random seeded per episode; raise ValueError if none are susceptible",
        "tie_breaking": "uniform random over all currently susceptible actions; no preference by drug name or future value",
    }
    vi_contract = {
        "implementation": "ml/src/value_iteration.py:value_iteration",
        "environment": "REF_DETERMINISTIC_FIRST_SUPPORTED",
        "planning_state": "EpisodeState(resistance_profile, treatment_step), excludes last_action because it does not affect transitions/reward/termination",
        "horizon": 8,
        "gamma": 1.0,
        "tie_breaking": "exact maximizing tie; lowest feasible action ID",
        "terminal": "all-resistant terminal value equals negative remaining horizon; other terminal value zero; terminal policy None",
    }
    transition_fingerprint = configuration_fingerprint({
        "semantics": transition_semantics,
        "transition_sources": transition_source_hashes,
        "transition_data": environment_contract["transition_data"],
    })
    reward_fingerprint = configuration_fingerprint({
        "reward_contract": reward_contract,
        "reward_implementation_sha256": source_hashes["simulation/reward.py"],
    })
    environment_fingerprint = configuration_fingerprint({
        "contract": environment_contract,
        "source_hashes": environment_source_hashes,
    })
    scientific_configuration = {
        "environment": environment_contract,
        "reward": reward_contract,
        "transition": transition_semantics,
        "ppo": ppo_contract,
        "greedy": greedy_contract,
        "value_iteration": vi_contract,
        "matched_evaluation": {
            "scenario_id": matched_config["scenario_id"],
            "horizon": matched_config["horizon"],
            "profiles": profiles,
            "profile_order": PROFILE_ORDER,
            "evaluation_seed_bases_by_training_seed": matched_config["evaluation_seed_bases_by_training_seed"],
            "policy_seed_pairs_by_training_seed": evaluation_pairs,
            "matched_case_count": 3200,
        },
        "transition_fingerprint": transition_fingerprint,
        "reward_fingerprint": reward_fingerprint,
        "environment_fingerprint": environment_fingerprint,
    }
    config_fingerprint = configuration_fingerprint(scientific_configuration)

    provenance_validation = _validate_experiment_lineage(root, matched_config_sha, checkpoint_records)
    if not provenance_validation["ok"]:
        raise ValueError(f"Experiment provenance validation failed: {provenance_validation['issues']}")

    source_paths = _experiment_artifacts()
    artifact_records = []
    for relative in source_paths:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Final experiment artifact missing: {relative}")
        artifact_records.append({
            "path": canonical_relative_path(relative),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    for relative, digest in sorted(source_hashes.items()):
        path = root / relative
        artifact_records.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": digest,
        })
    for checkpoint in checkpoint_records:
        path = root / checkpoint["path"]
        artifact_records.append({
            "path": checkpoint["path"], "size_bytes": path.stat().st_size,
            "sha256": checkpoint["sha256"],
        })
    integrity_inventory = {
        "algorithm": "SHA-256",
        "scope": "frozen final and best checkpoints, training configs/manifests, key raw matched/trace/Step5/Step7/Step8 inputs and summaries; plots and temporary files excluded",
        "files": sorted({record["path"]: record for record in artifact_records}.values(), key=lambda record: record["path"]),
    }

    output.mkdir(parents=True, exist_ok=True)
    checkpoint_inventory = {
        "checkpoint_count": len(checkpoint_records),
        "final_checkpoint_count_used_in_reports": sum(item["selected_for_final_comparisons"] for item in checkpoint_records),
        "checkpoints": checkpoint_records,
    }
    fingerprint_record = {
        "configuration_fingerprint": config_fingerprint,
        "environment_fingerprint": environment_fingerprint,
        "transition_fingerprint": transition_fingerprint,
        "reward_fingerprint": reward_fingerprint,
        "scientific_configuration": scientific_configuration,
        "source_file_sha256": source_hashes,
        "algorithm": "SHA-256(canonical JSON with sorted keys, compact separators, no NaN)",
        "volatile_excluded": sorted(_VOLATILE_KEYS),
    }
    experiment_inventory = _experiment_inventory(root)
    dependency_record = {
        "install_requirements": "ml/requirements.txt",
        "install_requirements_sha256": sha256_file(requirements_path),
        "dependency_lockfile": "ml/requirements-lock.txt",
        "dependency_lockfile_sha256": sha256_file(lock_path),
        "dependency_lockfile_encoding": lock_encoding,
        "historical_lock_role": "captured environment package snapshot; README install workflow uses ml/requirements.txt",
        "python_version": sys.version.split()[0],
        "packages": {
            name: _metadata_version(name) for name in (
                "stable-baselines3", "sb3-contrib", "torch", "gymnasium",
                "numpy", "scipy", "matplotlib", "pandas", "pytest",
            )
        },
    }
    manifest = {
        "project": PROJECT,
        "experiment_version": EXPERIMENT_VERSION,
        "code_revision": _source_revision(root),
        "configuration_fingerprint": config_fingerprint,
        "environment_fingerprint": environment_fingerprint,
        "transition_fingerprint": transition_fingerprint,
        "reward_fingerprint": reward_fingerprint,
        "action_order": action_order,
        "horizon": 8,
        "gamma": 1.0,
        "training_seeds": list(FINAL_TRAINING_SEEDS),
        "evaluation_seeds": matched_config["evaluation_seed_bases_by_training_seed"],
        "policy_seed_pairs_by_training_seed": evaluation_pairs,
        "initial_profile_order": PROFILE_ORDER,
        "initial_profile_count": 128,
        "checkpoint_inventory": "checkpoint_inventory.json",
        "evaluation_artifacts": "artifact_integrity.json",
        "experiment_commands": "experiment_inventory.json",
        "python_version": dependency_record["python_version"],
        "dependency_lockfile": dependency_record,
        "training": ppo_contract,
        "training_run_records": training_seeds,
        "environment": environment_contract,
        "transition_selection": transition_semantics,
        "reward": reward_contract,
        "greedy": greedy_contract,
        "deterministic_reference": vi_contract,
        "evaluation_design": scientific_configuration["matched_evaluation"],
        "experiment_status": {
            "step5": "reproducible with frozen checkpoints and saved trajectory/artifact inputs; no standalone config fingerprint exists in its output, so compatibility and checkpoint provenance are reconstructed and disclosed",
            "step6": "not a successful unseen-state experiment; all 127 nonterminal profiles were training starts and retained logs cannot certify never-seen observations",
            "step7": "reproducible with frozen artifacts and the existing source tree; two computational selection rules only",
            "step8": "re-scoring of frozen trajectories; no retraining under alternative objectives",
        },
        "clean_checkout_reproduction": {
            "tested": False,
            "status": "not validated from a clean checkout",
            "reason": "current experiment runners and some supporting pipeline code are uncommitted/untracked relative to the recorded base commit",
        },
        "timestamp_if_already_available": None,
        "integrity_inventory": "artifact_integrity.json",
        "integrity_file_count": len(integrity_inventory["files"]),
        "base_matched_config_sha256": matched_config_sha,
        "lineage_validation": provenance_validation,
    }
    manifest = finalize_manifest(manifest)
    (output / "checkpoint_inventory.json").write_text(json.dumps(checkpoint_inventory, indent=2, allow_nan=False), encoding="utf-8")
    (output / "configuration_fingerprints.json").write_text(json.dumps(fingerprint_record, indent=2, allow_nan=False), encoding="utf-8")
    (output / "experiment_inventory.json").write_text(json.dumps(experiment_inventory, indent=2, allow_nan=False), encoding="utf-8")
    (output / "artifact_integrity.json").write_text(json.dumps(integrity_inventory, indent=2, allow_nan=False), encoding="utf-8")
    (output / "reproducibility_manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    (output / "reproduction_report.md").write_text(_render_reproduction_report(manifest, checkpoint_inventory, experiment_inventory, fingerprint_record), encoding="utf-8")
    (output / "README.md").write_text(_package_readme(), encoding="utf-8")
    return manifest


def _validate_experiment_lineage(repository_root: Path, matched_config_sha256: str, checkpoints: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    issues = []
    expected_hashes = {record["training_seed"]: record["sha256"] for record in checkpoints if record["checkpoint_type"] == "final"}
    matched_config = json.loads((repository_root / f"{MATCHED_DIR}/config.json").read_text(encoding="utf-8"))
    matched_summary = json.loads((repository_root / f"{MATCHED_DIR}/summary.json").read_text(encoding="utf-8"))
    step4 = json.loads((repository_root / f"{STEP4_DIR}/summary.json").read_text(encoding="utf-8"))
    step5 = json.loads((repository_root / f"{STEP5_DIR}/summary.json").read_text(encoding="utf-8"))
    step5_compatibility = json.loads((repository_root / f"{STEP5_DIR}/compatibility.json").read_text(encoding="utf-8"))
    step7_config = json.loads((repository_root / f"{STEP7_DIR}/config.json").read_text(encoding="utf-8"))
    step7_summary = json.loads((repository_root / f"{STEP7_DIR}/summary.json").read_text(encoding="utf-8"))
    step8_config = json.loads((repository_root / f"{STEP8_DIR}/config.json").read_text(encoding="utf-8"))
    step8_summary = json.loads((repository_root / f"{STEP8_DIR}/summary.json").read_text(encoding="utf-8"))
    if matched_config_sha256 != sha256_file(repository_root / f"{MATCHED_DIR}/config.json"):
        issues.append("step2: matched config fingerprint does not match the package")
    if matched_summary.get("training_seed_count") != 5 or matched_summary.get("initial_profile_count") != 128 or matched_summary.get("matched_case_count") != 3200:
        issues.append("step2: expected five seeds x five schedules x 128 matched cases")
    if step4.get("decisions") != 25400 or step4.get("episodes") != 3200:
        issues.append("step4: decision-trace coverage differs from the recorded 3,200 episodes")
    if step5_compatibility.get("horizon") != 8 or step5_compatibility.get("gamma") != 1.0:
        issues.append("step5: deterministic-reference horizon/gamma differs from the frozen contract")
    if step7_config.get("conditions") != [REFERENCE_SCENARIO_ID, "REF_DETERMINISTIC_FIRST_SUPPORTED"]:
        issues.append("step7: transition-selection conditions differ from the two documented modes")
    if step7_config.get("source_config_sha256") != matched_config_sha256:
        issues.append("step7: source matched-config fingerprint mismatch")
    for condition in (REFERENCE_SCENARIO_ID, "REF_DETERMINISTIC_FIRST_SUPPORTED"):
        paired = step7_summary.get("conditions", {}).get(f"{condition}:paired_ppo_vs_greedy", {})
        if paired.get("paired_case_count") != 3200:
            issues.append(f"step7: incomplete paired cases for {condition}")
    if step8_config.get("source_config_sha256") != matched_config_sha256 or step8_config.get("transition_scenario") != REFERENCE_SCENARIO_ID:
        issues.append("step8: source matched config or transition condition differs")
    if step8_summary.get("case_count") != 3200 or step8_config.get("no_retraining_or_source_mutation") is not True:
        issues.append("step8: frozen-trajectory re-scoring design differs from the recorded 3,200-case experiment")
    for name, rows, hash_key in (
        ("step4", step4["model_provenance"], "checkpoint_sha256"),
        ("step5", step5["model_provenance"], "sha256"),
        ("step7", step7_config["models"], "checkpoint_sha256"),
        ("step8", json.loads((repository_root / f"{STEP8_DIR}/compatibility.json").read_text(encoding="utf-8"))["source_checkpoint_provenance"], "checkpoint_sha256"),
    ):
        for row in rows:
            seed = int(row["training_seed"])
            if expected_hashes.get(seed) != row.get(hash_key):
                issues.append(f"{name}: checkpoint provenance mismatch for seed {seed}")
    return {"ok": not issues, "issues": issues, "verified_steps": ["step4", "step5", "step7", "step8"]}


def verify_reproducibility_package(repository_root: str | Path, package_dir: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    package = Path(package_dir)
    if not package.is_absolute():
        package = root / package
    manifest_path = package / "reproducibility_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = json.loads((package / "artifact_integrity.json").read_text(encoding="utf-8"))
    checkpoints = json.loads((package / "checkpoint_inventory.json").read_text(encoding="utf-8"))
    fingerprint = json.loads((package / "configuration_fingerprints.json").read_text(encoding="utf-8"))
    integrity = verify_integrity_inventory(root, inventory)
    checkpoint_results = []
    for checkpoint in checkpoints["checkpoints"]:
        path = root / checkpoint["path"]
        actual = sha256_file(path) if path.is_file() else None
        checkpoint_results.append({
            "path": checkpoint["path"], "ok": actual == checkpoint["sha256"],
            "expected": checkpoint["sha256"], "actual": actual,
        })
    fingerprint_matches = configuration_fingerprint(fingerprint["scientific_configuration"]) == manifest["configuration_fingerprint"]
    schema_missing = validate_manifest(manifest)
    lineage = _validate_experiment_lineage(root, manifest["base_matched_config_sha256"], checkpoints["checkpoints"])
    return {
        "ok": integrity["ok"] and all(item["ok"] for item in checkpoint_results) and fingerprint_matches and not schema_missing and lineage["ok"],
        "integrity": integrity,
        "checkpoint_hash_checks": checkpoint_results,
        "configuration_fingerprint_matches": fingerprint_matches,
        "missing_required_manifest_fields": list(schema_missing),
        "lineage_validation": lineage,
    }


def _runtime_contracts() -> dict[str, Any]:
    return {
        "hard_constraints": "susceptible-action mask; effectiveness is feasibility, not reward",
        "reward_terms": "-N_R(next_state)/7 with all-resistant terminal-tail convention",
        "evaluation_only": ["final resistant count", "resistance-emergence events/rate", "effectiveness rate", "action-count exposure proxy"],
        "exposure_objective": "not modeled",
    }


def _render_reproduction_report(manifest, checkpoint_inventory, experiment_inventory, fingerprint_record) -> str:
    checkpoints = checkpoint_inventory["checkpoints"]
    lines = [
        "# Reproducibility Audit: Steps 1-8", "",
        "## 10.1 Reproduction Status", "",
        "**Status: reproducible with frozen artifacts in the current audited working tree; clean-checkout reproduction is not validated.** The five final checkpoints, per-run training configs/environment manifests, matched evaluation seed schedules, and raw trajectory/results artifacts exist and their SHA-256 hashes are recorded. Evaluation/re-scoring commands can be rerun against these checkpoints and trajectories using the current working-tree sources. The repository base commit is `" + str(manifest["code_revision"]["base_commit"]) + "`, but the working tree is dirty and contains uncommitted/untracked experiment runners; a clean checkout at that commit does not contain the full final pipeline.",
        "Historical PPO training has saved configurations and a documented CLI reconstruction (`--seed`, `--total-timesteps 100000`); exact bitwise checkpoint reproduction and clean-checkout training were not tested. Re-running training writes new checkpoints and is not required for the reported Step 5/7/8 evaluations.",
        "", "## Frozen Scientific Contracts", "",
        f"- State: 7 binary resistance components (128 profiles), elapsed step; PPO observation has 15 float32 values including one-hot last action.",
        f"- Action IDs: {', '.join(f'{index}={name}' for index, name in enumerate(manifest['action_order']))}.",
        "- Mask: only currently susceptible actions are feasible; all-resistant is terminal.",
        "- Primary transition: `REF_UNIFORM_SUPPORTED`; deduplicate by target/outcome and uniformly select an applicable supported candidate; no candidate means unchanged state with `unsupported_no_candidate`.",
        r"- Reward: $r_t=-N_R(s_{t+1})/7$, $H=8$, $\gamma=1$; an all-resistant state is charged through the remaining horizon. There is no separate effectiveness bonus, future-option bonus, or unnecessary-exposure objective.",
        "- PPO: MaskablePPO MlpPolicy, [64, 64], training configs/hash per seed below; deterministic action inference with susceptibility mask for evaluation.",
        "- Greedy: `GreedyPolicy` chooses uniformly from susceptible canonical action IDs using private `random.Random(seed)` per episode.",
        "- Deterministic reference: `REF_DETERMINISTIC_FIRST_SUPPORTED`, planning state profile + elapsed step, H=8, gamma=1, exact ties choose lowest feasible action ID; all-resistant terminal value is negative remaining horizon.",
        "", "## Checkpoint Inventory", "",
        "| Training seed | Type | Selected in final comparisons | Path | SHA-256 |",
        "|---:|---|---:|---|---|",
    ]
    lines.extend(f"| {item['training_seed']} | {item['checkpoint_type']} | {item['selected_for_final_comparisons']} | `{item['path']}` | `{item['sha256']}` |" for item in checkpoints)
    lines.extend([
        "", "The five final checkpoints used by Steps 2/4/5/7/8 are the `final` rows above. Best-validation checkpoints are inventoried but not used in the final reported comparisons.",
        "", "## Seed Inventory", "",
        "- Training seeds: `1000, 2000, 3000, 4000, 5000`; each uses PPO/environment/validation seeds `seed, seed+1, seed+2`.",
        "- Each trained run requested 100,000 timesteps; saved summaries report 100,096 actual timesteps because PPO completes full rollout batches.",
        "- Main evaluation: five saved evaluation schedules per checkpoint × 128 canonical profiles = 3,200 paired PPO/Greedy cases. Per-checkpoint reset and policy-seed pairs are retained in the matched output configs.",
        "- Initial profile order is canonical `itertools.product((0,1), repeat=7)`, with 0 susceptible and 1 resistant.",
        "", "## Experiment Inventory", "",
        "| Experiment | Purpose / condition | Canonical outputs | Status |",
        "|---|---|---|---|",
    ])
    for name, item in experiment_inventory["experiments"].items():
        outputs = ", ".join(item["outputs"][:3]) or "none"
        condition = item["transition"]
        if isinstance(condition, list):
            condition = ", ".join(condition)
        lines.append(f"| {name} | {item['purpose']} Transition: {condition}. | `{outputs}` | {item['status']} |")
    lines.extend([
        "", "### Step 6 Interpretation", "",
        "Step 6 is a limitation finding, not a positive held-out-state result: training cycles through all 127 nonterminal resistance profiles as starts, and stored episode summaries do not certify observation-level nonvisitation.",
        "", "### Step 8 Interpretation", "",
        "Step 8 re-scores the same 3,200 matched trajectories under A normalized burden, B unnormalized burden, C emergence-only, and D terminal-only objectives. It does not retrain PPO under B/C/D.",
        "", "## Configuration Fingerprints", "",
        f"- Configuration SHA-256: `{manifest['configuration_fingerprint']}`",
        f"- Environment SHA-256: `{manifest['environment_fingerprint']}`",
        f"- Transition/data SHA-256: `{manifest['transition_fingerprint']}`",
        f"- Reward SHA-256: `{manifest['reward_fingerprint']}`",
        "- Fingerprint input details and source file hashes are in `configuration_fingerprints.json`; timestamps/absolute paths are excluded from the scientific configuration hash.",
        "", "## Existing Result Directories", "",
        *[f"- `{path}`" for path in experiment_inventory["existing_result_directories"]],
        "", "## Reproduction Commands", "",
        "Commands use fresh output paths. The training block is optional when reproducing reported evaluation results from the frozen checkpoints; run it only to reconstruct training.",
    ])
    for command_group, command_value in experiment_inventory["reproduction_commands"].items():
        lines.extend(["", f"### {command_group.replace('_', ' ').title()}", "", "```powershell"])
        if command_group == "training":
            lines.extend(command_value["commands"])
        elif command_group == "matched_ppo_vs_greedy":
            lines.append(command_value[0] + " `")
            lines.extend(command + (" `" if index < len(command_value) - 1 else "") for index, command in enumerate(command_value[1:], start=1))
        else:
            lines.extend(command_value if isinstance(command_value, list) else [str(command_value)])
        lines.extend(["```"])
    lines.extend([
        "", "## Integrity and Limitations", "",
        f"`artifact_integrity.json` covers {manifest['integrity_file_count']} important source/checkpoint/result files. Verify without rerunning experiments using the package README command. A mismatch fails verification rather than silently accepting changed artifacts.",
        "- Step 5's saved directory has no top-level config or explicit interaction-data fingerprint. This package reconstructs its contracts from `compatibility.json`, saved checkpoint hashes, the matched source config, and the Step 2/7 environment fingerprint; this is recorded as a provenance gap, not silently treated as native metadata.",
        "- The base Git revision does not include the uncommitted/untracked experiment runners; source-file hashes capture the audited working-tree implementation, but no commit binds those files yet.",
        "- Step 7 transition modes are computational candidate-selection rules, not empirically estimated biological probabilities.",
        "- Gentamicin's unchanged unsupported outcome reflects a limitation of the computational candidate model and is not biological or clinical benefit.",
        "- No clinical efficacy or patient-level claims are established. Unnecessary antibiotic exposure is not explicitly modeled.",
        "- A clean checkout was not created or tested. The complete pipeline depends on the current dirty working tree and locally present frozen artifacts.",
        "", "The manifest documents provenance and integrity; it does not establish scientific or clinical validity.",
    ])
    return "\n".join(lines) + "\n"


def _package_readme() -> str:
    commands = _commands()
    lines = [
        "# Reproducibility Package", "",
        "Canonical artifacts remain in their original `experiments/results` locations; this package records references and hashes rather than copying checkpoints or trajectories.",
        "", "## Environment", "",
        "```powershell", *commands["install"], "```", "",
        "Use the recorded Python 3.11 environment. The `requirements-lock.txt` file is an environment snapshot; the documented setup installs the repository's `requirements.txt`.",
        "", "## Frozen PPO Training Reconstruction", "",
        "These reproduce the saved 100,000-step requested budgets with fresh output directories; actual completed timesteps are 100,096 due to rollout batch boundaries. Training is not required when using the existing frozen checkpoints.", "",
    ]
    for command in commands["training"]["commands"]:
        lines.extend(["```powershell", command, "```", ""])
    lines.extend([
        "## Matched Evaluation", "", "The model paths below refer to the fresh training outputs above. The same command can point at the frozen canonical checkpoints when only reproducing evaluation.", "", "```powershell",
    ])
    matched = commands["matched_ppo_vs_greedy"]
    lines.append(matched[0] + " `")
    lines.extend(command + (" `" if index < len(matched) - 1 else "") for index, command in enumerate(matched[1:], start=1))
    lines.extend(["```", ""])
    for heading, key in (
        ("Gentamicin Audit", "gentamicin_audit"),
        ("Decision Traces", "decision_traces"),
        ("Step 5 PPO vs Value Iteration", "step5_ppo_vs_value_iteration"),
        ("Step 7 Transition Sensitivity", "step7_transition_sensitivity"),
        ("Step 8 Reward/Objective Re-scoring", "step8_reward_objective_rescoring"),
    ):
        lines.extend([f"## {heading}", "", "```powershell", *commands[key], "```", ""])
    lines.extend([
        "## Tests and Integrity", "", "```powershell", *commands["tests"], "```", "",
        "```powershell", *commands["integrity_verification"], "```", "",
        "See `reproduction_report.md` for reproducibility status, frozen contracts, checkpoint hashes, fingerprints, Step 6 limitation, and provenance gaps.", "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the AMR experiment reproducibility package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="experiments/results/reproducibility_step9_final")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--package-dir", default="experiments/results/reproducibility_step9_final")
    args = parser.parse_args()
    if args.verify:
        result = verify_reproducibility_package(args.repo_root, args.package_dir)
        print(json.dumps(result, indent=2, allow_nan=False))
        if not result["ok"]:
            raise SystemExit(1)
        return
    manifest = build_reproducibility_package(args.repo_root, args.output_dir)
    print(json.dumps({
        "configuration_fingerprint": manifest["configuration_fingerprint"],
        "integrity_file_count": manifest["integrity_file_count"],
        "output_dir": canonical_relative_path(args.output_dir),
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()