import json

import numpy as np
import pytest
import torch

import ml.src.gentamicin_audit as audit
from ml.src.gentamicin_audit import (
    counterfactual_one_step_actions,
    extract_masked_action_probabilities,
    run_gentamicin_audit,
)
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig, make_training_environment
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


class FakeDistribution:
    def __init__(self, probabilities):
        self.distribution = type("Categorical", (), {"probs": torch.tensor([probabilities])})()


class FakePolicy:
    def __init__(self, probabilities):
        self.probabilities = probabilities
        self.seen_mask = None

    def obs_to_tensor(self, observation):
        return torch.as_tensor(observation).unsqueeze(0), False

    def get_distribution(self, observation, *, action_masks):
        self.seen_mask = action_masks.copy()
        return FakeDistribution(self.probabilities)


class FakeModel:
    def __init__(self, probabilities):
        self.policy = FakePolicy(probabilities)


def test_action_probabilities_respect_mask_and_sum_to_one():
    mask = np.asarray([True, False, True, True, True, False, True])
    model = FakeModel([0.2, 0.0, 0.1, 0.15, 0.4, 0.0, 0.15])
    probabilities = extract_masked_action_probabilities(model, np.zeros(15), mask)

    assert probabilities[ANTIBIOTICS.index("GENTAMICIN")] == pytest.approx(0.4)
    assert sum(probabilities) == pytest.approx(1.0)
    assert all(probability == 0.0 for probability, valid in zip(probabilities, mask) if not valid)
    assert np.array_equal(model.policy.seen_mask, mask.reshape(1, -1))


def test_counterfactual_alternatives_use_seed_without_mutating_environment():
    config = PPOConfig(horizon=8)
    environment = make_training_environment(config)
    initial_episode = environment.episode
    rng_state = environment.np_random.bit_generator.state.copy()
    state = ResistanceState((0,) * 7)

    alternatives = counterfactual_one_step_actions(environment, state, 123456, 0)

    assert len(alternatives) == len(ANTIBIOTICS)
    gent = alternatives[ANTIBIOTICS.index("GENTAMICIN")]
    assert gent["transition_type"] == "unsupported_no_candidate"
    assert gent["next_state"] == "SSSSSSS"
    assert gent["immediate_reward"] == 0.0
    assert all(row["same_seed_one_step_counterfactual"] for row in alternatives)
    assert all(not row["downstream_rollout_evaluated"] for row in alternatives)
    assert environment.episode is initial_episode
    assert environment.np_random.bit_generator.state == rng_state
    environment.close()


def test_invalid_policy_probability_distribution_is_rejected():
    mask = np.asarray([True] * 7)
    model = FakeModel([0.4, 0.4, 0, 0, 0, 0, 0])
    with pytest.raises(ValueError, match="sum to one"):
        extract_masked_action_probabilities(model, np.zeros(15), mask)


def test_audit_trace_reconstructs_real_decision_without_mutating_audit_environment(tmp_path, monkeypatch):
    config = PPOConfig(horizon=8)
    initial_state = (0,) * 7
    evaluation_seed = 321
    ppo_environment = make_training_environment(config)
    ppo_observation, _ = ppo_environment.reset(
        seed=evaluation_seed,
        options={"initial_resistance_state": initial_state},
    )
    ppo_next_observation, ppo_reward, ppo_terminated, ppo_truncated, ppo_info = ppo_environment.step(4)

    greedy_environment = make_training_environment(config)
    greedy_observation, _ = greedy_environment.reset(
        seed=evaluation_seed,
        options={"initial_resistance_state": initial_state},
    )
    greedy_next_observation, greedy_reward, greedy_terminated, greedy_truncated, greedy_info = greedy_environment.step(2)
    ppo_environment.close()
    greedy_environment.close()

    profiles = [list(profile.resistance) for profile in canonical_initial_profiles()]
    matched_dir = tmp_path / "matched"
    model_dir = matched_dir / "models" / "ppo_seed_71"
    model_dir.mkdir(parents=True)
    (matched_dir / "config.json").write_text(json.dumps({
        "scenario_id": config.scenario_id,
        "horizon": config.horizon,
        "initial_profiles": profiles,
        "evaluation_seed_bases_by_training_seed": {"71": [evaluation_seed]},
    }), encoding="utf-8")
    fake_model_path = tmp_path / "model.zip"
    (model_dir / "config.json").write_text(json.dumps({
        "ppo_model_path": str(fake_model_path),
    }), encoding="utf-8")
    ppo_episode = {
        "episode_id": 0,
        "environment_seed": evaluation_seed,
        "policy_seed": 99,
        "initial_resistance_profile": list(initial_state),
        "final_resistance_profile": list(ppo_next_observation[:7].astype(int)),
        "steps": [{
            "observation": ppo_observation.tolist(),
            "action": 4,
            "next_observation": ppo_next_observation.tolist(),
            "reward": float(ppo_reward),
            "terminated": ppo_terminated,
            "truncated": ppo_truncated,
            "info": ppo_info,
        }],
        "cumulative_reward": float(ppo_reward),
        "terminal_reward_adjustment": 0.0,
        "termination_reason": "maximum_horizon",
    }
    greedy_episode = {
        **ppo_episode,
        "steps": [{
            "observation": greedy_observation.tolist(),
            "action": 2,
            "next_observation": greedy_next_observation.tolist(),
            "reward": float(greedy_reward),
            "terminated": greedy_terminated,
            "truncated": greedy_truncated,
            "info": greedy_info,
        }],
        "final_resistance_profile": list(greedy_next_observation[:7].astype(int)),
        "cumulative_reward": float(greedy_reward),
    }
    raw_case = [{
        "case_id": "case_321_profile_000",
        "initial_state": "SSSSSSS",
        "evaluation_seed": evaluation_seed,
        "ppo": ppo_episode,
        "greedy": greedy_episode,
    }]
    (model_dir / "raw_trajectories.json").write_text(
        json.dumps(raw_case, default=lambda value: value.item() if isinstance(value, np.generic) else value),
        encoding="utf-8",
    )
    ppo_config_path = tmp_path / "ppo.json"
    ppo_config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")

    audit_environments = []
    def make_audit_environment(audit_config):
        environment = make_training_environment(audit_config)
        audit_environments.append(environment)
        return environment

    monkeypatch.setattr(audit, "load_ppo_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(audit, "extract_masked_action_probabilities", lambda *_args: (1 / 7,) * 7)
    monkeypatch.setattr(audit, "make_training_environment", make_audit_environment)
    audit_env_state = audit_environments
    result = run_gentamicin_audit(matched_dir, ppo_config_path, tmp_path / "audit")

    decision = json.loads((tmp_path / "audit" / "decision_audit.json").read_text(encoding="utf-8"))[0]
    assert decision["selected_antibiotic"] == "GENTAMICIN"
    assert decision["gentamicin_feasible"] is True
    assert decision["resistance_count_before"] == sum(initial_state)
    assert decision["resistance_count_after"] == sum(ppo_next_observation[:7])
    assert decision["reward"] == pytest.approx(ppo_reward)
    assert sum(decision["action_probabilities"].values()) == pytest.approx(1.0)
    assert decision["actual_transition_type"] == ppo_info["transition_status"]
    assert result["summary"]["gentamicin_infeasible_actions_selected"] == 0
    assert audit_env_state and all(environment.episode is None for environment in audit_env_state)
