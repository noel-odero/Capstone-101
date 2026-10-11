import csv
import json
import math
import statistics
from pathlib import Path

import pytest
import torch
from scipy.stats import t as student_t

import ml.src.ppo_seed_study as study
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, config_for_seed, load_ppo_model, train_ppo


def _write_run(run_dir: Path, seed: int, *, checkpoint_bytes=None, config_overrides=None, timesteps=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    config = study.protocol_config(seed).to_dict()
    config.update(config_overrides or {})
    if timesteps is None:
        timesteps = study.expected_realized_timesteps(config["n_steps"])
    (run_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (run_dir / "training_summary.json").write_text(json.dumps({"total_timesteps": timesteps}), encoding="utf-8")
    (run_dir / "final_model.zip").write_bytes(checkpoint_bytes or f"checkpoint-{seed}".encode())


def _write_ledger(root: Path, seed: int, status: str, error: str | None = None) -> None:
    path = root / "run_ledger" / f"training_seed_{seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"training_seed": seed, "status": status, "elapsed_seconds": 1.0, "error": error}
    run_dir = root / "training" / f"ppo_seed_{seed}"
    if status == "completed" and run_dir.is_dir():
        record["metadata_sha256"] = study._metadata_hashes(run_dir)
        record["checkpoint_sha256"] = study._sha256_file(run_dir / "final_model.zip")
    path.write_text(json.dumps(record), encoding="utf-8")


FAULTS = {
    6000: "missing",
    7000: "failed",
    8000: "interrupted",
    9000: "incompatible",
    10000: "duplicate",
    11000: "duplicate",
    12000: "incomplete",
}


def _build_batch(root: Path, canonical: Path, faults: dict[int, str]) -> None:
    study._write_protocol_lock(root)
    for seed in study.RETAINED_SEEDS:
        _write_run(canonical / f"ppo_seed_{seed}", seed)
    for seed in study.NEW_SEEDS:
        fault = faults.get(seed)
        if fault == "missing":
            continue
        kwargs = {}
        if fault == "incompatible":
            kwargs["config_overrides"] = {"learning_rate": 0.5}
        if fault == "duplicate":
            kwargs["checkpoint_bytes"] = b"shared-checkpoint"
        if fault == "incomplete":
            kwargs["timesteps"] = 4096
        _write_run(root / "training" / f"ppo_seed_{seed}", seed, **kwargs)
        status = {"failed": "failed", "interrupted": "started"}.get(fault, "completed")
        _write_ledger(root, seed, status, error="boom" if fault == "failed" else None)


def _statuses(manifest: dict) -> dict[int, str]:
    return {record["training_seed"]: record["status"] for record in manifest["training_runs"]}


def test_seed_plan_is_unique_and_training_blocks_stay_clear_of_evaluation_seeds():
    assert len(set(study.TRAINING_SEEDS)) == 20
    assert study.TRAINING_SEEDS[:5] == study.RETAINED_SEEDS
    assert study.NEW_SEEDS == tuple(range(6000, 20001, 1000))
    base = study.protocol_config(study.TRAINING_SEEDS[0])
    evaluation_low = min(base.matched_evaluation_seed_bases)
    occupied: set[int] = set()
    for seed in study.TRAINING_SEEDS:
        block = {seed, seed + 1, seed + 2}
        assert not occupied & block
        occupied |= block
        assert seed + 2 < evaluation_low


def test_every_protocol_config_fixes_budget_and_training_fingerprint():
    expected = study.expected_training_fingerprint()
    for seed in study.TRAINING_SEEDS:
        config = study.protocol_config(seed)
        assert config.total_timesteps == study.TOTAL_TIMESTEPS == 100000
        assert (config.ppo_seed, config.environment_seed, config.evaluation_seed) == (seed, seed + 1, seed + 2)
        assert study.training_fingerprint(config.to_dict()) == expected


def test_realized_budget_accepts_rollout_aligned_count_only(tmp_path):
    assert study.protocol_config(6000).n_steps == 256
    assert study.expected_realized_timesteps(256) == 100096
    expected = study.expected_training_fingerprint()
    outcomes = {100096: "complete", 100256: "incompatible", 99999: "incomplete"}
    for timesteps, status in outcomes.items():
        root = tmp_path / f"timesteps_{timesteps}"
        _write_run(root / "training" / "ppo_seed_6000", 6000, timesteps=timesteps)
        _write_ledger(root, 6000, "completed")
        record = study._verify_training_run(
            6000,
            root=root,
            canonical_root=tmp_path / "canonical",
            pinned_checkpoint_hashes={},
            pinned_metadata_hashes={},
            expected_fingerprint=expected,
        )
        assert study._status(record["problems"]) == status, timesteps


def test_train_new_seed_refuses_retained_seeds_and_existing_ledgers(tmp_path):
    with pytest.raises(study.StudyRefusal):
        study.train_new_seed(1000, tmp_path)
    _write_ledger(tmp_path, 6000, "completed")
    with pytest.raises(study.StudyRefusal):
        study.train_new_seed(6000, tmp_path)


def test_study_root_refuses_other_canonical_result_directories():
    with pytest.raises(study.StudyRefusal):
        study._check_study_root(study.CANONICAL_ROOT / "ppo_seed_1000")
    assert study._check_study_root(study.STUDY_ROOT) == study.STUDY_ROOT.resolve()


def test_manifest_reports_clean_batch_as_training_complete(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={})
    assert manifest["training_complete"] is True
    assert set(_statuses(manifest).values()) == {"complete"}
    assert manifest["evaluation"]["status"] == "missing"
    assert manifest["complete"] is False


def test_manifest_detects_missing_failed_interrupted_incompatible_duplicate_and_incomplete_runs(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, FAULTS)
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={})
    statuses = _statuses(manifest)
    assert statuses[6000] == "missing"
    assert statuses[7000] == "failed"
    assert statuses[8000] == "interrupted"
    assert statuses[9000] == "incompatible"
    assert statuses[10000] == "duplicate"
    assert statuses[11000] == "duplicate"
    assert statuses[12000] == "incomplete"
    assert all(statuses[seed] == "complete" for seed in study.RETAINED_SEEDS)
    assert manifest["training_complete"] is False
    assert manifest["complete"] is False


def test_manifest_flags_checkpoint_hash_that_differs_from_pinned_value(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={1000: "0" * 64}, pinned_metadata_hashes={})
    assert _statuses(manifest)[1000] == "incompatible"


def test_report_and_evaluation_refuse_incomplete_batch(tmp_path):
    root = tmp_path / "study"
    _build_batch(root, tmp_path / "canonical", FAULTS)
    with pytest.raises(study.StudyRefusal):
        study.report_study(root)
    with pytest.raises(study.StudyRefusal):
        study.evaluate_study(root)
    assert not (root / "run_ledger" / "evaluation.json").exists()


def test_metric_statistics_counts_wins_ties_and_losses():
    stats = study._metric_statistics([0.5, 0.5, 0.0, -1e-13, 1.0])
    assert stats["ppo_lower_seed_count"] == 3
    assert stats["tied_seed_count"] == 2
    assert stats["greedy_lower_seed_count"] == 0
    assert stats["mean_greedy_minus_ppo"] == pytest.approx(0.4)


def test_primary_interval_uses_student_t_with_nineteen_degrees_of_freedom():
    values = [float(index) for index in range(20)]
    interval = study._metric_statistics(values)["primary_t_interval"]
    half_width = (interval["upper_bound"] - interval["lower_bound"]) / 2
    expected_half_width = student_t.ppf(0.975, 19) * statistics.stdev(values) / math.sqrt(20)
    assert half_width == pytest.approx(expected_half_width, rel=1e-9)


def test_schedule_protocol_is_recorded_in_protocol_record():
    record = study.protocol_record()
    assert record["evaluation_schedule"] == "shared_schedule"
    assert record["evaluation_seed_bases"] == list(study.protocol_config(1000).matched_evaluation_seed_bases)
    assert len(canonical_initial_profiles()) == 128


def _tiny_base() -> PPOConfig:
    return PPOConfig(
        horizon=3,
        total_timesteps=32,
        n_steps=16,
        batch_size=8,
        n_epochs=2,
        evaluation_frequency=16,
        evaluation_episodes=2,
        policy_architecture=(16, 16),
    )


def test_same_seed_reproduces_trained_parameters_and_other_seed_differs(tmp_path):
    base = _tiny_base()
    states = {}
    for name, seed in (("first", 71), ("second", 71), ("other", 72)):
        output = tmp_path / name
        train_ppo(config_for_seed(base, seed), output)
        states[name] = load_ppo_model(output / "final_model.zip").policy.state_dict()
    assert states["first"].keys() == states["second"].keys()
    assert all(torch.equal(states["first"][key], states["second"][key]) for key in states["first"])
    assert any(not torch.equal(states["first"][key], states["other"][key]) for key in states["first"])


EVAL_DIFFERENCES = dict(zip(study.TRAINING_SEEDS, (0.5, 0.0, -0.25, 1.0) * 5))


def _metric_fields():
    return [column for columns in study.METRIC_COLUMNS.values() for column in columns.values()]


def _write_evaluation(root: Path, canonical: Path, *, differences=EVAL_DIFFERENCES) -> None:
    """Write a shared-schedule evaluation fixture with the real raw_results.csv column names."""
    bases = list(study.protocol_config(study.TRAINING_SEEDS[0]).matched_evaluation_seed_bases)
    eval_dir = root / "evaluation"
    hashes = {}
    metadata_hashes = {}
    for seed in study.TRAINING_SEEDS:
        (eval_dir / "models" / f"ppo_seed_{seed}").mkdir(parents=True, exist_ok=True)
        run_directory = study._run_directory(seed, root=root, canonical_root=canonical)
        hashes[str(seed)] = study._sha256_file(run_directory / "final_model.zip")
        metadata_hashes[str(seed)] = study._metadata_hashes(run_directory)
    rows = []
    for seed in study.TRAINING_SEEDS:
        for base in bases:
            for profile in range(len(canonical_initial_profiles())):
                row = {"case_id": f"seed_{base}_profile_{profile:03d}", "ppo_training_seed": seed}
                for metric, columns in study.METRIC_COLUMNS.items():
                    greedy = 2.0 if metric == study.PRIMARY_METRIC else 1.0
                    ppo = greedy - differences[seed] if metric == study.PRIMARY_METRIC else 1.0
                    row[columns["ppo"]] = ppo
                    row[columns["greedy"]] = greedy
                    row[columns["difference"]] = greedy - ppo
                rows.append(row)
    eval_dir.mkdir(parents=True, exist_ok=True)
    with (eval_dir / "raw_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["case_id", "ppo_training_seed", *_metric_fields()])
        writer.writeheader()
        writer.writerows(rows)
    config = {
        "evaluation_protocol": "shared_schedule",
        "evaluation_seed_bases_by_training_seed": {str(seed): bases for seed in study.TRAINING_SEEDS},
        "policy_seed_start_by_training_seed": {
            str(seed): study.protocol_config(seed).matched_policy_seed_start for seed in study.TRAINING_SEEDS
        },
        "checkpoint_sha256_by_training_seed": hashes,
        "metadata_sha256_by_training_seed": metadata_hashes,
    }
    (eval_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (eval_dir / "summary.json").write_text(json.dumps({"training_seeds": list(study.TRAINING_SEEDS)}), encoding="utf-8")
    ledger = study._ledger_path(root, "evaluation")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"status": "completed", "error": None}), encoding="utf-8")


