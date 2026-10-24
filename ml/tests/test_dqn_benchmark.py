from dataclasses import replace
import csv
import json
from importlib.metadata import version
from pathlib import Path
import shutil

import numpy as np
import pytest
import torch

from ml.src.dqn_benchmark import (
    BenchmarkProtocol, DQNSettings, REPO_ROOT, archive_inputs, run_benchmark, train_dqn,
)
from ml.src.masked_dqn import MaskedDQN, masked_bootstrap
from ml.src.ppo_training import PPOConfig, make_training_environment
from ml.src.ppo_training import environment_manifest


def observation(profile=(0, 1, 1, 1, 1, 1, 1), step=0):
    return np.asarray([*profile, *([0] * 7), step], dtype=np.float32)


def pilot_protocol_values():
    return {
        "study_id": "test", "stage": "pilot", "training_timesteps": 4096,
        "training_seeds": [61000, 62000, 63000],
        "evaluation_seed_bases": [710001, 720001], "baseline_policy_seed_start": 810001,
        "ppo_config": "experiments/ppo_baseline_config.json", "dqn": {},
    }


def test_selection_exploration_and_warmup_never_choose_resistant_actions():
    environment = make_training_environment(PPOConfig())
    model = MaskedDQN("MlpPolicy", environment, gamma=1.0, seed=12)
    try:
        with torch.no_grad():
            for parameter in model.q_net.parameters():
                parameter.zero_()
            model.q_net.q_net[-1].bias.copy_(torch.tensor([-10., 500., 400., 300., 200., 100., 50.]))
        # The only feasible action deliberately has the lowest Q-value.
        assert int(model.predict(observation(), deterministic=True)[0]) == 0
        model.exploration_rate = 1.0
        for _ in range(30):
            assert int(model.predict(observation(), deterministic=False)[0]) == 0
        batch = np.stack([observation(), observation((1, 1, 1, 1, 1, 1, 0))])
        model._last_obs = batch
        for _ in range(30):
            actions, replay_actions = model._sample_action(learning_starts=100, n_envs=2)
            np.testing.assert_array_equal(actions, [0, 6])
            np.testing.assert_array_equal(actions, replay_actions)
        with pytest.raises(ValueError, match="no susceptible action"):
            model.predict(observation((1,) * 7), deterministic=True)
    finally:
        environment.close()


def test_bellman_target_masks_invalid_actions_and_terminal_bootstrap():
    states = torch.tensor(np.stack([
        observation(), observation((1,) * 7), observation(),
    ]))
    q_values = torch.tensor([[-4., 100., 90., 80., 70., 60., 50.]] * 3)
    dones = torch.tensor([[0.], [1.], [1.]])
    actual = masked_bootstrap(q_values, states, dones)
    torch.testing.assert_close(actual, torch.tensor([[-4.], [0.], [0.]]))
    assert torch.isfinite(actual).all()
    with pytest.raises(ValueError, match="nonterminal replay state"):
        masked_bootstrap(q_values[1:2], states[1:2], torch.zeros((1, 1)))


@pytest.mark.parametrize("values", [
    {"training_seeds": [1, 2]},
    {"training_seeds": [1, 1]},
    {"evaluation_seed_bases": [100001, 100002]},
    {"evaluation_seed_bases": [61000]},
    {"baseline_policy_seed_start": 710001},
    {"training_timesteps": 256},
])
def test_protocol_rejects_overlapping_seed_streams_and_invalid_budgets(values):
    data = pilot_protocol_values()
    with pytest.raises(ValueError):
        BenchmarkProtocol.from_dict({**data, **values})


def test_protocol_refuses_budget_that_would_overshoot_ppo_rollouts():
    data = pilot_protocol_values()
    protocol = BenchmarkProtocol.from_dict({**data, "training_timesteps": 4100})
    with pytest.raises(ValueError, match="PPO rollout length"):
        protocol.shared_config(61000)


def test_public_data_retraining_pins_new_data_and_refuses_another_dataset(tmp_path):
    protocol = BenchmarkProtocol.from_dict(json.loads(Path("experiments/dqn_public_data_v2_config.json").read_text()))
    assert protocol.ppo_checkpoint_root is None
    assert len(protocol.training_seeds) == 20
    assert protocol.expected_interaction_data_sha256 == environment_manifest(protocol.shared_config(12000))["interaction_data_sha256"]
    with pytest.raises(ValueError, match="dataset pinned"):
        run_benchmark(replace(protocol, expected_interaction_data_sha256="0" * 64), tmp_path / "wrong-data")
    assert not (tmp_path / "wrong-data").exists()


