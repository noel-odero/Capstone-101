import json
from pathlib import Path

import numpy as np

import ml.src.matched_policy_evaluation as matched
from ml.src.ppo_training import PPOConfig
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ANTIBIOTICS


class FirstFeasibleModel:
    def predict(self, observation, *, deterministic, action_masks):
        assert deterministic is True
        return int(np.flatnonzero(action_masks)[0]), None


def matched_config() -> PPOConfig:
    return PPOConfig(
        ppo_seed=10,
        environment_seed=20,
        evaluation_seed=30,
        horizon=4,
        total_timesteps=32,
        n_steps=16,
        batch_size=8,
        n_epochs=2,
        evaluation_frequency=16,
        evaluation_episodes=2,
        matched_evaluation_seed_bases=(110001, 120001),
        matched_policy_seed_start=900001,
        policy_architecture=(16, 16),
    )


def run_small_match(tmp_path: Path, monkeypatch, output_name: str):
    config = matched_config()
    created_environments = []
    closed_environment_ids = set()
    real_factory = matched.make_training_environment

    def tracked_factory(environment_config):
        environment = real_factory(environment_config)
        created_environments.append(environment)
        environment.close = lambda: closed_environment_ids.add(id(environment))
        return environment

    monkeypatch.setattr(matched, "make_training_environment", tracked_factory)
    monkeypatch.setattr(matched, "load_ppo_model", lambda _path, device="cpu": FirstFeasibleModel())
    profiles = [
        (0, 0, 0, 0, 0, 0, 0),
        (1, 0, 1, 0, 0, 0, 0),
        (1, 1, 1, 1, 1, 1, 1),
    ]
    result = matched.run_matched_policy_evaluation(
        "synthetic-checkpoint.zip",
        config,
        tmp_path / output_name,
        initial_profiles=profiles,
    )
    assert len(created_environments) == 4
    assert len({id(environment) for environment in created_environments}) == 4
    assert closed_environment_ids == {id(environment) for environment in created_environments}
    return result, profiles


def test_matched_cases_preserve_profile_order_and_common_seed_stream(tmp_path, monkeypatch):
    result, profiles = run_small_match(tmp_path, monkeypatch, "matched")
    rows = result["raw_results"]
    assert len(rows) == 6
    assert [row["initial_resistance_profile"] for row in rows] == [
        list(profile) for profile in profiles
    ] * 2
    assert [row["evaluation_seed"] for row in rows] == [110001, 110002, 110003, 120001, 120002, 120003]
    assert [row["case_id"] for row in rows] == [
        "seed_110001_profile_000", "seed_110001_profile_001", "seed_110001_profile_002",
        "seed_120001_profile_000", "seed_120001_profile_001", "seed_120001_profile_002",
    ]

    for trajectory in result["raw_trajectories"]:
        ppo = trajectory["ppo"]
        greedy = trajectory["greedy"]
        assert ppo["initial_resistance_profile"] == greedy["initial_resistance_profile"]
        assert ppo["environment_seed"] == greedy["environment_seed"]
        for ppo_step, greedy_step in zip(ppo["steps"], greedy["steps"]):
            assert ppo_step["info"]["transition_seed"] == greedy_step["info"]["transition_seed"]


def test_matched_metrics_and_difference_directions_are_correct(tmp_path, monkeypatch):
    result, _ = run_small_match(tmp_path, monkeypatch, "metrics")
    first = result["raw_results"][0]
    assert first["greedy_minus_ppo_burden"] == (
        first["greedy_cumulative_resistance_burden"]
        - first["ppo_cumulative_resistance_burden"]
    )
    assert first["greedy_minus_ppo_final_resistant"] == (
        first["greedy_final_resistant_antibiotics"]
        - first["ppo_final_resistant_antibiotics"]
    )
    assert first["greedy_minus_ppo_resistance_emergence_events"] == (
        first["greedy_resistance_emergence_events"]
        - first["ppo_resistance_emergence_events"]
    )
    assert first["ppo_cumulative_resistance_burden"] == -first["ppo_cumulative_reward"]
    assert first["initial_state"] == "SSSSSSS"


def test_matched_results_are_reproducible_and_persist_raw_artifacts(tmp_path, monkeypatch):
    first, _ = run_small_match(tmp_path, monkeypatch, "first")
    second, _ = run_small_match(tmp_path, monkeypatch, "second")
    assert first["raw_results"] == second["raw_results"]
    assert first["summary"] == second["summary"]
    config_path = tmp_path / "first" / "config.json"
    raw_csv = tmp_path / "first" / "raw_results.csv"
    raw_traces = tmp_path / "first" / "raw_trajectories.json"
    summary_path = tmp_path / "first" / "summary.json"
    assert config_path.exists() and raw_csv.exists() and raw_traces.exists() and summary_path.exists()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert len(config["initial_profiles"]) == 3
    assert config["evaluation_seed_bases"] == [110001, 120001]
    assert config["reward_configuration"]["objective"] == "normalized_resistance_burden"
    assert config["action_mask_configuration"]["enabled"] is True


