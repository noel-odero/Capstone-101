"""Multi-seed PPO study: fixed protocol, run ledger, manifest, and statistics."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any, Sequence

from ml.src.confidence_intervals import t_confidence_interval
from ml.src.matched_policy_evaluation import BURDEN_TIE_TOLERANCE, run_matched_ppo_seed_ensemble
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, config_for_seed, train_ppo
from ml.src.statistical_comparison import paired_bootstrap_interval


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_ROOT = REPO_ROOT / "experiments" / "results"
STUDY_ROOT = CANONICAL_ROOT / "ppo_step9a_multiseed"
BASELINE_CONFIG_PATH = REPO_ROOT / "experiments" / "ppo_baseline_config.json"
STUDY_ID = "ppo_step9a_multiseed"

RETAINED_SEEDS = (1000, 2000, 3000, 4000, 5000)
NEW_SEEDS = tuple(range(6000, 20001, 1000))
TRAINING_SEEDS = RETAINED_SEEDS + NEW_SEEDS
# Configured budget; PPO realizes whole rollouts, so the accepted count is expected_realized_timesteps().
TOTAL_TIMESTEPS = 100000
PRIMARY_METRIC = "cumulative_resistance_burden"
SECONDARY_METRICS = ("final_resistant_antibiotics", "resistance_emergence_rate")
METRIC_COLUMNS = {
    "cumulative_resistance_burden": {
        "ppo": "ppo_cumulative_resistance_burden",
        "greedy": "greedy_cumulative_resistance_burden",
        "difference": "greedy_minus_ppo_burden",
    },
    "final_resistant_antibiotics": {
        "ppo": "ppo_final_resistant_antibiotics",
        "greedy": "greedy_final_resistant_antibiotics",
        "difference": "greedy_minus_ppo_final_resistant",
    },
    "resistance_emergence_rate": {
        "ppo": "ppo_resistance_emergence_rate",
        "greedy": "greedy_resistance_emergence_rate",
        "difference": "greedy_minus_ppo_resistance_emergence_rate",
    },
}
GREEDY_COLUMNS = tuple(columns["greedy"] for columns in METRIC_COLUMNS.values())
CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_SEED = 31415
BOOTSTRAP_RESAMPLES = 10000
# Shared with the per-profile counts in matched_policy_evaluation; see BURDEN_TIE_TOLERANCE there for the basis.
TIE_TOLERANCE = BURDEN_TIE_TOLERANCE
TIE_TOLERANCE_BASIS = (
    "Nonzero cumulative-burden differences are multiples of 1/(7 x 640), about 2.2e-4; analytic float64 error is "
    "about 2e-14; 1e-12 lies between these scales. Applies to cumulative_resistance_burden only; secondary ratio "
    "metrics use the same threshold without this granularity argument."
)
TRAINING_FINGERPRINT_FIELDS = (
    "scenario_id",
    "horizon",
    "total_timesteps",
    "learning_rate",
    "n_steps",
    "batch_size",
    "n_epochs",
    "gamma",
    "gae_lambda",
    "ent_coef",
    "clip_range",
    "policy_architecture",
    "training_profile_design",
    "evaluation_frequency",
    "evaluation_episodes",
    "device",
)
PROBLEM_PRECEDENCE = ("missing", "interrupted", "failed", "incomplete", "incompatible", "duplicate")
PROTOCOL_LOCK_NAME = "protocol_lock.json"
EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_REFUSED = 2
EXIT_RUN_FAILED = 3
FAILURE_RECOVERY = (
    "Failed or interrupted seeds are never deleted: quarantine --seed S --reason TEXT moves the seed's ledger and run directory to root/quarantine/.",
    "Only a seed whose ledger status is failed or started can be quarantined by default. A completed seed is quarantined only with --invalid-completed, and only when verify reports its training as invalid; a completed seed that verifies complete is never quarantined.",
    "Before quarantining an interrupted seed, confirm that no training process is still writing to its run directory.",
    "After quarantine, train --seed S reruns the same seed under the unchanged protocol; the seed set and protocol are not altered. A quarantined completed seed keeps its ledger, checkpoint, and metadata in quarantine as evidence.",
    "Quarantining any training seed leaves an existing evaluation incompatible; run quarantine-evaluation --reason TEXT before evaluate is rerun.",
    "An evaluation whose checkpoint or metadata bytes differ from the verified training hashes, or that changes before it is committed, is recorded as failed.",
    "If the seed set or any protocol field changes, the protocol lock mismatches; train refuses unless --confirm-protocol-change is given, which moves the old lock and all batch state (ledgers, training runs, evaluation, manifest) to quarantine.",
    "verify must report protocol_lock match and training_complete before evaluate or report will run.",
    "A failed, interrupted, or invalid evaluation is never deleted: quarantine-evaluation --reason TEXT moves run_ledger/evaluation.json and evaluation/ to root/quarantine/ after verify reports the evaluation is not complete.",
    "A completed, valid evaluation is never quarantined or overwritten; evaluate refuses while any evaluation ledger or output directory exists.",
    "Quarantining an evaluation touches only the evaluation ledger and output; training runs, training ledgers, the protocol lock, and the seed set are unchanged. Confirm no evaluate process is still running first.",
    "After quarantine-evaluation, evaluate reruns the shared-schedule evaluation once; it is not a partial resume.",
)


class StudyRefusal(Exception):
    """A requested action was refused before training or evaluation started; study state is unchanged."""
# Pinned from the Step 9 integrity inventory; canonical checkpoints must match these.
CANONICAL_CHECKPOINT_SHA256 = {
    1000: "c08bb537792e38688bb8af08269ab51d9cb84f74a2ef15039ea5c1c572633d00",
    2000: "fd17d5af7d4fa4eaf3e6b5d7f62167d40a5364aea6bfbfaa065118a1f852f3dd",
    3000: "11ee3d1d37036e5504ab3b65bb818aba760c0efab0e1ac1636759271689cf843",
    4000: "ec777b0966ccef05b2b516a9d90435799aeaa277329e8c6af5cf645fc485cae0",
    5000: "1366af12aff1cf8d50052f501fdc56fde74dec9773b4772d7ae6bd83abf3ae54",
}
# Checkpoint metadata files whose hashes are recorded at training completion and bound into the evaluation.
METADATA_FILES = ("config.json", "training_summary.json")
# Pinned read-only from the retained canonical run directories; any other content is refused.
CANONICAL_METADATA_SHA256 = {
    1000: {
        "config.json": "0bb53cc6b161f273f50cc850b443535297c6cd7658ba30dfcce5d00cabcc4a75",
        "training_summary.json": "88360552bf701c0875342e75dcda7e0fc2b49373a2c5f41c58c468c0ca9f3fa5",
    },
    2000: {
        "config.json": "2627b46aaa405c935bb59a77c96bd8b97220673789de567f92d77f9d85b32729",
        "training_summary.json": "7d85ab9594e43fc04b62a796ab100d0c42a644c50ef85bb5c34e34fcaef53947",
    },
    3000: {
        "config.json": "9554e7e153668b80fcc460f8282a0d17b1b49acee90ca19b733965d8a4d09379",
        "training_summary.json": "adf6e4ab278a8a7d5f75bab5e52209084364717dfad74c51534a84605cc5e58a",
    },
    4000: {
        "config.json": "c077ff257b27ecd6755f842848d01b096887ed2545b7594bc2e9f7a2871902ce",
        "training_summary.json": "853caeb0c5171c52ffcfa4271843b9fc455bd0fc2537b5e6178578eb5f122b03",
    },
    5000: {
        "config.json": "7369dabde9d6e9ee35eac9336b623d9582c2611a8192d680319d319740513f60",
        "training_summary.json": "4256813bccc3b58b0e4dfe3db6a925fe27722f641a50328d2664cd00b8faa346",
    },
}
# Feasibility is a construction constraint, not a measured outcome. The PPO path raises RuntimeError
# when MaskablePPO selects an infeasible action (ppo_evaluation.py), and GreedyPolicy samples only
# susceptible actions (greedy_policy.py). AntibioticEnvironment.step does not itself reject
# non-susceptible actions, so the constraint is enforced by the policies, not by the environment.
# No violation counter is recorded: a completed evaluation implies zero violations by construction.
FEASIBILITY_GATE = {
    "infeasible_selections_allowed": 0,
    "enforcement": "construction",
    "basis": "MaskablePPOObservationPolicy raises RuntimeError on infeasible PPO actions; GreedyPolicy samples susceptible actions only",
    "environment_step_rejects_infeasible_actions": False,
    "measured_outcome": False,
    "violation_counter": None,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_hashes(run_dir: Path) -> dict[str, str]:
    """SHA-256 of each checkpoint metadata file; raises if one is missing so the caller records a failure."""
    return {name: _sha256_file(run_dir / name) for name in METADATA_FILES}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _load_json(path: Path, problems: list[dict[str, str]]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        _flag(problems, "incompatible", f"unreadable JSON {path.name}: {error}")
        return None


def _flag(problems: list[dict[str, str]], category: str, message: str) -> None:
    if category not in PROBLEM_PRECEDENCE:
        raise ValueError(f"Unknown problem category: {category}")
    problems.append({"category": category, "message": message})


def _status(problems: list[dict[str, str]]) -> str:
    if not problems:
        return "complete"
    return min((problem["category"] for problem in problems), key=PROBLEM_PRECEDENCE.index)


def _check_study_root(root: Path | str) -> Path:
    resolved = Path(root).resolve()
    if resolved.parent == CANONICAL_ROOT.resolve() and resolved != STUDY_ROOT.resolve():
        raise StudyRefusal(f"Refusing to write study output into canonical result area: {resolved}")
    return resolved


def _training_name(seed: int) -> str:
    return f"training_seed_{seed}"


def _ledger_path(root: Path, name: str) -> Path:
    return root / "run_ledger" / f"{name}.json"


def _run_directory(seed: int, *, root: Path, canonical_root: Path) -> Path:
    if seed in RETAINED_SEEDS:
        return canonical_root / f"ppo_seed_{seed}"
    return root / "training" / f"ppo_seed_{seed}"


def protocol_config(training_seed: int) -> PPOConfig:
    """Return the baseline PPO configuration with the fixed study budget and one training seed."""
    base = PPOConfig.from_json(BASELINE_CONFIG_PATH)
    return config_for_seed(replace(base, total_timesteps=TOTAL_TIMESTEPS), training_seed)


def expected_realized_timesteps(n_steps: int) -> int:
    """Smallest whole-rollout count that reaches the configured budget (100096 at n_steps=256)."""
    if n_steps <= 0:
        raise ValueError("n_steps must be positive.")
    return -(-TOTAL_TIMESTEPS // n_steps) * n_steps


def training_fingerprint(record: dict[str, Any]) -> str:
    """Hash the training-relevant fields of a configuration record, excluding seeds."""
    selected = {name: record[name] for name in TRAINING_FINGERPRINT_FIELDS}
    return _sha256_text(_canonical_json(selected))


def expected_training_fingerprint() -> str:
    return training_fingerprint(protocol_config(TRAINING_SEEDS[0]).to_dict())


def protocol_record() -> dict[str, Any]:
    base = protocol_config(TRAINING_SEEDS[0])
    return {
        "training_seeds": list(TRAINING_SEEDS),
        "retained_canonical_seeds": list(RETAINED_SEEDS),
        "new_training_seeds": list(NEW_SEEDS),
        "total_timesteps": TOTAL_TIMESTEPS,
        "realized_total_timesteps": expected_realized_timesteps(base.n_steps),
        "training_fingerprint_fields": list(TRAINING_FINGERPRINT_FIELDS),
        "expected_training_fingerprint": expected_training_fingerprint(),
        "evaluation_schedule": "shared_schedule",
        "evaluation_seed_bases": list(base.matched_evaluation_seed_bases),
        "matched_policy_seed_start": base.matched_policy_seed_start,
        "primary_metric": PRIMARY_METRIC,
        "secondary_metrics": list(SECONDARY_METRICS),
        "difference_definition": "Greedy minus PPO, mean over matched cases per training seed; positive favors PPO",
        "tie_tolerance": TIE_TOLERANCE,
        "tie_tolerance_basis": TIE_TOLERANCE_BASIS,
        "primary_interval": f"two-sided Student-t, confidence {CONFIDENCE_LEVEL}, df = seeds - 1",
        "sensitivity_interval": f"percentile paired bootstrap, seed {BOOTSTRAP_SEED}, {BOOTSTRAP_RESAMPLES} resamples",
        "statistical_tests": "none",
    }


def _protocol_fingerprint() -> str:
    return _sha256_text(_canonical_json(protocol_record()))


def _protocol_lock_path(root: Path) -> Path:
    return root / PROTOCOL_LOCK_NAME


def _protocol_lock_status(root: Path) -> str:
    """Return absent, match, mismatch, or unreadable for the protocol lock under root."""
    path = _protocol_lock_path(root)
    if not path.exists():
        return "absent"
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    return "match" if lock.get("protocol_fingerprint") == _protocol_fingerprint() else "mismatch"


def _write_protocol_lock(root: Path) -> None:
    _write_json(
        _protocol_lock_path(root),
        {"protocol_fingerprint": _protocol_fingerprint(), "protocol": protocol_record(), "locked_utc": _utc_now()},
    )


def _quarantine_directory(root: Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = root / "quarantine" / f"{stamp}_{label}"
    if destination.exists():
        raise StudyRefusal(f"Quarantine destination already exists: {destination}")
    destination.mkdir(parents=True)
    return destination


def _batch_state_paths(root: Path) -> list[Path]:
    """Every path the batch writes under root. Retained canonical runs live outside root and are never listed."""
    return [root / "run_ledger", root / "training", root / "evaluation", root / "manifest.json"]


def _admit_protocol(root: Path, confirm_protocol_change: bool) -> None:
    """Write the protocol lock on first training; refuse a changed protocol unless explicitly confirmed.

    A confirmed change moves the old lock and all batch state (ledgers, training runs, evaluation, manifest)
    to one quarantine directory, so no artifact from the old protocol can be read into the new batch.
    """
    status = _protocol_lock_status(root)
    if status == "match":
        return
    present = [path for path in _batch_state_paths(root) if path.exists()]
    if status == "absent" and not present:
        _write_protocol_lock(root)
        return
    if not confirm_protocol_change:
        detail = "no lock exists but batch state is present" if status == "absent" else f"protocol lock is {status}"
        raise StudyRefusal(
            f"Protocol lock is {status}; {detail}. The protocol differs from the one this study was started under. "
            "Pass --confirm-protocol-change only if the change is intended."
        )
    destination = _quarantine_directory(root, "protocol_change")
    moved = []
    lock_path = _protocol_lock_path(root)
    if lock_path.exists():
        shutil.move(str(lock_path), str(destination / PROTOCOL_LOCK_NAME))
        moved.append(PROTOCOL_LOCK_NAME)
    for path in present:
        shutil.move(str(path), str(destination / path.name))
        moved.append(path.name)
    _write_json(
        destination / "quarantine_reason.json",
        {
            "reason": "protocol change confirmed; batch state moved so it cannot mix with the new protocol",
            "previous_lock_status": status,
            "moved": moved,
            "quarantined_utc": _utc_now(),
        },
    )
    _write_protocol_lock(root)


def quarantine_seed(
    training_seed: int,
    reason: str,
    root: Path | str = STUDY_ROOT,
    *,
    invalid_completed: bool = False,
    canonical_root: Path | str = CANONICAL_ROOT,
) -> Path:
    """Move a failed, interrupted, or integrity-invalid completed seed aside; nothing is deleted.

    A completed seed is quarantined only when ``invalid_completed`` is set and verification reports its training
    as invalid. A completed seed that verifies complete is never quarantined.
    """
    if training_seed not in NEW_SEEDS:
        raise StudyRefusal(f"Seed {training_seed} is not a new study seed; retained seeds cannot be quarantined.")
    if not reason.strip():
        raise StudyRefusal("A non-empty quarantine reason is required.")
    root = _check_study_root(root)
    ledger_path = _ledger_path(root, _training_name(training_seed))
    if not ledger_path.exists():
        raise StudyRefusal(f"No run ledger for seed {training_seed}; nothing to quarantine.")
    try:
        previous = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StudyRefusal(f"Run ledger for seed {training_seed} is unreadable ({error}); it is not quarantined.") from error
    if not isinstance(previous, dict):
        raise StudyRefusal(f"Run ledger for seed {training_seed} is not a JSON object; it is not quarantined.")
    status = previous.get("status")
    verification: dict[str, Any] | None = None
    if invalid_completed:
        if status != "completed":
            raise StudyRefusal(
                f"--invalid-completed applies only to a completed ledger; seed {training_seed} ledger status is {status!r}."
            )
        batch = _verify_training_batch(root, canonical_root=Path(canonical_root))
        record = next(item for item in batch if item["training_seed"] == training_seed)
        if record["status"] == "complete":
            raise StudyRefusal(
                f"Seed {training_seed} completed and verifies complete; valid completed training is never quarantined."
            )
        verification = {"status": record["status"], "problems": record["problems"]}
    elif status not in {"failed", "started"}:
        raise StudyRefusal(
            f"Seed {training_seed} ledger status is {status!r}; only failed or started seeds are quarantined. "
            "An integrity-invalid completed seed requires --invalid-completed."
        )
    run_dir = _run_directory(training_seed, root=root, canonical_root=CANONICAL_ROOT)
    had_run_directory = run_dir.exists()
    destination = _quarantine_directory(root, _training_name(training_seed))
    shutil.move(str(ledger_path), str(destination / "run_ledger.json"))
    if had_run_directory:
        shutil.move(str(run_dir), str(destination / "run_directory"))
    _write_json(
        destination / "quarantine_reason.json",
        {
            "training_seed": training_seed,
            "reason": reason,
            "previous_ledger": previous,
            "invalid_completed": invalid_completed,
            "verification": verification,
            "run_directory_moved": had_run_directory,
            "quarantined_utc": _utc_now(),
        },
    )
    return destination


def quarantine_evaluation(reason: str, root: Path | str = STUDY_ROOT) -> Path:
    """Move a failed, interrupted, or invalid evaluation aside so it can be rerun; nothing is deleted.

    Refuses when the evaluation verifies complete. Touches only run_ledger/evaluation.json and evaluation/;
    training runs, training ledgers, the protocol lock, and the seed set are left unchanged.
    """
    if not reason.strip():
        raise StudyRefusal("A non-empty quarantine reason is required.")
    root = _check_study_root(root)
    evaluation = build_manifest(root)["evaluation"]
    if evaluation["status"] == "complete":
        raise StudyRefusal("Evaluation verifies complete; a completed, valid evaluation is never quarantined or overwritten.")
    ledger_path = _ledger_path(root, "evaluation")
    eval_dir = root / "evaluation"
    if not ledger_path.exists() and not eval_dir.exists():
        raise StudyRefusal("No evaluation ledger or output directory; nothing to quarantine.")
    previous: Any = None
    if ledger_path.exists():
        try:
            previous = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {"readable": False}
    destination = _quarantine_directory(root, "evaluation")
    moved: dict[str, str] = {}
    if ledger_path.exists():
        target = destination / "run_ledger_evaluation.json"
        shutil.move(str(ledger_path), str(target))
        moved[str(ledger_path)] = str(target)
    if eval_dir.exists():
        target = destination / "evaluation"
        shutil.move(str(eval_dir), str(target))
        moved[str(eval_dir)] = str(target)
    _write_json(
        destination / "quarantine_reason.json",
        {
            "reason": reason,
            "verification_status": evaluation["status"],
            "verification_problems": [problem["message"] for problem in evaluation["problems"]],
            "previous_ledger": previous,
            "moved_paths": moved,
            "quarantined_utc": _utc_now(),
        },
    )
    return destination


def train_new_seed(
    training_seed: int,
    root: Path | str = STUDY_ROOT,
    *,
    confirm_protocol_change: bool = False,
) -> dict[str, Any]:
    """Train one new study seed at the fixed budget and record its outcome in the run ledger."""
    if training_seed not in NEW_SEEDS:
        raise StudyRefusal(f"Seed {training_seed} is not a new study seed; retained seeds are not retrained.")
    root = _check_study_root(root)
    _admit_protocol(root, confirm_protocol_change)
    ledger_path = _ledger_path(root, _training_name(training_seed))
    if ledger_path.exists():
        raise StudyRefusal(
            f"Run ledger already exists for seed {training_seed}; refusing duplicate training. "
            "Use quarantine for a failed or interrupted seed."
        )
    run_dir = _run_directory(training_seed, root=root, canonical_root=CANONICAL_ROOT)
    if run_dir.exists():
        raise StudyRefusal(f"Run directory already exists for seed {training_seed}: {run_dir}")
    config = protocol_config(training_seed)
    record: dict[str, Any] = {
        "training_seed": training_seed,
        "status": "started",
        "total_timesteps": config.total_timesteps,
        "run_dir": str(run_dir),
        "started_utc": _utc_now(),
        "finished_utc": None,
        "elapsed_seconds": None,
        "error": None,
        "metadata_sha256": None,
        "checkpoint_sha256": None,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("x", encoding="utf-8") as ledger_file:
        json.dump(record, ledger_file, indent=2, allow_nan=False)
    started = time.perf_counter()
    try:
        train_ppo(config, run_dir)
        metadata = _metadata_hashes(run_dir)
        checkpoint = _sha256_file(run_dir / "final_model.zip")
    except Exception as error:
        record.update(
            status="failed",
            finished_utc=_utc_now(),
            elapsed_seconds=time.perf_counter() - started,
            error=f"{type(error).__name__}: {error}",
        )
        _write_json(ledger_path, record)
        raise
    record.update(
        status="completed",
        finished_utc=_utc_now(),
        elapsed_seconds=time.perf_counter() - started,
        metadata_sha256=metadata,
        checkpoint_sha256=checkpoint,
    )
    _write_json(ledger_path, record)
    return record


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _check_training_artifacts(
    seed: int,
    run_dir: Path,
    record: dict[str, Any],
    *,
    pinned_checkpoint_hashes: dict[int, str],
    expected_metadata: dict[str, str] | None,
    expected_fingerprint: str,
) -> None:
    problems = record["problems"]
    config_path = run_dir / "config.json"
    summary_path = run_dir / "training_summary.json"
    checkpoint = run_dir / "final_model.zip"
    absent = [path.name for path in (config_path, summary_path, checkpoint) if not path.is_file()]
    if absent:
        _flag(problems, "incomplete", f"missing artifacts: {', '.join(absent)}")
        return
    config = _load_json(config_path, problems)
    summary = _load_json(summary_path, problems)
    if config is not None:
        absent_fields = [name for name in TRAINING_FINGERPRINT_FIELDS if name not in config]
        if absent_fields:
            _flag(problems, "incompatible", f"config lacks fields: {', '.join(absent_fields)}")
        else:
            record["config_fingerprint"] = training_fingerprint(config)
            if record["config_fingerprint"] != expected_fingerprint:
                _flag(problems, "incompatible", "training configuration differs from protocol")
        seeds_found = (config.get("ppo_seed"), config.get("environment_seed"), config.get("evaluation_seed"))
        if seeds_found != (seed, seed + 1, seed + 2):
            _flag(problems, "incompatible", f"seed fields {seeds_found} differ from protocol")
    if summary is not None:
        timesteps = summary.get("total_timesteps")
        n_steps = config.get("n_steps") if config is not None else None
        if not isinstance(timesteps, int) or timesteps < TOTAL_TIMESTEPS:
            _flag(problems, "incomplete", f"training stopped at {timesteps}; below configured budget {TOTAL_TIMESTEPS}")
        elif isinstance(n_steps, int) and n_steps > 0 and timesteps != expected_realized_timesteps(n_steps):
            expected = expected_realized_timesteps(n_steps)
            _flag(problems, "incompatible", f"training realized {timesteps} timesteps; rollout-aligned count is {expected}")
    record["metadata_sha256"] = _metadata_hashes(run_dir)
    if expected_metadata is not None:
        for name in METADATA_FILES:
            if record["metadata_sha256"][name] != expected_metadata.get(name):
                _flag(
                    problems,
                    "incompatible",
                    f"{name} hash differs from the value recorded at training completion or the pinned canonical value",
                )
    record["checkpoint_sha256"] = _sha256_file(checkpoint)
    pinned = pinned_checkpoint_hashes.get(seed)
    if pinned is not None and record["checkpoint_sha256"] != pinned:
        _flag(problems, "incompatible", "checkpoint hash differs from pinned canonical value")


def _verify_training_run(
    seed: int,
    *,
    root: Path,
    canonical_root: Path,
    pinned_checkpoint_hashes: dict[int, str],
    pinned_metadata_hashes: dict[int, dict[str, str]],
    expected_fingerprint: str,
) -> dict[str, Any]:
    retained = seed in RETAINED_SEEDS
    run_dir = _run_directory(seed, root=root, canonical_root=canonical_root)
    ledger_path = _ledger_path(root, _training_name(seed))
    record: dict[str, Any] = {
        "training_seed": seed,
        "source": "canonical" if retained else "study",
        "run_dir": str(run_dir),
        "ledger": None if retained else str(ledger_path),
        "status": None,
        "problems": [],
        "elapsed_seconds": None,
        "config_fingerprint": None,
        "checkpoint": str(run_dir / "final_model.zip"),
        "checkpoint_sha256": None,
        "metadata_sha256": None,
    }
    problems = record["problems"]
    expected_metadata = pinned_metadata_hashes.get(seed) if retained else None
    expected_checkpoint: str | None = None
    if not retained:
        if ledger_path.exists():
            ledger = _load_json(ledger_path, problems)
            if isinstance(ledger, dict):
                record["elapsed_seconds"] = ledger.get("elapsed_seconds")
                if ledger.get("training_seed") != seed:
                    _flag(problems, "incompatible", "ledger seed differs from file name")
                ledger_status = ledger.get("status")
                if ledger_status == "failed":
                    _flag(problems, "failed", f"training failed: {ledger.get('error')}")
                elif ledger_status == "started":
                    _flag(problems, "interrupted", "training started but no completion was recorded")
                elif ledger_status != "completed":
                    _flag(problems, "incompatible", f"unknown ledger status: {ledger_status}")
                else:
                    expected_metadata = ledger.get("metadata_sha256")
                    if not isinstance(expected_metadata, dict) or set(expected_metadata) != set(METADATA_FILES):
                        _flag(problems, "incompatible", "completed ledger records no metadata hashes")
                        expected_metadata = None
                    expected_checkpoint = ledger.get("checkpoint_sha256")
                    if not _is_sha256(expected_checkpoint):
                        _flag(problems, "incompatible", "completed ledger records no checkpoint hash")
                        expected_checkpoint = None
        else:
            _flag(problems, "missing", "no run ledger entry")
            if run_dir.exists():
                _flag(problems, "incompatible", "run directory exists without a run ledger entry")
    if not run_dir.exists():
        _flag(problems, "missing", "run directory is missing")
    else:
        _check_training_artifacts(
            seed,
            run_dir,
            record,
            pinned_checkpoint_hashes=pinned_checkpoint_hashes,
            expected_metadata=expected_metadata,
            expected_fingerprint=expected_fingerprint,
        )
        if (
            expected_checkpoint is not None
            and record["checkpoint_sha256"] is not None
            and record["checkpoint_sha256"] != expected_checkpoint
        ):
            _flag(problems, "incompatible", "checkpoint hash differs from the value recorded at training completion")
    return record


def _mark_duplicate_checkpoints(records: list[dict[str, Any]]) -> None:
    owners: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["checkpoint_sha256"]:
            owners[record["checkpoint_sha256"]].append(record)
    for group in owners.values():
        if len(group) > 1:
            seeds = [str(record["training_seed"]) for record in group]
            for record in group:
                _flag(record["problems"], "duplicate", f"checkpoint bytes shared with seeds {', '.join(seeds)}")


def _unexpected_entries(root: Path, seeds: Sequence[int]) -> list[str]:
    expected_ledgers = {_training_name(seed) for seed in seeds}
    expected_dirs = {f"ppo_seed_{seed}" for seed in seeds if seed not in RETAINED_SEEDS}
    unexpected = []
    ledger_dir = root / "run_ledger"
    if ledger_dir.exists():
        for path in sorted(ledger_dir.glob("training_seed_*.json")):
            if path.stem not in expected_ledgers:
                unexpected.append(f"unexpected run ledger: {path.name}")
    training_dir = root / "training"
    if training_dir.exists():
        for path in sorted(training_dir.iterdir()):
            if path.is_dir() and path.name not in expected_dirs:
                unexpected.append(f"unexpected training directory: {path.name}")
    return unexpected


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _optional_float(value: str) -> float | None:
    """Parse a CSV cell. An empty cell is an undefined rate (None), never zero."""
    return None if value == "" else float(value)


def _differs(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(a - b) > TIE_TOLERANCE


def _shared_evaluation_problems(rows: list[dict[str, str]], seeds: Sequence[int], bases: Sequence[int]) -> list[str]:
    expected_per_seed = len(bases) * len(canonical_initial_profiles())
    counts: dict[int, int] = defaultdict(int)
    greedy_by_case: dict[str, dict[int, tuple[float, ...]]] = defaultdict(dict)
    for row in rows:
        seed = int(row["ppo_training_seed"])
        counts[seed] += 1
        greedy_by_case[row["case_id"]][seed] = tuple(_optional_float(row[column]) for column in GREEDY_COLUMNS)
    problems = []
    for seed in seeds:
        if counts.get(seed, 0) != expected_per_seed:
            problems.append(f"seed {seed} has {counts.get(seed, 0)} rows; expected {expected_per_seed}")
    if set(counts) - set(seeds):
        problems.append("evaluation contains rows for unexpected training seeds")
    for case_id, by_seed in greedy_by_case.items():
        if len(by_seed) != len(seeds):
            problems.append(f"case {case_id} is not evaluated for every training seed")
            break
        first = next(iter(by_seed.values()))
        if any(_differs(a, b) for values in by_seed.values() for a, b in zip(values, first)):
            problems.append(f"Greedy baseline differs across training seeds for case {case_id}")
            break
    return problems


def _verify_evaluation(
    root: Path,
    seeds: Sequence[int],
    bases: Sequence[int],
    policy_seed_start: int,
    expected_by_seed: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    eval_dir = root / "evaluation"
    ledger_path = _ledger_path(root, "evaluation")
    record: dict[str, Any] = {
        "status": None,
        "output_dir": str(eval_dir),
        "ledger": str(ledger_path),
        "problems": [],
        "config_sha256": None,
        "summary_sha256": None,
        "raw_results_sha256": None,
    }
    problems = record["problems"]
    if ledger_path.exists():
        ledger = _load_json(ledger_path, problems)
        if isinstance(ledger, dict):
            ledger_status = ledger.get("status")
            if ledger_status == "failed":
                _flag(problems, "failed", f"evaluation failed: {ledger.get('error')}")
            elif ledger_status == "started":
                _flag(problems, "interrupted", "evaluation started but no completion was recorded")
            elif ledger_status != "completed":
                _flag(problems, "incompatible", f"unknown evaluation ledger status: {ledger_status}")
    else:
        _flag(problems, "missing", "no evaluation ledger entry")
    if not eval_dir.exists():
        _flag(problems, "missing", "evaluation output directory is missing")
    else:
        paths = {name: eval_dir / name for name in ("config.json", "summary.json", "raw_results.csv")}
        absent = [name for name, path in paths.items() if not path.is_file()]
        if absent:
            _flag(problems, "incomplete", f"missing artifacts: {', '.join(absent)}")
        else:
            config = _load_json(paths["config.json"], problems)
            summary = _load_json(paths["summary.json"], problems)
            if isinstance(config, dict):
                if config.get("evaluation_protocol") != "shared_schedule":
                    _flag(problems, "incompatible", "evaluation was not run under the shared schedule")
                schedules = config.get("evaluation_seed_bases_by_training_seed", {})
                if set(schedules) != {str(seed) for seed in seeds} or any(
                    list(value) != list(bases) for value in schedules.values()
                ):
                    _flag(problems, "incompatible", "evaluation seed schedules differ from protocol")
                policy_starts = config.get("policy_seed_start_by_training_seed", {})
                if set(policy_starts) != {str(seed) for seed in seeds} or any(
                    value != policy_seed_start for value in policy_starts.values()
                ):
                    _flag(problems, "incompatible", f"policy-seed start differs from protocol value {policy_seed_start}")
                recorded_hashes = config.get("checkpoint_sha256_by_training_seed", {})
                recorded_metadata = config.get("metadata_sha256_by_training_seed", {})
                for seed in seeds:
                    expected = expected_by_seed.get(seed, {})
                    expected_hash = expected.get("checkpoint_sha256")
                    if expected_hash is None or recorded_hashes.get(str(seed)) != expected_hash:
                        _flag(problems, "incompatible", f"checkpoint hash for seed {seed} differs from the verified training checkpoint")
                    expected_metadata = expected.get("metadata_sha256")
                    if expected_metadata is None or recorded_metadata.get(str(seed)) != expected_metadata:
                        _flag(problems, "incompatible", f"training metadata hashes for seed {seed} differ from the verified training record")
            if isinstance(summary, dict) and summary.get("training_seeds") != list(seeds):
                _flag(problems, "incompatible", "evaluated training seed order differs from protocol")
            rows = _read_rows(paths["raw_results.csv"])
            for message in _shared_evaluation_problems(rows, seeds, bases):
                _flag(problems, "incompatible", message)
            missing_models = [seed for seed in seeds if not (eval_dir / "models" / f"ppo_seed_{seed}").is_dir()]
            if missing_models:
                _flag(problems, "incomplete", f"missing per-model outputs for seeds {missing_models}")
            record["config_sha256"] = _sha256_file(paths["config.json"])
            record["summary_sha256"] = _sha256_file(paths["summary.json"])
            record["raw_results_sha256"] = _sha256_file(paths["raw_results.csv"])
    record["status"] = _status(problems)
    return record


def _verify_training_batch(
    root: Path,
    *,
    seeds: Sequence[int] = TRAINING_SEEDS,
    canonical_root: Path = CANONICAL_ROOT,
    pinned_checkpoint_hashes: dict[int, str] = CANONICAL_CHECKPOINT_SHA256,
    pinned_metadata_hashes: dict[int, dict[str, str]] = CANONICAL_METADATA_SHA256,
) -> list[dict[str, Any]]:
    """Verify each training run, cross-mark duplicate checkpoints, and set every record's status."""
    expected_fingerprint = protocol_record()["expected_training_fingerprint"]
    training = [
        _verify_training_run(
            seed,
            root=root,
            canonical_root=Path(canonical_root),
            pinned_checkpoint_hashes=pinned_checkpoint_hashes,
            pinned_metadata_hashes=pinned_metadata_hashes,
            expected_fingerprint=expected_fingerprint,
        )
        for seed in seeds
    ]
    _mark_duplicate_checkpoints(training)
    for record in training:
        record["status"] = _status(record["problems"])
    return training


