from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ml.src.evaluation_runner import EpisodeResult, EvaluationResult, StepResult, run_evaluation
from ml.src.metrics import calculate_episode_metrics, calculate_metrics
from ml.src.greedy_policy import GreedyPolicy
from ml.src.random_policy import RandomPolicy
from simulation.environment import AntibioticEnvironment


SCENARIO_ID = "TEST_SCENARIO"


def observation(profile, step=0):
    return tuple(profile) + (0,) * 7 + (step,)


def trajectory(profiles, effectiveness, rewards, *, episode_id=0, truncated=False):
    steps = tuple(
        StepResult(
            observation=observation(profiles[index], index),
            action=0,
            next_observation=observation(profiles[index + 1], index + 1),
            reward=reward,
            terminated=index == len(rewards) - 1 and not truncated,
            truncated=index == len(rewards) - 1 and truncated,
            info={
                "effective": effectiveness[index],
                "scenario_id": SCENARIO_ID,
                "transition_status": "deliberately_uninformative_label",
                "source_ids": ["TEST_SOURCE"],
            },
        )
        for index, reward in enumerate(rewards)
    )
    return EpisodeResult(
        episode_id=episode_id,
        environment_seed=42 + episode_id,
        policy_seed=18 + episode_id,
        policy_name="test.policy",
        initial_resistance_profile=tuple(profiles[0]),
        final_resistance_profile=tuple(profiles[-1]),
        initial_observation=observation(profiles[0]),
        reset_info={},
        steps=steps,
        terminated=not truncated,
        truncated=truncated,
        termination_reason="truncated" if truncated else "maximum_horizon",
    )


def evaluation(*episodes):
    return EvaluationResult(
        scenario_id=SCENARIO_ID, horizon=8,
        reward_specification={
            "objective": "normalized_resistance_burden",
            "normalization": 7,
            "terminal_convention": "all_resistant_state_persists_to_horizon",
        },
        episodes=tuple(episodes),
    )


def test_manually_calculated_mixed_trajectory():
    profiles = [(0,) * 7, (0, 1, 1, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0), (1, 0, 0, 0, 0, 0, 0)]
    episode = trajectory(profiles, [True, True, False], [0.4, 0.9, -0.6])
    metrics = calculate_episode_metrics(episode, scenario_id=SCENARIO_ID)

    assert metrics.treatment_steps == metrics.transitions == 3
    assert metrics.effective_steps == 2
    assert metrics.treatment_effectiveness_rate == pytest.approx(2 / 3)
    assert metrics.resistance_emergence_events == 1
    assert metrics.resistance_emergence_rate == pytest.approx(1 / 3)
    assert metrics.future_effective_antibiotics == 6
    assert metrics.change_in_future_effective_antibiotics == -1
    assert metrics.cumulative_antibiotic_exposure == 3
    assert metrics.cumulative_reward == pytest.approx(0.7)
    assert metrics.policy_name == episode.policy_name
    assert metrics.scenario_id == SCENARIO_ID
    assert metrics.environment_seed == episode.environment_seed
    assert metrics.terminated and not metrics.truncated


def test_collateral_sensitivity_improves_future_options():
    episode = trajectory([(1, 1, 0, 0, 0, 0, 0), (1, 0, 0, 0, 0, 0, 0)], [False], [-0.6])
    metrics = calculate_episode_metrics(episode, scenario_id=SCENARIO_ID)
    assert metrics.resistance_emergence_rate == 0.0
    assert metrics.treatment_effectiveness_rate == 0.0
    assert metrics.future_effective_antibiotics == 6
    assert metrics.change_in_future_effective_antibiotics == 1


def test_unchanged_transition_counts_in_rate_denominator_and_exposure():
    metrics = calculate_episode_metrics(
        trajectory([(0,) * 7, (0,) * 7], [True], [0.9]), scenario_id=SCENARIO_ID,
    )
    assert metrics.transitions == 1
    assert metrics.resistance_emergence_rate == 0.0
    assert metrics.treatment_effectiveness_rate == 1.0
    assert metrics.change_in_future_effective_antibiotics == 0
    assert metrics.cumulative_antibiotic_exposure == 1