def test_short_training_changes_weights_and_roundtrips_checkpoint(tmp_path):
    config = PPOConfig(
        ppo_seed=61, environment_seed=62, evaluation_seed=63, total_timesteps=32,
        n_steps=16, batch_size=8, evaluation_frequency=16, evaluation_episodes=2,
        policy_architecture=(16,),
    )
    settings = DQNSettings(learning_starts=4, batch_size=4, buffer_size=64, target_update_interval=8)
    summary = train_dqn(config, settings, tmp_path / "first")
    assert summary["total_timesteps"] == 32
    assert summary["gradient_updates"] > 0
    model = MaskedDQN.load(tmp_path / "first" / "final_model.zip", device="cpu")
    environment = make_training_environment(config)
    initial = MaskedDQN(
        "MlpPolicy", environment, **settings.__dict__, gamma=1.,
        policy_kwargs={"net_arch": [16]}, seed=61, device="cpu",
    )
    try:
        assert any(not torch.equal(a, b) for a, b in zip(model.q_net.parameters(), initial.q_net.parameters()))
        assert int(model.predict(observation(), deterministic=True)[0]) == 0
        # Same seed/config retrains to the same learned weights, not just feasible predictions.
        train_dqn(config, settings, tmp_path / "second")
        repeated = MaskedDQN.load(tmp_path / "second" / "final_model.zip", device="cpu")
        for first, second in zip(model.q_net.parameters(), repeated.q_net.parameters()):
            torch.testing.assert_close(first, second, rtol=0, atol=0)
        with pytest.raises(FileExistsError):
            train_dqn(config, settings, tmp_path / "first")
    finally:
        environment.close()


def test_three_strategy_benchmark_preserves_paired_cases_and_saved_traces(tmp_path, monkeypatch):
    protocol = BenchmarkProtocol(
        study_id="test", stage="pilot", training_timesteps=256, training_seeds=(61000,),
        evaluation_seed_bases=(710001,), baseline_policy_seed_start=810001,
        ppo_config="experiments/ppo_baseline_config.json",
        dqn=DQNSettings(learning_starts=8, buffer_size=512),
    )
    output = tmp_path / "benchmark"
    report = run_benchmark(protocol, output)
    assert report["evaluation_profile_count"] == 128
    assert report["replicates"][0]["actual_timesteps_per_model"] == 256
    assert set(report["summary"]) == {"dqn", "ppo", "random_susceptible_baseline"}
    for strategy in ("dqn", "ppo"):
        evaluation = json.loads((output / "seed_61000" / strategy / "evaluation.json").read_text())
        episodes = evaluation["runs"][0]["evaluation"]["episodes"]
        assert len(episodes) == 128
        assert episodes[-1]["steps"] == []
        assert episodes[-1]["terminal_reward_adjustment"] == -8
        assert report["summary"][strategy]["susceptible_action_rate"] == 1.0
    assert json.loads((output / "status.json").read_text())["status"] == "completed"
    assert (output / "report.md").exists()
    with pytest.raises(FileExistsError):
        run_benchmark(protocol, output)
    checkpoint = output / "seed_61000" / "dqn" / "final_model.zip"
    modified = checkpoint.stat().st_mtime_ns

    def unexpected_training(*args, **kwargs):
        raise AssertionError("A completed replicate must not be retrained on resume.")

    monkeypatch.setattr("ml.src.dqn_benchmark.train_dqn", unexpected_training)
    resumed = run_benchmark(protocol, output, resume=True)
    assert resumed["summary"] == report["summary"]
    assert checkpoint.stat().st_mtime_ns == modified
    with monkeypatch.context() as changed:
        changed.setattr("ml.src.dqn_benchmark.environment_manifest", lambda config: {
            **environment_manifest(config), "interaction_data_sha256": "0" * 64,
        })
        with pytest.raises(ValueError, match="Cannot resume: dataset"):
            run_benchmark(protocol, output, resume=True)
    snapshot = output / "empirical_interactions.csv"
    original_csv = snapshot.read_bytes()
    snapshot.write_bytes(original_csv + b"changed")
    with pytest.raises(ValueError, match="archived training interactions changed"):
        run_benchmark(protocol, output, resume=True)
    snapshot.write_bytes(original_csv)
    with pytest.raises(ValueError, match="Cannot resume"):
        run_benchmark(replace(protocol, study_id="different"), output, resume=True)
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checkpoint changed"):
        run_benchmark(protocol, output, resume=True)