def _revalidate_training_inputs(root: Path, expected_inputs: Sequence[dict[str, Any]]) -> None:
    """Re-verify the protocol lock and training batch just before an evaluation is committed.

    Uses the same manifest path as verify. Raises if the lock or batch no longer verifies complete, or if any
    checkpoint or metadata hash differs from the values the evaluation was run on; the caller then records the
    evaluation as failed.
    """
    manifest = build_manifest(root)
    problems: list[str] = []
    if manifest["protocol_lock"] != "match":
        problems.append(f"protocol lock is {manifest['protocol_lock']} at commit time")
    if not manifest["training_complete"]:
        problems.append("training batch no longer verifies complete at commit time")
    by_seed = {record["training_seed"]: record for record in manifest["training_runs"]}
    for item in expected_inputs:
        seed = item["training_seed"]
        record = by_seed[seed]
        if record["status"] != "complete":
            problems.append(f"seed {seed} is {record['status']} at commit time")
        elif record["checkpoint_sha256"] != item["checkpoint_sha256"] or record["metadata_sha256"] != item["metadata_sha256"]:
            problems.append(f"seed {seed} checkpoint or metadata bytes changed during evaluation")
    if problems:
        raise RuntimeError("; ".join(problems))


def build_manifest(
    root: Path | str = STUDY_ROOT,
    *,
    seeds: Sequence[int] = TRAINING_SEEDS,
    canonical_root: Path | str = CANONICAL_ROOT,
    pinned_checkpoint_hashes: dict[int, str] = CANONICAL_CHECKPOINT_SHA256,
    pinned_metadata_hashes: dict[int, dict[str, str]] = CANONICAL_METADATA_SHA256,
) -> dict[str, Any]:
    """Build the completeness manifest for training and evaluation without writing it."""
    root = Path(root)
    canonical_root = Path(canonical_root)
    protocol = protocol_record()
    training = _verify_training_batch(
        root,
        seeds=seeds,
        canonical_root=canonical_root,
        pinned_checkpoint_hashes=pinned_checkpoint_hashes,
        pinned_metadata_hashes=pinned_metadata_hashes,
    )
    unexpected = _unexpected_entries(root, seeds)
    training_complete = all(record["status"] == "complete" for record in training) and not unexpected
    evaluation = _verify_evaluation(
        root,
        seeds,
        tuple(protocol["evaluation_seed_bases"]),
        protocol["matched_policy_seed_start"],
        {
            record["training_seed"]: {
                "checkpoint_sha256": record["checkpoint_sha256"],
                "metadata_sha256": record["metadata_sha256"],
            }
            for record in training
            if record["status"] == "complete"
        },
    )
    evaluation_complete = evaluation["status"] == "complete"
    protocol_lock = _protocol_lock_status(root)
    problems = [
        f"training {record['training_seed']}: {record['status']} ("
        + "; ".join(problem["message"] for problem in record["problems"])
        + ")"
        for record in training
        if record["status"] != "complete"
    ]
    problems.extend(unexpected)
    if protocol_lock != "match":
        problems.append(f"protocol lock: {protocol_lock}")
    if not evaluation_complete:
        problems.append(
            f"evaluation: {evaluation['status']} ("
            + "; ".join(problem["message"] for problem in evaluation["problems"])
            + ")"
        )
    return {
        "study_id": STUDY_ID,
        "protocol": protocol,
        "protocol_fingerprint": _sha256_text(_canonical_json(protocol)),
        "training_seed_count": len(seeds),
        "training_complete": training_complete,
        "evaluation_complete": evaluation_complete,
        "complete": training_complete and evaluation_complete and protocol_lock == "match",
        "protocol_lock": protocol_lock,
        "failure_recovery": list(FAILURE_RECOVERY),
        "unexpected_entries": unexpected,
        "training_runs": training,
        "evaluation": evaluation,
        "historical_reference": {
            "path": str(CANONICAL_ROOT / "ppo_greedy_matched_five_seed_final"),
            "note": "Positional schedules; retained as historical evidence; not pooled with the shared-schedule study.",
        },
        "problems": problems,
    }


