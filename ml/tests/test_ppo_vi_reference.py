from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from ml.src.ppo_vi_reference import (
    compare_reference_action, planning_state_from_observation,
    reference_observation, reference_predecessor_histories,
)
from ml.src.value_iteration import value_iteration
from ml.src.decision_traces import build_decision_trace
import ml.src.ppo_vi_benchmark as benchmark
from ml.src.ppo_training import PPOConfig, environment_manifest, make_training_environment
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.episode import EpisodeState
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def test_observation_encoding_retains_resistance_time_and_last_action():
    state = EpisodeState(ResistanceState((1, 0, 1, 0, 0, 0, 0)), 3)
    observation = reference_observation(state, 4)
    assert planning_state_from_observation(observation) == state
    assert observation[11] == 1
    assert sum(observation[7:14]) == 1
    assert ANTIBIOTICS[4] == "GENTAMICIN"


def test_exact_ties_are_optimal_not_policy_errors_and_q_lookup_is_correct():
    environment = DeterministicReferenceEnvironment()
    solution = value_iteration(environment)
    state = EpisodeState(ResistanceState((0,) * 7), 7)
    tie = compare_reference_action(environment, solution, state, 4)
    assert tie["vi_optimal_action"] == 2
    assert tie["selects_exact_optimal_action"]
    assert tie["agreement_category"] == "different_action_exact_optimal_tie"
    assert tie["reference_action_value_gap"] == 0
    inferior = compare_reference_action(environment, solution, state, 0)
    assert inferior["reference_action_value_gap"] == pytest.approx(1 / 7)
    assert inferior["vi_q_value_of_ppo_action"] == solution.action_values[state][0]
    assert inferior["immediate_disadvantage_vs_vi_action"]


def test_comparison_is_reproducible_and_does_not_mutate_reference():
    environment = DeterministicReferenceEnvironment()
    environment.reset(seed=9)
    episode = environment.episode
    random_state = deepcopy(environment.np_random.bit_generator.state)
    solution = value_iteration(environment)
    first = compare_reference_action(environment, solution, episode, 4)
    assert first == compare_reference_action(environment, solution, episode, 4)
    assert environment.episode is episode
    assert environment.np_random.bit_generator.state == random_state
    histories = reference_predecessor_histories(environment)
    assert histories
    assert all(environment._action_config.actions[action] == ANTIBIOTICS[action]
               for actions in histories.values() for action in actions)


def test_infeasible_and_terminal_decisions_are_not_compared():
    environment = DeterministicReferenceEnvironment()
    solution = value_iteration(environment)
    state = EpisodeState(ResistanceState((1, 0, 0, 0, 0, 0, 0)))
    with pytest.raises(ValueError, match="infeasible"):
        compare_reference_action(environment, solution, state, 0)
    with pytest.raises(ValueError, match="Terminal"):
        compare_reference_action(environment, solution, EpisodeState(ResistanceState((1,) * 7)), 0)


def test_reference_decision_reuses_canonical_trace_schema_from_mid_horizon():
    environment = DeterministicReferenceEnvironment()
    state = EpisodeState(ResistanceState((0,) * 7), 3)
    next_state, reward, terminal, info = environment.transition(state, 4)
    episode = {
        "episode_id": 0, "environment_seed": None, "initial_resistance_profile": [0] * 7,
        "steps": [{
            "observation": reference_observation(state, 2).tolist(), "action": 4,
            "next_observation": reference_observation(next_state, 4).tolist(),
            "reward": reward, "info": info,
        }],
    }
    trace = build_decision_trace(
        episode, 0, [0, 0, 0, 0, 1, 0, 0], environment,
        case_id="reference_example", training_seed=1000, checkpoint_identifier="test-model",
        initial_treatment_step=3,
    )
    assert trace["step"] == 3
    assert trace["reward"] == reward
    assert trace["transition_info"]["scenario_id"] == "REF_DETERMINISTIC_FIRST_SUPPORTED"
    assert environment.episode is None