def test_initially_terminal_episode_rates_are_undefined():
    episode = replace(trajectory([(1,) * 7], [], []), termination_reason="no_effective_antibiotic")
    metrics = calculate_episode_metrics(episode, scenario_id=SCENARIO_ID)
    assert metrics.treatment_effectiveness_rate is None
    assert metrics.resistance_emergence_rate is None
    assert metrics.future_effective_antibiotics == 0
    assert metrics.change_in_future_effective_antibiotics == 0
    assert metrics.cumulative_antibiotic_exposure == metrics.transitions == 0
    assert metrics.cumulative_reward == 0.0
    assert metrics.termination_reason == "no_effective_antibiotic"


def test_unequal_lengths_keep_pooled_and_mean_rates_distinct():
    long_episode = trajectory(
        [(0,) * 7, (0, 1, 0, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0)],
        [True, True, False], [0.4, 0.4, -1.1],
    )
    short_episode = trajectory([(1,) * 7, (1,) * 7], [False], [-1.1], episode_id=1, truncated=True)
    zero_episode = replace(trajectory([(1,) * 7], [], [], episode_id=2), termination_reason="no_effective_antibiotic")
    result = calculate_metrics(evaluation(long_episode, short_episode, zero_episode))
    summary = result.summary

    assert summary.episode_count == 3
    assert summary.zero_step_episode_count == 1
    assert summary.total_treatment_steps == summary.total_transitions == 4
    assert summary.pooled_treatment_effectiveness_rate == 0.5
    assert summary.mean_episode_treatment_effectiveness_rate == pytest.approx(1 / 3)
    assert summary.pooled_resistance_emergence_rate == 0.5
    assert summary.mean_episode_resistance_emergence_rate == pytest.approx(1 / 3)
    assert summary.treatment_rate_episode_count == summary.emergence_rate_episode_count == 2
    assert summary.mean_future_effective_antibiotics == pytest.approx(5 / 3)
    assert summary.mean_change_in_future_effective_antibiotics == pytest.approx(-2 / 3)
    assert summary.total_cumulative_antibiotic_exposure == 4
    assert summary.mean_cumulative_antibiotic_exposure == pytest.approx(4 / 3)
    assert summary.total_cumulative_reward == pytest.approx(-1.4)
    assert summary.mean_cumulative_reward == pytest.approx(-1.4 / 3)
    assert summary.terminated_episode_count == 2
    assert summary.truncated_episode_count == 1
    assert summary.termination_reason_counts == {
        "maximum_horizon": 1, "truncated": 1, "no_effective_antibiotic": 1,
    }


def test_all_zero_step_batch_and_empty_batch():
    zero = trajectory([(1,) * 7], [], [])
    summary = calculate_metrics(evaluation(zero)).summary
    assert summary.pooled_treatment_effectiveness_rate is None
    assert summary.mean_episode_resistance_emergence_rate is None
    assert summary.treatment_rate_episode_count == 0
    assert summary.mean_future_effective_antibiotics == 0.0
    assert summary.mean_cumulative_reward == 0.0

    empty = calculate_metrics(evaluation())
    assert empty.policy_name is None
    assert empty.summary.episode_count == 0
    assert empty.summary.pooled_treatment_effectiveness_rate is None
    assert empty.summary.mean_future_effective_antibiotics is None
    assert empty.summary.mean_cumulative_reward is None
    assert empty.summary.total_cumulative_reward == 0.0
    assert empty.summary.termination_reason_counts == {}


def test_truncation_is_preserved_not_reinterpreted_as_termination():
    episode = trajectory([(0,) * 7, (0,) * 7], [True], [0.9], truncated=True)
    result = calculate_metrics(evaluation(episode))
    assert result.episodes[0].truncated and not result.episodes[0].terminated
    assert result.summary.terminated_episode_count == 0
    assert result.summary.truncated_episode_count == 1