def test_archived_ppo_must_match_budget_and_checksums(tmp_path, monkeypatch):
    from ml.src.artifact_checksums import checksum_of

    values = json.loads(Path("experiments/dqn_public_data_v2_config.json").read_text())
    protocol = BenchmarkProtocol.from_dict(values)
    config = protocol.shared_config(1000)
    target = tmp_path / "ppo_seed_1000"
    target.mkdir()
    inputs = {
        "final_model.zip": b"test-checkpoint",
        "config.json": json.dumps(config.to_dict()).encode(),
        "environment_manifest.json": json.dumps(environment_manifest(config)).encode(),
        "training_summary.json": json.dumps({
            "algorithm": "MaskablePPO", "total_timesteps": config.total_timesteps,
            "software_versions": {
                key: version(package) for package, key in (
                    ("torch", "torch"), ("stable-baselines3", "stable_baselines3"),
                    ("sb3-contrib", "sb3_contrib"), ("gymnasium", "gymnasium"),
                )
            },
        }).encode(),
    }
    for name, data in inputs.items():
        (target / name).write_bytes(data)
    (tmp_path / "SHA256SUMS.txt").write_text("".join(
        f"{checksum_of(name, data)}  ppo_seed_1000/{name}\n" for name, data in inputs.items()
    ))
    assert archive_inputs(config, tmp_path) == inputs
    with monkeypatch.context() as changed:
        changed.setattr("ml.src.dqn_benchmark.environment_manifest", lambda current: {
            **environment_manifest(current), "interaction_data_sha256": "0" * 64,
        })
        with pytest.raises(ValueError, match="simulator or transition-data manifest differs"):
            archive_inputs(config, tmp_path)
    with pytest.raises(ValueError, match="actual training budget"):
        archive_inputs(replace(config, total_timesteps=512), tmp_path)
    (target / "final_model.zip").write_bytes(inputs["final_model.zip"] + b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        archive_inputs(config, tmp_path)


def test_frozen_policies_match_best_validation_candidates_and_remain_feasible():
    from experiments.freeze_models import verify_frozen
    from ml.src.artifact_checksums import verify_checksums

    folder = REPO_ROOT / "artifacts/frozen/public-data-v2"
    selection = json.loads((folder / "selection.json").read_text())
    with (folder / "selection.csv").open(newline="") as stream:
        candidates = list(csv.DictReader(stream))
    for strategy in ("ppo", "dqn"):
        rows = [row for row in candidates if row["strategy"] == strategy]
        assert len(rows) == len({row["training_seed"] for row in rows}) == 20
        best = min(rows, key=lambda row: (
            float(row["resistance_burden"]), float(row["resistance_emergence_events"]),
            -float(row["remaining_susceptible_options"]), int(row["training_seed"]),
        ))
        assert int(best["training_seed"]) == selection["selected"][strategy]["training_seed"]
        assert best["checkpoint_sha256"] == selection["selected"][strategy]["checkpoint_sha256"]
    schedules = [set(range(base, base + 128)) for base in (
        *selection["validation_seed_bases"], *selection["confirmation_seed_bases"],
    )]
    assert sum(map(len, schedules)) == len(set().union(*schedules))
    assert all(result.status == "ok" for result in verify_checksums(folder / "SHA256SUMS.txt"))
    assert verify_frozen(folder) == 254


def test_freeze_verification_rejects_a_changed_selected_checkpoint(tmp_path):
    from experiments.freeze_models import verify_frozen

    source = REPO_ROOT / "artifacts/frozen/public-data-v2"
    (tmp_path / "ppo").mkdir()
    shutil.copyfile(source / "selection.json", tmp_path / "selection.json")
    shutil.copyfile(source / "ppo/manifest.json", tmp_path / "ppo/manifest.json")
    (tmp_path / "ppo/final_model.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint differs"):
        verify_frozen(tmp_path)


def test_enumerated_review_matches_hand_calculated_occurrence_and_fallback_costs():
    from types import SimpleNamespace
    from experiments.review_frozen_policies import EnumeratedModel
    from simulation.candidate_transition import CandidateTransition

    candidate = CandidateTransition("NITROFURANTOIN", "collateral_sensitivity", ("test",))
    generator = SimpleNamespace(generate=lambda state, action: (candidate,) if state.resistance[1] and action == 0 else ())
    model = EnumeratedModel(generator, "SENSITIVITY_Q_025", 2, lambda *context: 0)
    profile = (0, 1, 1, 1, 1, 1, 1)
    # At t=1, resistance is 6 with probability .75; at t=2, with probability .75**2.
    expected = ((5 + .75) + (5 + .75**2)) / 7
    assert model.optimal(profile, 2) == pytest.approx(expected)
    values = model.policy("ppo", profile, None, 2)
    assert values == pytest.approx((expected, 0, 2 - .75**2, .25, 1))
    assert model.policy("random_susceptible_baseline", profile, None, 2)[0] == pytest.approx(expected)


def test_enumerated_review_preserves_terminal_tail_cost_without_inventing_actions():
    from types import SimpleNamespace
    from experiments.review_frozen_policies import EnumeratedModel
    from simulation.candidate_transition import CandidateTransition

    candidate = CandidateTransition("CIPROFLOXACIN", "cross_resistance", ("test",))
    model = EnumeratedModel(SimpleNamespace(generate=lambda *args: (candidate,)), "REF_UNIFORM_SUPPORTED", 3, lambda *context: 0)
    assert model.optimal((0, 1, 1, 1, 1, 1, 1), 3) == 3
    assert model.policy("ppo", (0, 1, 1, 1, 1, 1, 1), None, 3) == (3, 1, 0, 0, 0)
    assert model.policy("ppo", (1,) * 7, None, 3) == (3, 0, 0, 0, 0)