def verify_study(root: Path | str = STUDY_ROOT) -> dict[str, Any]:
    root = _check_study_root(root)
    manifest = build_manifest(root)
    _write_json(root / "manifest.json", manifest)
    return manifest


def evaluate_study(root: Path | str = STUDY_ROOT) -> dict[str, Any]:
    """Run the shared-schedule evaluation for all 20 checkpoints once training is complete."""
    root = _check_study_root(root)
    manifest = build_manifest(root)
    if not manifest["training_complete"]:
        raise StudyRefusal("Evaluation refused: training batch is incomplete. Run verify for details.")
    if manifest["protocol_lock"] != "match":
        raise StudyRefusal(f"Evaluation refused: protocol lock is {manifest['protocol_lock']}.")
    ledger_path = _ledger_path(root, "evaluation")
    evaluation = manifest["evaluation"]
    if ledger_path.exists() or (root / "evaluation").exists():
        if evaluation["status"] == "complete":
            raise StudyRefusal("Evaluation refused: a completed, valid evaluation exists and is never overwritten.")
        raise StudyRefusal(
            f"Evaluation refused: existing evaluation state is {evaluation['status']}. Run quarantine-evaluation --reason TEXT "
            "to move it aside, then evaluate again."
        )
    config = protocol_config(TRAINING_SEEDS[0])
    model_paths = [
        _run_directory(seed, root=root, canonical_root=CANONICAL_ROOT) / "final_model.zip"
        for seed in TRAINING_SEEDS
    ]
    verified = {item["training_seed"]: item for item in manifest["training_runs"]}
    expected_inputs = [
        {
            "training_seed": seed,
            "checkpoint_sha256": verified[seed]["checkpoint_sha256"],
            "metadata_sha256": verified[seed]["metadata_sha256"],
        }
        for seed in TRAINING_SEEDS
    ]
    record: dict[str, Any] = {
        "status": "started",
        "output_dir": str(root / "evaluation"),
        "started_utc": _utc_now(),
        "finished_utc": None,
        "elapsed_seconds": None,
        "error": None,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("x", encoding="utf-8") as ledger_file:
        json.dump(record, ledger_file, indent=2, allow_nan=False)
    started = time.perf_counter()
    try:
        ensemble = run_matched_ppo_seed_ensemble(
            model_paths,
            config,
            root / "evaluation",
            shared_evaluation_schedule=True,
            expected_inputs=expected_inputs,
        )
        _revalidate_training_inputs(root, expected_inputs)
    except Exception as error:
        record.update(
            status="failed",
            finished_utc=_utc_now(),
            elapsed_seconds=time.perf_counter() - started,
            error=f"{type(error).__name__}: {error}",
        )
        _write_json(ledger_path, record)
        raise
    record.update(status="completed", finished_utc=_utc_now(), elapsed_seconds=time.perf_counter() - started)
    _write_json(ledger_path, record)
    return {
        "training_seed_count": ensemble["summary"]["training_seed_count"],
        "matched_case_count": ensemble["summary"]["matched_case_count"],
        "output_dir": str(root / "evaluation"),
    }


def _defined_mean(values: Sequence[float | None]) -> float | None:
    defined = [value for value in values if value is not None]
    return statistics.mean(defined) if defined else None


def _per_seed_metrics(rows: list[dict[str, str]]) -> dict[int, dict[str, dict[str, Any]]]:
    """Per-seed means use defined case values only; undefined cells are excluded for that metric, never zero-filled."""
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["ppo_training_seed"])].append(row)
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for seed in TRAINING_SEEDS:
        seed_rows = grouped.get(seed, [])
        if not seed_rows:
            raise ValueError(f"No evaluation rows for training seed {seed}.")
        result[seed] = {}
        for metric, columns in METRIC_COLUMNS.items():
            differences = [_optional_float(row[columns["difference"]]) for row in seed_rows]
            result[seed][metric] = {
                "ppo_mean": _defined_mean([_optional_float(row[columns["ppo"]]) for row in seed_rows]),
                "greedy_mean": _defined_mean([_optional_float(row[columns["greedy"]]) for row in seed_rows]),
                "difference": _defined_mean(differences),
                "defined_case_count": sum(value is not None for value in differences),
            }
    return result