def test_case_classification_keeps_neither_optimal_separate_from_q_ordering():
    diagnostic = {"vi_q_value_of_ppo_action": -2.0, "vi_optimal_state_value": -1.0}
    assert benchmark.classify_ciprofloxacin_reference(diagnostic, -1.5) == "C_neither_action_exact_optimal"
    assert benchmark.classify_ciprofloxacin_reference(diagnostic, -1.0) == "A_ciprofloxacin_higher_exact_reference_q"
    diagnostic["vi_q_value_of_ppo_action"] = -1.0
    assert benchmark.classify_ciprofloxacin_reference(diagnostic, -1.0) == "B_ppo_action_equal_or_higher_exact_reference_q"


def test_benchmark_is_reproducible_covers_states_and_preserves_sources(tmp_path, monkeypatch):
    config = PPOConfig()
    model_dir = tmp_path / "model"
    matched_dir = tmp_path / "matched"
    traces_dir = tmp_path / "traces"
    for directory in (model_dir, matched_dir, traces_dir):
        directory.mkdir()
    checkpoint = model_dir / "final_model.zip"
    checkpoint.write_bytes(b"immutable test checkpoint")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    config_path = model_dir / "config.json"
    config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    (model_dir / "environment_manifest.json").write_text(json.dumps(environment_manifest(config)), encoding="utf-8")
    (matched_dir / "config.json").write_text(json.dumps({"scenario_id": config.scenario_id, "horizon": 8}), encoding="utf-8")
    (traces_dir / "summary.json").write_text(json.dumps({"model_provenance": [{
        "training_seed": 1000, "checkpoint": str(checkpoint), "checkpoint_sha256": checksum,
    }]}), encoding="utf-8")
    observation = reference_observation(EpisodeState(ResistanceState((0, 0, 1, 0, 0, 1, 0)), 1), 6)
    (traces_dir / "ciprofloxacin_immediate_advantage.json").write_text(json.dumps([{
        "decision": {"training_seed": 1000, "case_id": "test-case", "step": 1,
                     "observation": observation.tolist(), "selected_action": 4, "reward": -2 / 7},
        "ciprofloxacin_alternative": {"immediate_reward": -1 / 7},
    }]), encoding="utf-8")
    environment = make_training_environment(config)
    model = SimpleNamespace(gamma=1.0, action_space=environment.action_space, observation_space=environment.observation_space)
    environment.close()
    monkeypatch.setattr(benchmark, "load_ppo_model", lambda *args, **kwargs: model)

    def deterministic_policy(model, observation):
        feasible = np.flatnonzero(observation[:7] == 0)
        action = 4 if 4 in feasible else int(feasible[0])
        probabilities = [float(index == action) for index in range(7)]
        return action, probabilities, 0.0

    monkeypatch.setattr(benchmark, "inspect_policy", deterministic_policy)
    monkeypatch.setattr(benchmark, "generate_reference_benchmark_plots", lambda *args: [])
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first = benchmark.run_reference_benchmark(matched_dir, traces_dir, config_path, first_dir)
    second = benchmark.run_reference_benchmark(matched_dir, traces_dir, config_path, second_dir)
    assert first == second
    assert first["state_context_comparison"]["evaluated_observation_contexts"] == 2591
    assert first["terminal_and_missing_history_records"] == 143
    assert first["ciprofloxacin_cases"]["decision_count"] == 1
    for filename in ("raw_state_contexts.csv", "deterministic_reference_rollouts.json", "example_decisions.json", "report.md"):
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checksum
    assert not first["examples_present"]["immediate_disadvantage_long_horizon_equivalent"]
    with pytest.raises(FileExistsError):
        benchmark.run_reference_benchmark(matched_dir, traces_dir, config_path, first_dir)
    checkpoint.write_bytes(b"changed test checkpoint")
    with pytest.raises(ValueError, match="Checkpoint changed"):
        benchmark.run_reference_benchmark(matched_dir, traces_dir, config_path, tmp_path / "changed")