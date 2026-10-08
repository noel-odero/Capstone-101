import json

import pytest

from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.reproducibility import (
    REQUIRED_MANIFEST_FIELDS,
    configuration_fingerprint,
    finalize_manifest,
    sha256_file,
    validate_manifest,
    validate_seed_pairing,
    verify_integrity_inventory,
    _validate_experiment_lineage,
)
from pathlib import Path


def valid_manifest():
    return {
        "project": "test project",
        "experiment_version": "test",
        "code_revision": {"base_commit": "abc123"},
        "configuration_fingerprint": "0" * 64,
        "environment_fingerprint": "1" * 64,
        "transition_fingerprint": "2" * 64,
        "reward_fingerprint": "3" * 64,
        "action_order": ["A", "B"],
        "horizon": 8,
        "gamma": 1.0,
        "training_seeds": [1000],
        "evaluation_seeds": {"1000": [100001]},
        "initial_profile_order": "canonical",
        "checkpoint_inventory": "checkpoint_inventory.json",
        "evaluation_artifacts": "artifact_integrity.json",
        "experiment_commands": "experiment_inventory.json",
        "python_version": "3.11.9",
        "dependency_lockfile": {"path": "ml/requirements-lock.txt"},
    }


def test_manifest_required_fields_and_generation_are_deterministic():
    source = valid_manifest()
    assert validate_manifest(source) == ()
    first = finalize_manifest(source)
    second = finalize_manifest(source)
    assert first == second
    assert set(REQUIRED_MANIFEST_FIELDS).issubset(first)
    del source["gamma"]
    assert "gamma" in validate_manifest(source)
    with pytest.raises(ValueError, match="missing required fields"):
        finalize_manifest(source)


def test_configuration_fingerprint_is_stable_sensitive_and_ignores_volatile_fields():
    configuration = {
        "action_order": ["A", "B"],
        "horizon": 8,
        "gamma": 1.0,
        "reward": {"objective": "burden", "normalization": 7},
        "generated_at_utc": "2026-10-08T00:00:00Z",
        "output_dir": "C:/temporary/run-a",
    }
    identical = {**configuration, "generated_at_utc": "2027-01-01T00:00:00Z", "output_dir": "D:/other/run"}
    assert configuration_fingerprint(configuration) == configuration_fingerprint(identical)
    changed = {**identical, "gamma": 0.99}
    assert configuration_fingerprint(configuration) != configuration_fingerprint(changed)


def test_checkpoint_sha256_is_repeatable_and_detects_file_changes(tmp_path):
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"frozen checkpoint bytes")
    first = sha256_file(checkpoint)
    assert first == sha256_file(checkpoint)
    checkpoint.write_bytes(b"changed checkpoint bytes")
    assert first != sha256_file(checkpoint)


def test_integrity_verifier_detects_missing_or_modified_artifacts(tmp_path):
    artifact = tmp_path / "summary.json"
    artifact.write_text(json.dumps({"score": 1}), encoding="utf-8")
    inventory = {"algorithm": "SHA-256", "files": [{"path": "summary.json", "sha256": sha256_file(artifact)}]}
    assert verify_integrity_inventory(tmp_path, inventory)["ok"]
    artifact.write_text(json.dumps({"score": 2}), encoding="utf-8")
    result = verify_integrity_inventory(tmp_path, inventory)
    assert not result["ok"]
    assert result["mismatched"][0]["path"] == "summary.json"
    artifact.unlink()
    assert verify_integrity_inventory(tmp_path, inventory)["missing"] == ["summary.json"]


def seed_plans():
    schedules = {}
    policy_pairs = {}
    for model_index, seed in enumerate((1000, 2000, 3000, 4000, 5000)):
        bases = [100001 + model_index * 10000 + index * 1000 for index in range(5)]
        policy_base = 900001 + model_index * 1000
        schedules[str(seed)] = bases
        policy_pairs[str(seed)] = [[base, policy_base + index * 128] for index, base in enumerate(bases)]
    return schedules, policy_pairs


def test_canonical_profile_order_and_evaluation_policy_seed_pairing():
    schedules, policy_pairs = seed_plans()
    profiles = [list(profile.resistance) for profile in canonical_initial_profiles()]
    validate_seed_pairing(profiles, schedules, policy_pairs)
    with pytest.raises(ValueError, match="canonical 128-profile order"):
        validate_seed_pairing(profiles[::-1], schedules, policy_pairs)
    bad_pairs = {key: [list(pair) for pair in pairs] for key, pairs in policy_pairs.items()}
    bad_pairs["1000"][0][0] += 1
    with pytest.raises(ValueError, match="mismatched evaluation and policy"):
        validate_seed_pairing(profiles, schedules, bad_pairs)


def test_overlapping_seed_schedules_are_rejected():
    profiles = [list(profile.resistance) for profile in canonical_initial_profiles()]
    schedules, policy_pairs = seed_plans()
    schedules["2000"][0] = schedules["1000"][0]
    policy_pairs["2000"][0][0] = schedules["2000"][0]
    with pytest.raises(ValueError, match="overlap"):
        validate_seed_pairing(profiles, schedules, policy_pairs)


def test_existing_experiment_lineage_matches_frozen_checkpoint_provenance():
    root = Path(__file__).resolve().parents[2]
    matched_config = root / "experiments/results/ppo_greedy_matched_five_seed_final/config.json"
    inventory = []
    for seed in (1000, 2000, 3000, 4000, 5000):
        checkpoint = root / f"experiments/results/ppo_seed_{seed}/final_model.zip"
        inventory.append({"training_seed": seed, "checkpoint_type": "final", "sha256": sha256_file(checkpoint)})
    result = _validate_experiment_lineage(root, sha256_file(matched_config), inventory)
    assert result["ok"]
    assert result["issues"] == []