def _outcome(difference: float) -> str:
    """Classify a Greedy-minus-PPO difference; positive favors PPO (lower burden). Boundaries are inclusive for tied."""
    if difference > TIE_TOLERANCE:
        return "ppo_lower"
    if difference < -TIE_TOLERANCE:
        return "greedy_lower"
    return "tied"


def _metric_statistics(differences: Sequence[float]) -> dict[str, Any]:
    values = [float(value) for value in differences]
    outcomes = [_outcome(value) for value in values]
    primary_interval = t_confidence_interval(values, CONFIDENCE_LEVEL)
    sensitivity = paired_bootstrap_interval(
        values,
        seed=BOOTSTRAP_SEED,
        resamples=BOOTSTRAP_RESAMPLES,
        confidence_level=CONFIDENCE_LEVEL,
        independent_runs_assumed=True,
    )
    return {
        "training_seed_count": len(values),
        "mean_greedy_minus_ppo": statistics.mean(values),
        "standard_deviation": statistics.stdev(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "ppo_lower_seed_count": outcomes.count("ppo_lower"),
        "tied_seed_count": outcomes.count("tied"),
        "greedy_lower_seed_count": outcomes.count("greedy_lower"),
        "primary_t_interval": asdict(primary_interval),
        "bootstrap_sensitivity": asdict(sensitivity),
    }


def report_study(root: Path | str = STUDY_ROOT) -> dict[str, Any]:
    """Compute paired statistics only after the manifest reports a complete batch."""
    root = _check_study_root(root)
    manifest = build_manifest(root)
    if not manifest["complete"]:
        raise StudyRefusal("Report refused: manifest is incomplete. Run verify for details.")
    rows = _read_rows(root / "evaluation" / "raw_results.csv")
    per_seed = _per_seed_metrics(rows)
    statistics_by_metric: dict[str, dict[str, Any]] = {}
    for metric in (PRIMARY_METRIC, *SECONDARY_METRICS):
        differences = {seed: per_seed[seed][metric]["difference"] for seed in TRAINING_SEEDS}
        defined_seeds = [seed for seed in TRAINING_SEEDS if differences[seed] is not None]
        if len(defined_seeds) < 2:
            raise StudyRefusal(f"Report refused: {metric} has fewer than two training seeds with defined differences.")
        statistics_by_metric[metric] = {
            **_metric_statistics([differences[seed] for seed in defined_seeds]),
            "excluded_training_seeds": [seed for seed in TRAINING_SEEDS if differences[seed] is None],
        }
    report = {
        "study_id": STUDY_ID,
        "protocol_fingerprint": manifest["protocol_fingerprint"],
        "difference_definition": "Greedy minus PPO per training seed; positive values favor PPO",
        "primary_metric": {"name": PRIMARY_METRIC, **statistics_by_metric[PRIMARY_METRIC]},
        "secondary_metrics": {metric: statistics_by_metric[metric] for metric in SECONDARY_METRICS},
        "feasibility_gate": FEASIBILITY_GATE,
        "per_training_seed": [
            {
                "training_seed": seed,
                "ppo_burden_mean": per_seed[seed][PRIMARY_METRIC]["ppo_mean"],
                "greedy_burden_mean": per_seed[seed][PRIMARY_METRIC]["greedy_mean"],
                **{f"{metric}_greedy_minus_ppo": per_seed[seed][metric]["difference"] for metric in (PRIMARY_METRIC, *SECONDARY_METRICS)},
                **{f"{metric}_defined_case_count": per_seed[seed][metric]["defined_case_count"] for metric in (PRIMARY_METRIC, *SECONDARY_METRICS)},
            }
            for seed in TRAINING_SEEDS
        ],
        "statistical_tests": "none; intervals only",
    }
    _write_json(root / "statistics.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Exit codes: 0 success; 1 verify incomplete; 2 refused before running; 3 run failed."""
    parser = argparse.ArgumentParser(description="Multi-seed PPO study: train, quarantine, verify, evaluate, report.")
    commands = parser.add_subparsers(dest="command", required=True)
    train_parser = commands.add_parser("train", help="Train one new seed at the fixed budget (realized 100096 at n_steps=256).")
    train_parser.add_argument("--seed", type=int, required=True)
    train_parser.add_argument(
        "--confirm-protocol-change",
        action="store_true",
        help="Allow a changed protocol; the old protocol lock is moved to quarantine.",
    )
    quarantine_parser = commands.add_parser("quarantine", help="Move a failed or interrupted seed aside; nothing is deleted.")
    quarantine_parser.add_argument("--seed", type=int, required=True)
    quarantine_parser.add_argument("--reason", required=True, help="Why the seed is quarantined.")
    quarantine_parser.add_argument(
        "--invalid-completed",
        action="store_true",
        help="Quarantine a completed seed that verify reports as integrity-invalid; valid completed seeds are refused.",
    )
    verify_parser = commands.add_parser("verify", help="Write manifest.json and report completeness.")
    evaluate_parser = commands.add_parser("evaluate", help="Run the shared-schedule evaluation for all 20 checkpoints.")
    quarantine_evaluation_parser = commands.add_parser(
        "quarantine-evaluation",
        help="Move a failed, interrupted, or invalid evaluation aside; refuses a completed valid evaluation.",
    )
    quarantine_evaluation_parser.add_argument("--reason", required=True, help="Why the evaluation is quarantined.")
    report_parser = commands.add_parser("report", help="Write statistics.json for a complete batch.")
    for subparser in (
        train_parser,
        quarantine_parser,
        verify_parser,
        evaluate_parser,
        report_parser,
        quarantine_evaluation_parser,
    ):
        subparser.add_argument("--root", type=Path, default=STUDY_ROOT, help="Study output root.")
    args = parser.parse_args(argv)
    try:
        if args.command == "quarantine":
            print(
                json.dumps(
                    {
                        "quarantined_to": str(
                            quarantine_seed(args.seed, args.reason, args.root, invalid_completed=args.invalid_completed)
                        )
                    },
                    indent=2,
                )
            )
            return EXIT_OK
        if args.command == "quarantine-evaluation":
            print(json.dumps({"quarantined_to": str(quarantine_evaluation(args.reason, args.root))}, indent=2))
            return EXIT_OK
        if args.command == "verify":
            manifest = verify_study(args.root)
            print(json.dumps({
                "complete": manifest["complete"],
                "training_complete": manifest["training_complete"],
                "evaluation_complete": manifest["evaluation_complete"],
                "protocol_lock": manifest["protocol_lock"],
                "problems": manifest["problems"],
            }, indent=2))
            return EXIT_OK if manifest["complete"] else EXIT_INCOMPLETE
        if args.command == "report":
            print(json.dumps(report_study(args.root)["primary_metric"], indent=2))
            return EXIT_OK
        if args.command == "train":
            try:
                record = train_new_seed(args.seed, args.root, confirm_protocol_change=args.confirm_protocol_change)
            except StudyRefusal:
                raise
            except Exception as error:
                print(f"Run failed for seed {args.seed}: {type(error).__name__}: {error}", file=sys.stderr)
                return EXIT_RUN_FAILED
            print(json.dumps(record, indent=2))
            return EXIT_OK
        try:
            print(json.dumps(evaluate_study(args.root), indent=2))
        except StudyRefusal:
            raise
        except Exception as error:
            print(f"Evaluation failed: {type(error).__name__}: {error}", file=sys.stderr)
            return EXIT_RUN_FAILED
        return EXIT_OK
    except StudyRefusal as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