def _evaluated_batch(tmp_path: Path) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _write_evaluation(root, canonical)
    return root, canonical


def _evaluation_messages(root: Path, canonical: Path) -> tuple[str, list[str]]:
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={})
    return manifest["evaluation"]["status"], [problem["message"] for problem in manifest["evaluation"]["problems"]]


def _edit_evaluation_config(root: Path, edit) -> None:
    path = root / "evaluation" / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    edit(config)
    path.write_text(json.dumps(config), encoding="utf-8")


def _drop_evaluation_rows(root: Path, seed: int, count: int) -> None:
    path = root / "evaluation" / "raw_results.csv"
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = list(reader)
    kept = [row for row in rows if int(row["ppo_training_seed"]) != seed]
    kept.extend([row for row in rows if int(row["ppo_training_seed"]) == seed][:-count])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)


def test_complete_evaluation_fixture_passes_verification(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    status, messages = _evaluation_messages(root, canonical)
    assert status == "complete", messages


def test_evaluation_refuses_wrong_policy_seed_start(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    _edit_evaluation_config(root, lambda config: config["policy_seed_start_by_training_seed"].__setitem__("6000", 900002))
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("policy-seed start" in message for message in messages)


def test_evaluation_refuses_missing_rows(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    expected = len(study.protocol_config(6000).matched_evaluation_seed_bases) * len(canonical_initial_profiles())
    _drop_evaluation_rows(root, 6000, count=1)
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any(message.startswith(f"seed 6000 has {expected - 1} rows") for message in messages)


def test_evaluation_refuses_protocol_mismatch(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    _edit_evaluation_config(root, lambda config: config.__setitem__("evaluation_protocol", "positional_schedule"))
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert "evaluation was not run under the shared schedule" in messages


def test_evaluation_refuses_altered_seed_schedule(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    _edit_evaluation_config(
        root,
        lambda config: config["evaluation_seed_bases_by_training_seed"].__setitem__("6000", [1, 2, 3, 4, 5]),
    )
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert "evaluation seed schedules differ from protocol" in messages


def test_evaluation_refuses_recorded_checkpoint_hash_that_differs(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    _edit_evaluation_config(root, lambda config: config["checkpoint_sha256_by_training_seed"].__setitem__("7000", "0" * 64))
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("checkpoint hash for seed 7000" in message for message in messages)


def test_evaluation_refuses_checkpoint_replaced_after_evaluation(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    (root / "training" / "ppo_seed_7000" / "final_model.zip").write_bytes(b"replaced-after-evaluation")
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("checkpoint hash for seed 7000" in message for message in messages)


def _fake_training(monkeypatch, *, fail_seeds=()):
    """Replace train_ppo with a fake that writes a run directory, then fails for fail_seeds."""

    def fake_train(config, run_dir):
        _write_run(Path(run_dir), config.ppo_seed)
        if config.ppo_seed in fail_seeds:
            raise RuntimeError("simulated training failure")

    monkeypatch.setattr(study, "train_ppo", fake_train)


def _tamper_protocol_lock(root: Path) -> None:
    path = root / study.PROTOCOL_LOCK_NAME
    lock = json.loads(path.read_text(encoding="utf-8"))
    lock["protocol_fingerprint"] = "0" * 64
    path.write_text(json.dumps(lock), encoding="utf-8")


def _use_fixture_canonical(monkeypatch, canonical: Path) -> None:
    """Make manifest builds made inside evaluate/report use a fixture canonical area with no pins."""
    original = study.build_manifest
    monkeypatch.setattr(
        study,
        "build_manifest",
        lambda root, **kwargs: original(
            root,
            canonical_root=canonical,
            pinned_checkpoint_hashes={},
            pinned_metadata_hashes={},
            **kwargs,
        ),
    )


def test_first_train_writes_protocol_lock_and_mismatch_is_refused(tmp_path, monkeypatch):
    _fake_training(monkeypatch)
    study.train_new_seed(6000, tmp_path)
    assert study._protocol_lock_status(tmp_path) == "match"
    _tamper_protocol_lock(tmp_path)
    with pytest.raises(study.StudyRefusal, match="Protocol lock is mismatch"):
        study.train_new_seed(7000, tmp_path)
    assert not study._ledger_path(tmp_path, "training_seed_7000").exists()


def test_confirmed_protocol_change_moves_old_lock_and_batch_state_to_quarantine(tmp_path, monkeypatch):
    _fake_training(monkeypatch)
    study.train_new_seed(6000, tmp_path)
    _tamper_protocol_lock(tmp_path)
    study.train_new_seed(7000, tmp_path, confirm_protocol_change=True)
    assert study._protocol_lock_status(tmp_path) == "match"
    archived = list((tmp_path / "quarantine").glob("*_protocol_change"))
    assert len(archived) == 1
    destination = archived[0]
    assert (destination / study.PROTOCOL_LOCK_NAME).exists()
    assert (destination / "run_ledger" / study._ledger_path(tmp_path, "training_seed_6000").name).exists()
    assert (destination / "training" / "ppo_seed_6000" / "final_model.zip").exists()
    assert not study._ledger_path(tmp_path, "training_seed_6000").exists()
    assert not (tmp_path / "training" / "ppo_seed_6000").exists()


def test_changed_seed_set_mismatches_lock_and_requires_confirmation(tmp_path, monkeypatch):
    _fake_training(monkeypatch)
    study.train_new_seed(6000, tmp_path)
    monkeypatch.setattr(study, "TRAINING_SEEDS", study.TRAINING_SEEDS[:-1])
    assert study._protocol_lock_status(tmp_path) == "mismatch"
    with pytest.raises(study.StudyRefusal, match="Protocol lock is mismatch"):
        study.train_new_seed(7000, tmp_path)


def test_train_refuses_existing_run_directory(tmp_path):
    study._write_protocol_lock(tmp_path)
    _write_run(tmp_path / "training" / "ppo_seed_6000", 6000)
    with pytest.raises(study.StudyRefusal, match="Run directory already exists"):
        study.train_new_seed(6000, tmp_path)


def test_missing_lock_with_batch_state_is_refused_without_confirmation(tmp_path, monkeypatch):
    _fake_training(monkeypatch)
    _write_ledger(tmp_path, 6000, "failed", "simulated")
    with pytest.raises(study.StudyRefusal, match="Protocol lock is absent"):
        study.train_new_seed(7000, tmp_path)
    assert not study._protocol_lock_path(tmp_path).exists()
    assert not study._ledger_path(tmp_path, "training_seed_7000").exists()


def test_confirmed_change_quarantines_every_batch_state_path(tmp_path):
    study._write_protocol_lock(tmp_path)
    _tamper_protocol_lock(tmp_path)
    _write_ledger(tmp_path, 6000, "complete")
    _write_run(tmp_path / "training" / "ppo_seed_6000", 6000)
    (tmp_path / "evaluation").mkdir()
    (tmp_path / "evaluation" / "summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    study._admit_protocol(tmp_path, True)

    assert study._protocol_lock_status(tmp_path) == "match"
    for name in ("run_ledger", "training", "evaluation", "manifest.json"):
        assert not (tmp_path / name).exists()
    archived = list((tmp_path / "quarantine").glob("*_protocol_change"))
    assert len(archived) == 1
    destination = archived[0]
    for name in ("run_ledger", "training", "evaluation", "manifest.json", study.PROTOCOL_LOCK_NAME):
        assert (destination / name).exists()
    reason = json.loads((destination / "quarantine_reason.json").read_text(encoding="utf-8"))
    assert set(reason["moved"]) == {"run_ledger", "training", "evaluation", "manifest.json", study.PROTOCOL_LOCK_NAME}


def test_quarantine_moves_failed_seed_aside_and_allows_same_seed_rerun(tmp_path, monkeypatch):
    _fake_training(monkeypatch, fail_seeds={6000})
    with pytest.raises(RuntimeError):
        study.train_new_seed(6000, tmp_path)
    ledger = study._ledger_path(tmp_path, "training_seed_6000")
    assert json.loads(ledger.read_text(encoding="utf-8"))["status"] == "failed"

    destination = study.quarantine_seed(6000, "simulated failure", tmp_path)
    assert (destination / "run_ledger.json").exists()
    assert (destination / "run_directory" / "final_model.zip").exists()
    assert not ledger.exists()
    assert not (tmp_path / "training" / "ppo_seed_6000").exists()
    reason = json.loads((destination / "quarantine_reason.json").read_text(encoding="utf-8"))
    assert reason["run_directory_moved"] is True

    _fake_training(monkeypatch)
    record = study.train_new_seed(6000, tmp_path)
    assert record["status"] == "completed"
    with pytest.raises(study.StudyRefusal, match="only failed or started"):
        study.quarantine_seed(6000, "completed seed must not be quarantined", tmp_path)


def test_quarantine_refuses_retained_seeds_and_empty_reason(tmp_path):
    with pytest.raises(study.StudyRefusal):
        study.quarantine_seed(1000, "retained", tmp_path)
    _write_ledger(tmp_path, 6000, "failed", error="boom")
    with pytest.raises(study.StudyRefusal, match="reason is required"):
        study.quarantine_seed(6000, "   ", tmp_path)


def test_evaluation_refused_when_protocol_lock_mismatches(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _use_fixture_canonical(monkeypatch, canonical)
    _tamper_protocol_lock(root)
    with pytest.raises(study.StudyRefusal, match="protocol lock is mismatch"):
        study.evaluate_study(root)
    assert not (root / "run_ledger" / "evaluation.json").exists()


def test_feasibility_is_labeled_as_construction_enforced_not_measured():
    gate = study.FEASIBILITY_GATE
    assert gate["infeasible_selections_allowed"] == 0
    assert gate["enforcement"] == "construction"
    assert gate["environment_step_rejects_infeasible_actions"] is False
    assert gate["measured_outcome"] is False
    assert gate["violation_counter"] is None


def test_outcome_boundaries_use_inclusive_tie_tolerance():
    tie = study.TIE_TOLERANCE
    assert tie == study.BURDEN_TIE_TOLERANCE == 1e-12
    assert study._outcome(0.0) == "tied"
    assert study._outcome(tie) == "tied"
    assert study._outcome(-tie) == "tied"
    assert study._outcome(math.nextafter(tie, 1.0)) == "ppo_lower"
    assert study._outcome(math.nextafter(-tie, -1.0)) == "greedy_lower"
    assert study._outcome(1 / (7 * 640)) == "ppo_lower"
    assert study._outcome(-1 / (7 * 640)) == "greedy_lower"


def test_metric_statistics_counts_tolerance_boundaries_consistently():
    tie = study.TIE_TOLERANCE
    values = [0.0, tie, -tie, math.nextafter(tie, 1.0), math.nextafter(-tie, -1.0)]
    stats = study._metric_statistics(values)
    assert (stats["ppo_lower_seed_count"], stats["tied_seed_count"], stats["greedy_lower_seed_count"]) == (1, 3, 1)
    assert "tie_tolerance_basis" in study.protocol_record()


def test_end_to_end_report_from_fixture_csv_writes_expected_statistics(tmp_path, monkeypatch, capsys):
    root, canonical = _evaluated_batch(tmp_path)
    _use_fixture_canonical(monkeypatch, canonical)
    assert study.main(["report", "--root", str(root)]) == study.EXIT_OK
    statistics_json = json.loads((root / "statistics.json").read_text(encoding="utf-8"))
    primary = statistics_json["primary_metric"]
    assert primary["name"] == study.PRIMARY_METRIC
    assert primary["training_seed_count"] == 20
    assert primary["mean_greedy_minus_ppo"] == pytest.approx(0.3125)
    assert (primary["ppo_lower_seed_count"], primary["tied_seed_count"], primary["greedy_lower_seed_count"]) == (10, 5, 5)
    assert statistics_json["feasibility_gate"]["measured_outcome"] is False
    assert len(statistics_json["per_training_seed"]) == 20


def test_undefined_rate_cells_are_excluded_per_metric_and_never_zero(tmp_path, monkeypatch):
    root, canonical = _evaluated_batch(tmp_path)
    all_undefined_seed = study.TRAINING_SEEDS[0]
    partly_undefined_seed = study.TRAINING_SEEDS[1]
    path = root / "evaluation" / "raw_results.csv"
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = list(reader)
    # The Greedy baseline is shared across seeds, so only PPO-side rates (and their differences) are blanked here.
    ppo_columns = [study.METRIC_COLUMNS["resistance_emergence_rate"][role] for role in ("ppo", "difference")]
    partly_rows = [row for row in rows if int(row["ppo_training_seed"]) == partly_undefined_seed][:3]
    for row in rows:
        if int(row["ppo_training_seed"]) == all_undefined_seed:
            for column in ppo_columns:
                row[column] = ""
    for row in partly_rows:
        for column in ppo_columns:
            row[column] = ""
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    status, messages = _evaluation_messages(root, canonical)
    assert status == "complete", messages

    per_seed = study._per_seed_metrics(study._read_rows(path))
    rate = per_seed[all_undefined_seed]["resistance_emergence_rate"]
    assert (rate["ppo_mean"], rate["difference"], rate["defined_case_count"]) == (None, None, 0)
    assert rate["greedy_mean"] == pytest.approx(1.0)
    partial = per_seed[partly_undefined_seed]["resistance_emergence_rate"]
    assert partial["defined_case_count"] == sum(
        int(row["ppo_training_seed"]) == partly_undefined_seed for row in rows
    ) - len(partly_rows)
    assert partial["difference"] == pytest.approx(0.0)
    assert per_seed[all_undefined_seed][study.PRIMARY_METRIC]["difference"] == pytest.approx(
        EVAL_DIFFERENCES[all_undefined_seed]
    )

    _use_fixture_canonical(monkeypatch, canonical)
    assert study.main(["report", "--root", str(root)]) == study.EXIT_OK
    statistics_json = json.loads((root / "statistics.json").read_text(encoding="utf-8"))
    secondary = statistics_json["secondary_metrics"]["resistance_emergence_rate"]
    assert secondary["excluded_training_seeds"] == [all_undefined_seed]
    assert secondary["training_seed_count"] == 19
    assert statistics_json["primary_metric"]["excluded_training_seeds"] == []
    assert statistics_json["primary_metric"]["training_seed_count"] == 20


def test_greedy_undefined_on_one_seed_only_is_a_baseline_mismatch(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    path = root / "evaluation" / "raw_results.csv"
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = list(reader)
    greedy_column = study.METRIC_COLUMNS["resistance_emergence_rate"]["greedy"]
    target = next(row for row in rows if int(row["ppo_training_seed"]) == study.TRAINING_SEEDS[1])
    target[greedy_column] = ""
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("Greedy baseline differs" in message for message in messages)


def test_cli_exit_codes_for_refusals_incomplete_and_success(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    complete_root = tmp_path / "complete"
    _build_batch(complete_root, canonical, {})
    _write_evaluation(complete_root, canonical)
    _use_fixture_canonical(monkeypatch, canonical)
    assert study.main(["verify", "--root", str(complete_root)]) == study.EXIT_OK

    incomplete_root = tmp_path / "incomplete"
    _build_batch(incomplete_root, canonical, FAULTS)
    assert study.main(["verify", "--root", str(incomplete_root)]) == study.EXIT_INCOMPLETE
    assert study.main(["evaluate", "--root", str(incomplete_root)]) == study.EXIT_REFUSED
    assert study.main(["report", "--root", str(incomplete_root)]) == study.EXIT_REFUSED

    assert study.main(["train", "--seed", "1000", "--root", str(tmp_path / "fresh")]) == study.EXIT_REFUSED
    assert study.main(["train", "--seed", "6500", "--root", str(tmp_path / "fresh")]) == study.EXIT_REFUSED
    assert study.main(["quarantine", "--seed", "6000", "--reason", "completed seed", "--root", str(complete_root)]) == study.EXIT_REFUSED


def test_cli_train_success_and_failed_run_exit_codes(tmp_path, monkeypatch):
    _fake_training(monkeypatch, fail_seeds={6000})
    assert study.main(["train", "--seed", "6000", "--root", str(tmp_path)]) == study.EXIT_RUN_FAILED
    ledger = json.loads(study._ledger_path(tmp_path, "training_seed_6000").read_text(encoding="utf-8"))
    assert ledger["status"] == "failed"
    assert study.main(["quarantine", "--seed", "6000", "--reason", "simulated failure", "--root", str(tmp_path)]) == study.EXIT_OK

    _fake_training(monkeypatch)
    assert study.main(["train", "--seed", "6000", "--root", str(tmp_path)]) == study.EXIT_OK


def _partial_evaluation(root: Path, status: str) -> None:
    """Simulate an evaluation that stopped partway: its ledger status plus a partial model output directory."""
    ledger = study._ledger_path(root, "evaluation")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"status": status, "error": "boom" if status == "failed" else None}), encoding="utf-8")
    (root / "evaluation" / "models" / "ppo_seed_6000").mkdir(parents=True, exist_ok=True)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _outside_evaluation(snapshot: dict[str, bytes]) -> dict[str, bytes]:
    """Training, protocol, and seed-batch files: everything except evaluation output and quarantine."""
    return {
        name: data
        for name, data in snapshot.items()
        if name.split("/")[0] not in {"evaluation", "quarantine"} and name != "run_ledger/evaluation.json"
    }


def test_interrupted_evaluation_blocks_evaluate_until_quarantined(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _partial_evaluation(root, "started")
    _use_fixture_canonical(monkeypatch, canonical)
    assert study.build_manifest(root)["evaluation"]["status"] == "interrupted"
    with pytest.raises(study.StudyRefusal, match="quarantine-evaluation"):
        study.evaluate_study(root)
    assert study.main(["evaluate", "--root", str(root)]) == study.EXIT_REFUSED
    assert (root / "evaluation" / "models" / "ppo_seed_6000").is_dir()


def test_orphan_evaluation_directory_blocks_evaluate_and_nothing_to_quarantine_is_refused(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _use_fixture_canonical(monkeypatch, canonical)
    with pytest.raises(study.StudyRefusal, match="nothing to quarantine"):
        study.quarantine_evaluation("no evaluation exists", root)
    (root / "evaluation" / "models").mkdir(parents=True)
    with pytest.raises(study.StudyRefusal, match="quarantine-evaluation"):
        study.evaluate_study(root)
    destination = study.quarantine_evaluation("orphan output without a ledger", root)
    reason = json.loads((destination / "quarantine_reason.json").read_text(encoding="utf-8"))
    assert reason["previous_ledger"] is None
    assert not (root / "evaluation").exists()


@pytest.mark.parametrize("status", ["started", "failed"])
def test_safe_retry_after_quarantine_reruns_evaluation_once(tmp_path, monkeypatch, status):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _partial_evaluation(root, status)
    _use_fixture_canonical(monkeypatch, canonical)
    with pytest.raises(study.StudyRefusal, match="quarantine-evaluation"):
        study.evaluate_study(root)

    destination = study.quarantine_evaluation("simulated interruption in test", root)

    assert not study._ledger_path(root, "evaluation").exists()
    assert not (root / "evaluation").exists()
    reason = json.loads((destination / "quarantine_reason.json").read_text(encoding="utf-8"))
    assert reason["reason"] == "simulated interruption in test"
    assert reason["verification_status"] == {"started": "interrupted", "failed": "failed"}[status]
    assert reason["previous_ledger"]["status"] == status
    assert (destination / "run_ledger_evaluation.json").is_file()
    assert (destination / "evaluation" / "models" / "ppo_seed_6000").is_dir()
    assert set(reason["moved_paths"].values()) == {
        str(destination / "run_ledger_evaluation.json"),
        str(destination / "evaluation"),
    }

    calls = []

    def fake_ensemble(model_paths, config, output_dir, **kwargs):
        calls.append(Path(output_dir))
        _write_evaluation(root, canonical)
        return {"summary": {"training_seed_count": 20, "matched_case_count": 0}}

    monkeypatch.setattr(study, "run_matched_ppo_seed_ensemble", fake_ensemble)
    result = study.evaluate_study(root)
    assert result["training_seed_count"] == 20
    assert calls == [root / "evaluation"]
    assert study.build_manifest(root)["evaluation"]["status"] == "complete"
    with pytest.raises(study.StudyRefusal, match="never overwritten"):
        study.evaluate_study(root)
    assert len(calls) == 1


def test_completed_valid_evaluation_is_never_overwritten_or_quarantined(tmp_path, monkeypatch):
    root, canonical = _evaluated_batch(tmp_path)
    _use_fixture_canonical(monkeypatch, canonical)
    before = _snapshot(root)
    with pytest.raises(study.StudyRefusal, match="never overwritten"):
        study.evaluate_study(root)
    with pytest.raises(study.StudyRefusal, match="never quarantined or overwritten"):
        study.quarantine_evaluation("try to replace a valid result", root)
    assert study.main(["quarantine-evaluation", "--reason", "try", "--root", str(root)]) == study.EXIT_REFUSED
    assert _snapshot(root) == before
    assert not (root / "quarantine").exists()


def test_quarantining_evaluation_leaves_training_runs_lock_and_seed_set_unchanged(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _partial_evaluation(root, "started")
    _use_fixture_canonical(monkeypatch, canonical)
    before = _snapshot(root)
    protocol_before = study.protocol_record()

    study.quarantine_evaluation("interrupted during test", root)

    assert _outside_evaluation(_snapshot(root)) == _outside_evaluation(before)
    assert study.protocol_record() == protocol_before
    manifest = study.build_manifest(root)
    assert _statuses(manifest) == {seed: "complete" for seed in study.TRAINING_SEEDS}
    assert manifest["training_complete"] is True
    assert manifest["evaluation"]["status"] == "missing"


@pytest.mark.parametrize("name", study.METADATA_FILES)
def test_tampered_training_metadata_is_incompatible_on_that_seed(tmp_path, name):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    path = root / "training" / "ppo_seed_7000" / name
    path.write_bytes(path.read_bytes() + b" ")
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={})
    record = next(run for run in manifest["training_runs"] if run["training_seed"] == 7000)
    assert record["status"] == "incompatible"
    assert any(f"{name} hash differs" in problem["message"] for problem in record["problems"])
    assert _statuses(manifest)[6000] == "complete"
    assert manifest["training_complete"] is False


def test_retained_metadata_pins_accept_canonical_files_and_refuse_a_different_hash(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    pins = {seed: study._metadata_hashes(canonical / f"ppo_seed_{seed}") for seed in study.RETAINED_SEEDS}
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes=pins)
    assert all(_statuses(manifest)[seed] == "complete" for seed in study.RETAINED_SEEDS)
    wrong = {**pins, 1000: {**pins[1000], "config.json": "0" * 64}}
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes=wrong)
    assert _statuses(manifest)[1000] == "incompatible"
    assert all(_statuses(manifest)[seed] == "complete" for seed in study.RETAINED_SEEDS[1:])


def test_completed_ledger_without_metadata_hashes_is_incompatible(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    path = study._ledger_path(root, "training_seed_7000")
    record = json.loads(path.read_text(encoding="utf-8"))
    record.pop("metadata_sha256")
    path.write_text(json.dumps(record), encoding="utf-8")
    manifest = study.build_manifest(root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={})
    assert _statuses(manifest)[7000] == "incompatible"
    record = next(run for run in manifest["training_runs"] if run["training_seed"] == 7000)
    assert any("completed ledger records no metadata hashes" in problem["message"] for problem in record["problems"])


def test_evaluation_metadata_hash_that_differs_is_incompatible(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    _edit_evaluation_config(
        root,
        lambda config: config["metadata_sha256_by_training_seed"]["7000"].__setitem__("config.json", "0" * 64),
    )
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("training metadata hashes for seed 7000" in message for message in messages)


def test_training_metadata_replaced_after_evaluation_is_incompatible(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    path = root / "training" / "ppo_seed_7000" / "training_summary.json"
    path.write_bytes(path.read_bytes() + b" ")
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("training metadata hashes for seed 7000" in message for message in messages)


def test_cli_quarantine_evaluation_exit_codes(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    complete_root = tmp_path / "complete"
    _build_batch(complete_root, canonical, {})
    _write_evaluation(complete_root, canonical)
    interrupted_root = tmp_path / "interrupted"
    _build_batch(interrupted_root, canonical, {})
    _partial_evaluation(interrupted_root, "started")
    _use_fixture_canonical(monkeypatch, canonical)

    assert study.main(["quarantine-evaluation", "--reason", "completed", "--root", str(complete_root)]) == study.EXIT_REFUSED
    assert study.main(["quarantine-evaluation", "--reason", "  ", "--root", str(interrupted_root)]) == study.EXIT_REFUSED
    assert study.main(["quarantine-evaluation", "--reason", "interrupted in test", "--root", str(interrupted_root)]) == study.EXIT_OK
    assert not (interrupted_root / "evaluation").exists()
    assert (complete_root / "evaluation" / "config.json").is_file()


def _verified_seed(root: Path, canonical: Path, seed: int) -> dict:
    batch = study._verify_training_batch(
        root, canonical_root=canonical, pinned_checkpoint_hashes={}, pinned_metadata_hashes={}
    )
    return next(record for record in batch if record["training_seed"] == seed)


def _messages(record: dict) -> list[str]:
    return [problem["message"] for problem in record["problems"]]


def test_completed_seed_records_checkpoint_hash_at_training_completion(tmp_path, monkeypatch):
    _fake_training(monkeypatch)
    record = study.train_new_seed(6000, tmp_path)
    checkpoint = tmp_path / "training" / "ppo_seed_6000" / "final_model.zip"
    assert record["checkpoint_sha256"] == study._sha256_file(checkpoint)
    ledger = json.loads(study._ledger_path(tmp_path, "training_seed_6000").read_text(encoding="utf-8"))
    assert ledger["checkpoint_sha256"] == record["checkpoint_sha256"]


def test_checkpoint_replaced_after_completion_is_incompatible(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    (root / "training" / "ppo_seed_7000" / "final_model.zip").write_bytes(b"replaced after completion")
    record = _verified_seed(root, canonical, 7000)
    assert record["status"] == "incompatible"
    assert any("checkpoint hash differs from the value recorded at training completion" in m for m in _messages(record))


def test_completed_ledger_without_checkpoint_hash_is_incompatible(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    path = study._ledger_path(root, "training_seed_7000")
    record = json.loads(path.read_text(encoding="utf-8"))
    record.pop("checkpoint_sha256")
    path.write_text(json.dumps(record), encoding="utf-8")
    verified = _verified_seed(root, canonical, 7000)
    assert verified["status"] == "incompatible"
    assert any("completed ledger records no checkpoint hash" in m for m in _messages(verified))


def test_evaluation_refuses_when_ledger_checkpoint_hash_is_altered(tmp_path):
    root, canonical = _evaluated_batch(tmp_path)
    path = study._ledger_path(root, "training_seed_7000")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["checkpoint_sha256"] = "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")
    status, messages = _evaluation_messages(root, canonical)
    assert status == "incompatible"
    assert any("checkpoint hash for seed 7000" in message for message in messages)


def test_invalid_completed_seed_is_quarantined_with_evidence_and_retrained(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    (root / "training" / "ppo_seed_7000" / "final_model.zip").write_bytes(b"replaced after completion")

    destination = study.quarantine_seed(
        7000,
        "checkpoint replaced after completion",
        root,
        invalid_completed=True,
        canonical_root=canonical,
    )

    assert (destination / "run_ledger.json").is_file()
    assert (destination / "run_directory" / "final_model.zip").read_bytes() == b"replaced after completion"
    assert not study._ledger_path(root, "training_seed_7000").exists()
    assert not (root / "training" / "ppo_seed_7000").exists()
    reason = json.loads((destination / "quarantine_reason.json").read_text(encoding="utf-8"))
    assert reason["invalid_completed"] is True
    assert reason["verification"]["status"] == "incompatible"

    _fake_training(monkeypatch)
    assert study.train_new_seed(7000, root)["status"] == "completed"
    assert _verified_seed(root, canonical, 7000)["status"] == "complete"


def test_invalid_completed_quarantine_refuses_valid_and_non_completed_seeds(tmp_path):
    canonical = tmp_path / "canonical"
    valid_root = tmp_path / "valid"
    _build_batch(valid_root, canonical, {})
    with pytest.raises(study.StudyRefusal, match="verifies complete"):
        study.quarantine_seed(6000, "valid seed", valid_root, invalid_completed=True, canonical_root=canonical)
    assert study._ledger_path(valid_root, "training_seed_6000").exists()

    faulty_root = tmp_path / "faulty"
    _build_batch(faulty_root, canonical, FAULTS)
    with pytest.raises(study.StudyRefusal, match="applies only to a completed ledger"):
        study.quarantine_seed(7000, "failed seed", faulty_root, invalid_completed=True, canonical_root=canonical)
    assert study._ledger_path(faulty_root, "training_seed_7000").exists()


def test_quarantine_refuses_unreadable_ledger_without_moving_anything(tmp_path):
    path = study._ledger_path(tmp_path, "training_seed_6000")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(study.StudyRefusal, match="unreadable"):
        study.quarantine_seed(6000, "corrupt ledger", tmp_path)
    assert path.exists()
    assert not (tmp_path / "quarantine").exists()


def test_cli_quarantine_invalid_completed_flag_exit_codes(tmp_path):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    (root / "training" / "ppo_seed_7000" / "final_model.zip").write_bytes(b"replaced after completion")
    assert study.main(["quarantine", "--seed", "7000", "--reason", "tampered", "--root", str(root)]) == study.EXIT_REFUSED
    assert study.main(
        ["quarantine", "--seed", "6000", "--reason", "valid", "--root", str(root), "--invalid-completed"]
    ) == study.EXIT_REFUSED
    assert study.main(
        ["quarantine", "--seed", "7000", "--reason", "tampered", "--root", str(root), "--invalid-completed"]
    ) == study.EXIT_OK
    assert not study._ledger_path(root, "training_seed_7000").exists()


def test_evaluation_commits_only_after_revalidating_the_verified_inputs(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _use_fixture_canonical(monkeypatch, canonical)
    captured = {}

    def fake_ensemble(model_paths, config, output_dir, **kwargs):
        captured.update(kwargs)
        _write_evaluation(root, canonical)
        return {"summary": {"training_seed_count": 20, "matched_case_count": 0}}

    monkeypatch.setattr(study, "run_matched_ppo_seed_ensemble", fake_ensemble)
    study.evaluate_study(root)

    expected = captured["expected_inputs"]
    assert [item["training_seed"] for item in expected] == list(study.TRAINING_SEEDS)
    manifest = study.build_manifest(root)
    for item in expected:
        record = next(run for run in manifest["training_runs"] if run["training_seed"] == item["training_seed"])
        assert item["checkpoint_sha256"] == record["checkpoint_sha256"]
        assert item["metadata_sha256"] == record["metadata_sha256"]
    assert json.loads(study._ledger_path(root, "evaluation").read_text(encoding="utf-8"))["status"] == "completed"


def test_checkpoint_changed_during_evaluation_fails_the_evaluation(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _use_fixture_canonical(monkeypatch, canonical)

    def tampering_ensemble(model_paths, config, output_dir, **kwargs):
        (root / "training" / "ppo_seed_7000" / "final_model.zip").write_bytes(b"changed during evaluation")
        return {"summary": {"training_seed_count": 20, "matched_case_count": 0}}

    monkeypatch.setattr(study, "run_matched_ppo_seed_ensemble", tampering_ensemble)
    with pytest.raises(RuntimeError, match="seed 7000"):
        study.evaluate_study(root)
    ledger = json.loads(study._ledger_path(root, "evaluation").read_text(encoding="utf-8"))
    assert ledger["status"] == "failed"
    assert "seed 7000" in ledger["error"]


def test_ensemble_failure_records_evaluation_as_failed(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    root = tmp_path / "study"
    _build_batch(root, canonical, {})
    _use_fixture_canonical(monkeypatch, canonical)

    def failing_ensemble(model_paths, config, output_dir, **kwargs):
        raise RuntimeError("ensemble boom")

    monkeypatch.setattr(study, "run_matched_ppo_seed_ensemble", failing_ensemble)
    with pytest.raises(RuntimeError, match="ensemble boom"):
        study.evaluate_study(root)
    ledger = json.loads(study._ledger_path(root, "evaluation").read_text(encoding="utf-8"))
    assert ledger["status"] == "failed"
    assert "ensemble boom" in ledger["error"]