def test_production_profile_order_is_canonical_all_binary_order():
    profiles = matched.canonical_initial_profiles()
    assert len(profiles) == 128
    assert profiles[0].resistance == (0,) * 7
    assert profiles[-1].resistance == (1,) * 7
    assert len({profile.resistance for profile in profiles}) == 128
    assert all(len(profile.resistance) == len(ANTIBIOTICS) for profile in profiles)


def test_multi_checkpoint_aggregate_preserves_seed_and_profile_results(tmp_path, monkeypatch):
    config = PPOConfig(
        **{
            **matched_config().to_dict(),
            "matched_evaluation_seed_bases": (110001,),
            "matched_runs_independence_assumed": True,
        }
    )
    model_paths = []
    for seed in (1000, 2000):
        model_directory = tmp_path / f"model_{seed}"
        model_directory.mkdir()
        (model_directory / "config.json").write_text(
            json.dumps({"ppo_seed": seed, "scenario_id": config.scenario_id, "horizon": config.horizon}),
            encoding="utf-8",
        )
        model_paths.append(model_directory / "final_model.zip")

    def fake_matched_run(model_path, run_config, output_dir, *, evaluation_seed_bases, policy_seed_start=None, initial_profiles=None):
        profiles = matched.canonical_initial_profiles()
        base = evaluation_seed_bases[0]
        training_seed = int(Path(model_path).parent.name.split("_")[-1])
        rows = []
        for index, profile in enumerate(profiles):
            profile_bits = profile.resistance
            ppo_burden = float((sum(profile_bits) + training_seed // 1000) / 7)
            greedy_burden = ppo_burden + (0.5 if training_seed == 1000 else -0.25)
            ppo_final = sum(profile_bits)
            greedy_final = ppo_final + (1 if training_seed == 1000 else 0)
            ppo_events = 0
            greedy_events = int(training_seed == 1000)
            rows.append({
                "case_id": f"seed_{base}_profile_{index:03d}",
                "evaluation_seed_base": base,
                "evaluation_seed": base + index,
                "profile_index": index,
                "initial_state": "".join("R" if bit else "S" for bit in profile_bits),
                "ppo_cumulative_resistance_burden": ppo_burden,
                "greedy_cumulative_resistance_burden": greedy_burden,
                "greedy_minus_ppo_burden": greedy_burden - ppo_burden,
                "ppo_final_resistant_antibiotics": ppo_final,
                "greedy_final_resistant_antibiotics": greedy_final,
                "greedy_minus_ppo_final_resistant": greedy_final - ppo_final,
                "ppo_resistance_emergence_events": ppo_events,
                "greedy_resistance_emergence_events": greedy_events,
                "greedy_minus_ppo_resistance_emergence_events": greedy_events - ppo_events,
                "ppo_resistance_emergence_rate": 0.0,
                "greedy_resistance_emergence_rate": float(greedy_events),
                "greedy_minus_ppo_resistance_emergence_rate": float(greedy_events),
                "ppo_treatment_effectiveness_rate": 1.0,
                "greedy_treatment_effectiveness_rate": 1.0,
                "greedy_minus_ppo_treatment_effectiveness_rate": 0.0,
                "ppo_episode_length": 8,
                "greedy_episode_length": 8,
                "ppo_cumulative_reward": -ppo_burden,
                "greedy_cumulative_reward": -greedy_burden,
                "greedy_minus_ppo_reward": ppo_burden - greedy_burden,
            })
        return {
            "config": {"reward_configuration": {"objective": "normalized_resistance_burden"}},
            "summary": {"matched_case_count": len(rows)},
            "raw_results": rows,
        }

    monkeypatch.setattr(matched, "run_matched_policy_evaluation", fake_matched_run)
    result = matched.run_matched_ppo_seed_ensemble(
        model_paths,
        config,
        tmp_path / "ensemble",
    )
    assert result["summary"]["training_seed_count"] == 2
    assert result["summary"]["matched_case_count"] == 256
    assert result["summary"]["per_initial_profile_direction_counts"]["ppo_lower_mean_burden"] == 128
    assert len(result["per_initial_profile"]) == 128
    assert (tmp_path / "ensemble" / "raw_results.csv").exists()
    assert (tmp_path / "ensemble" / "per_initial_profile.csv").exists()
    assert (tmp_path / "ensemble" / "report.md").exists()
    assert len(result["plots"]) == 3
