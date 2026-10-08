from copy import deepcopy
import json

import numpy as np
import pytest

from ml.src.decision_traces import build_decision_trace
import ml.src.decision_trace_report as reporting
from ml.src.ppo_training import PPOConfig, make_training_environment


def saved_episode(environment):
    profile = (1, 0, 1, 0, 0, 0, 0)
    observation, _ = environment.reset(seed=123, options={"initial_resistance_state": profile})
    next_observation, reward, terminated, truncated, info = environment.step(4)
    return {
        "episode_id": 2,
        "environment_seed": 123,
        "initial_resistance_profile": list(profile),
        "steps": [{
            "observation": observation.tolist(), "action": 4,
            "next_observation": next_observation.tolist(), "reward": reward,
            "terminated": terminated, "truncated": truncated, "info": info,
        }],
    }


def build(environment, episode, probabilities=None):
    return build_decision_trace(
        episode, 0, probabilities or [0, .05, 0, .05, .8, .05, .05], environment,
        case_id="case_123", training_seed=1000, checkpoint_identifier="model.zip",
    )


def test_complete_reproducible_trace_matches_live_mask_and_does_not_mutate_environment():
    environment = make_training_environment(PPOConfig())
    episode = saved_episode(environment)
    state_before = environment.episode
    rng_before = deepcopy(environment.np_random.bit_generator.state)
    inputs_before = deepcopy(episode)
    first = build(environment, episode)
    assert first == build(environment, episode)
    assert first["action_mask"] == environment.action_masks().tolist()
    assert first["next_state"] == list(environment.episode.resistance_state.resistance)
    assert first["reward"] == episode["steps"][0]["reward"]
    assert first["remaining_feasible_actions"] == first["feasible_actions"]
    assert sum(first["policy_action_probabilities"]) == pytest.approx(1)
    assert environment.episode is state_before
    assert environment.np_random.bit_generator.state == rng_before
    assert episode == inputs_before
    control = make_training_environment(PPOConfig())
    saved_episode(control)
    assert environment.step(4)[1:] == control.step(4)[1:]
    environment.close()
    control.close()


@pytest.mark.parametrize("field,value", [
    ("action", 0), ("reward", -99),
    ("next_observation", [0] * 15),
])
def test_corrupt_action_reward_and_next_state_are_rejected(field, value):
    environment = make_training_environment(PPOConfig())
    episode = saved_episode(environment)
    episode["steps"][0][field] = value
    with pytest.raises(ValueError):
        build(environment, episode)
    environment.close()


def test_invalid_or_masked_probability_mass_is_rejected():
    environment = make_training_environment(PPOConfig())
    episode = saved_episode(environment)
    with pytest.raises(ValueError, match="normalized"):
        build(environment, episode, [1 / 7] * 7)
    environment.close()


def test_saved_trace_report_is_reproducible_and_saves_representatives(tmp_path, monkeypatch):
    config = PPOConfig()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    source = tmp_path / "matched"
    directory = source / "models" / "ppo_seed_1000"
    directory.mkdir(parents=True)
    checkpoint = tmp_path / "checkpoint.zip"
    checkpoint.write_bytes(b"synthetic test checkpoint")
    (source / "config.json").write_text(json.dumps({
        "scenario_id": config.scenario_id, "horizon": config.horizon,
        "evaluation_seed_bases_by_training_seed": {"1000": [123]},
    }), encoding="utf-8")
    (directory / "config.json").write_text(json.dumps({"ppo_model_path": str(checkpoint)}), encoding="utf-8")
    environment = make_training_environment(config)
    episode = saved_episode(environment)
    episode["final_resistance_profile"] = episode["steps"][0]["next_observation"][:7]
    raw = [{"case_id": "case_123", "ppo": episode, "greedy": deepcopy(episode)}]
    (directory / "raw_trajectories.json").write_text(
        json.dumps(raw, default=lambda value: value.item()), encoding="utf-8",
    )
    environment.close()
    monkeypatch.setattr(reporting, "load_ppo_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(reporting, "extract_masked_action_probabilities", lambda *_args: (0, .05, 0, .05, .8, .05, .05))
    first = reporting.generate_trace_report(source, config_path, tmp_path / "first")
    second = reporting.generate_trace_report(source, config_path, tmp_path / "second")
    assert first == second
    assert first["gentamicin_selected"] == 1
    assert first["gentamicin_categories"] == {"unchanged_unsupported_no_candidate": 1}
    assert first["representatives"]["resistance_increasing"] is None
    assert first["representatives"]["resistance_reducing"] is None
    assert (tmp_path / "first" / "canonical_decisions.jsonl").read_text() == (
        tmp_path / "second" / "canonical_decisions.jsonl"
    ).read_text()
    assert (tmp_path / "first" / "plots" / "typical_policy_distributions.png").exists()
    with pytest.raises(FileExistsError):
        reporting.generate_trace_report(source, config_path, tmp_path / "first")