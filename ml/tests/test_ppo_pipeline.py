from pathlib import Path

import pytest

from ml.src.ppo_evaluation import evaluate_ppo
from ml.src.ppo_training import PPOConfig, load_ppo_model, train_ppo
from simulation.environment import AntibioticEnvironment


def smoke_config() -> PPOConfig:
    return PPOConfig(
        ppo_seed=71,
        environment_seed=83,
        evaluation_seed=97,
        horizon=3,
        total_timesteps=32,
        n_steps=16,
        batch_size=8,
        n_epochs=2,
        evaluation_frequency=16,
        evaluation_episodes=2,
        policy_architecture=(16, 16),
    )


def test_maskable_ppo_training_checkpoint_evaluation_and_traces(tmp_path: Path):
    config = smoke_config()
    training_dir = tmp_path / "training"
    summary = train_ppo(config, training_dir)

    checkpoint = training_dir / "final_model.zip"
    assert checkpoint.exists()
    assert (training_dir / "checkpoints" / "best_model.zip").exists()
    assert (training_dir / "config.json").exists()
    assert (training_dir / "environment_manifest.json").exists()
    assert (training_dir / "training_episodes.json").exists()
    assert (training_dir / "training_summary.json").exists()
    assert (training_dir / "plots" / "training_reward.png").exists()
    assert (training_dir / "plots" / "training_resistance_burden.png").exists()
    assert (training_dir / "plots" / "training_action_distribution.png").exists()
    assert (training_dir / "plots" / "training_episode_length.png").exists()
    assert summary["action_masking"] is True
    assert summary["total_timesteps"] == 32

    model = load_ppo_model(checkpoint)
    environment = AntibioticEnvironment(max_steps=config.horizon)
    observation, _ = environment.reset(seed=1)
    action_masks = environment.action_masks()
    action, _ = model.predict(observation, action_masks=action_masks, deterministic=True)
    assert action_masks[int(action)]
    environment.close()

    evaluation_dir = tmp_path / "evaluation"
    result = evaluate_ppo(
        checkpoint,
        config,
        evaluation_dir,
        initial_states=[(0,) * 7, (1, 0, 1, 0, 1, 0, 0), (1,) * 7],
    )
    assert result["summary"]["treatment_effectiveness_rate"] == 1.0
    assert len(result["episodes"]) == 3
    assert (evaluation_dir / "evaluation_results.json").exists()
    assert (evaluation_dir / "decision_traces.json").exists()
    assert result["environment_manifest"]["interaction_data_sha256"]
    assert result["software_versions"]["sb3_contrib"] == "2.9.0"
    assert (evaluation_dir / "plots" / "final_resistance_distribution.png").exists()
    assert (evaluation_dir / "plots" / "evaluation_action_distribution.png").exists()
    assert (evaluation_dir / "plots" / "example_resistance_trajectories.png").exists()
    assert (evaluation_dir / "plots" / "resistance_state_heatmap.png").exists()

    for episode in result["episodes"]:
        for step in episode["steps"]:
            assert step["selected_antibiotic_name"] in step["feasible_actions"]
            assert step["was_action_effective"] is True
            assert step["current_resistance_count"] == sum(
                value == "R" for value in step["current_state"]
            )
            assert step["next_resistance_count"] == sum(
                value == "R" for value in step["next_state"]
            )
    assert result["episodes"][-1]["steps"] == []
    assert result["episodes"][-1]["terminal_reward_adjustment"] == -config.horizon


def test_ppo_config_rejects_discounting_for_burden_objective():
    with pytest.raises(ValueError, match="requires gamma=1.0"):
        PPOConfig(gamma=0.99)