def test_metrics_and_export_do_not_mutate_input():
    source = evaluation(trajectory([(0,) * 7, (0,) * 7], [True], [0.9]))
    before = deepcopy(source)
    result = calculate_metrics(source)
    exported = result.to_dict()
    json.dumps(exported, allow_nan=False)
    exported["reward_specification"]["normalization"] = 99
    exported["episodes"][0]["policy_name"] = "changed"
    result.reward_specification["normalization"] = 2
    assert source == before
    assert result.episodes[0].policy_name == "test.policy"
    null_export = calculate_metrics(evaluation(trajectory([(1,) * 7], [], []))).to_dict()
    assert json.loads(json.dumps(null_export))["episodes"][0]["treatment_effectiveness_rate"] is None


@pytest.mark.parametrize("value", [-1, 2, float("nan")])
def test_rejects_unknown_or_invalid_observation_profiles(value):
    episode = trajectory([(0,) * 7, (0,) * 7], [True], [0.9])
    step = replace(episode.steps[0], next_observation=(value,) + episode.steps[0].next_observation[1:])
    with pytest.raises(ValueError):
        calculate_episode_metrics(replace(episode, steps=(step,)), scenario_id=SCENARIO_ID)


@pytest.mark.parametrize("info", [{}, {"effective": "yes"}, {"effective": True, "scenario_id": "OTHER"}])
def test_rejects_missing_metadata_or_scenario_mismatch(info):
    episode = trajectory([(0,) * 7, (0,) * 7], [True], [0.9])
    with pytest.raises(ValueError):
        calculate_episode_metrics(
            replace(episode, steps=(replace(episode.steps[0], info=info),)),
            scenario_id=SCENARIO_ID,
        )


def test_rejects_discontinuous_or_inconsistent_endpoints():
    episode = trajectory([(0,) * 7, (0,) * 7], [True], [0.9])
    for corrupted in (
        replace(episode, initial_observation=observation((1,) * 7)),
        replace(episode, final_resistance_profile=(1,) * 7),
        replace(episode, steps=(replace(episode.steps[0], observation=observation((1,) * 7)),)),
    ):
        with pytest.raises(ValueError):
            calculate_episode_metrics(corrupted, scenario_id=SCENARIO_ID)


@pytest.mark.parametrize("reward", [float("nan"), float("inf")])
def test_rejects_nonfinite_rewards(reward):
    episode = trajectory([(0,) * 7, (0,) * 7], [True], [reward])
    with pytest.raises(ValueError, match="finite"):
        calculate_episode_metrics(episode, scenario_id=SCENARIO_ID)


def test_rejects_mixed_policy_aggregation_and_missing_scenario():
    episode = trajectory([(0,) * 7], [], [])
    with pytest.raises(ValueError, match="mixed policy"):
        calculate_metrics(evaluation(episode, replace(episode, policy_name="other")))
    with pytest.raises(ValueError, match="scenario_id"):
        calculate_metrics(replace(evaluation(), scenario_id=""))


@pytest.mark.parametrize("policy", [RandomPolicy, GreedyPolicy])
def test_real_runner_records_are_compatible_without_modification(policy):
    source = run_evaluation(AntibioticEnvironment(max_steps=2), policy, 2, environment_seed=42, policy_seed=18)
    result = calculate_metrics(source)
    assert result.scenario_id == source.scenario_id
    assert result.policy_name.endswith(policy.__name__)
    assert result.horizon == source.horizon
    for episode, metrics in zip(source.episodes, result.episodes):
        assert metrics.cumulative_reward == episode.cumulative_reward
        assert metrics.cumulative_antibiotic_exposure == episode.treatment_step_count
        assert metrics.future_effective_antibiotics == episode.final_resistance_profile.count(0)
    json.dumps(result.to_dict(), allow_nan=False)