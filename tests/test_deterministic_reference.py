import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from simulation.deterministic_reference import (
    DeterministicReferenceEnvironment,
    DeterministicTransitionModel,
    REFERENCE_SCENARIO_ID,
)
from simulation.episode import EpisodeState
from simulation.resistance_state import ResistanceState


@pytest.mark.parametrize(
    ("resistance", "action", "expected", "outcome"),
    [
        ((0, 0, 0, 0, 0, 0, 0), 0, (0, 0, 0, 0, 0, 0, 1), "cross_resistance"),
        ((0, 0, 0, 0, 0, 0, 1), 0, (0, 0, 0, 0, 0, 1, 1), "cross_resistance"),
        ((0, 0, 1, 1, 1, 1, 1), 0, (0, 0, 0, 1, 1, 1, 1), "collateral_sensitivity"),
        ((0, 1, 0, 0, 0, 0, 0), 3, (0, 1, 0, 0, 0, 0, 0), "neutral"),
        ((0, 0, 0, 0, 0, 0, 0), 2, (0, 0, 0, 0, 0, 0, 0), "unsupported_no_candidate"),
    ],
)
def test_expected_reference_transitions(resistance, action, expected, outcome):
    model = DeterministicTransitionModel()
    state = ResistanceState(resistance)
    results = [model.step(state, action, seed=seed) for seed in (None, 1, 42, 100)]

    assert all(result == results[0] for result in results)
    assert results[0].next_state.resistance == expected
    assert results[0].outcome == outcome
    assert state.resistance == resistance


def test_full_planning_table_is_small_deterministic_closed_and_pure():
    environment = DeterministicReferenceEnvironment()
    states = environment.states()
    state_set = set(states)
    assert len(states) == len(state_set) == 128 * 9
    assert environment.episode is None

    for state in states:
        for action in range(7):
            result = environment.transition(state, action)
            assert result == environment.transition(state, action)
            next_state, reward, terminated, info = result
            assert next_state in state_set
            assert isinstance(reward, float)
            assert terminated == environment.is_terminal(next_state)
            assert info["transition_probability"] == 1.0
            assert info["scenario_id"] == REFERENCE_SCENARIO_ID
            if environment.is_terminal(state):
                assert next_state == state
                assert reward == 0.0
            else:
                assert next_state.treatment_step == state.treatment_step + 1

    assert environment.episode is None


def test_known_reward_and_observation_semantics():
    environment = DeterministicReferenceEnvironment()
    observation, _ = environment.reset(seed=1)
    assert np.array_equal(observation[:7], np.zeros(7))
    observation, reward, terminated, truncated, info = environment.step(0)

    assert reward == pytest.approx(0.4)
    assert np.array_equal(observation[:7], [0, 0, 0, 0, 0, 0, 1])
    assert np.array_equal(observation[7:14], [1, 0, 0, 0, 0, 0, 0])
    assert observation[-1] == 1
    assert not terminated and not truncated
    assert info["source_ids"] == ["POD2018"]


def test_episode_identical_across_seeds_and_horizon_observations_valid():
    trajectories = []
    for seed in (1, 18, 42):
        environment = DeterministicReferenceEnvironment(max_steps=3)
        observation, _ = environment.reset(seed=seed)
        assert environment.observation_space.contains(observation)
        trajectory = []
        for step in range(1, 4):
            observation, reward, terminated, truncated, info = environment.step(2)
            assert environment.observation_space.contains(observation)
            assert terminated is (step == 3)
            trajectory.append((observation.tolist(), reward, terminated, truncated, info))
        with pytest.raises(RuntimeError, match="terminal"):
            environment.step(2)
        trajectories.append(trajectory)
        environment.close()
    assert trajectories[0] == trajectories[1] == trajectories[2]


def test_all_resistant_state_is_absorbing_for_planning():
    environment = DeterministicReferenceEnvironment()
    state = EpisodeState(ResistanceState((1,) * 7))
    next_state, reward, terminated, _ = environment.transition(state, 0)
    assert next_state == state
    assert reward == 0.0 and terminated


@pytest.mark.parametrize(("action", "exception"), [(0.9, TypeError), (True, TypeError), (-1, ValueError), (7, ValueError)])
def test_invalid_actions_rejected(action, exception):
    environment = DeterministicReferenceEnvironment()
    state = EpisodeState(ResistanceState((0,) * 7))
    with pytest.raises(exception):
        environment.transition(state, action)


def test_invalid_horizon_and_planning_state_rejected():
    with pytest.raises(ValueError):
        DeterministicReferenceEnvironment(max_steps=0)
    with pytest.raises(TypeError):
        DeterministicReferenceEnvironment(max_steps=1.5)
    environment = DeterministicReferenceEnvironment()
    with pytest.raises(ValueError):
        environment.transition(EpisodeState(ResistanceState((0,) * 7), 9), 0)
    with pytest.raises(RuntimeError, match="reset"):
        environment.step(0)


def test_custom_initial_state_and_numpy_action():
    environment = DeterministicReferenceEnvironment()
    observation, _ = environment.reset(options={"initial_resistance_state": (1, 0, 1, 0, 0, 0, 0)})
    assert np.array_equal(observation[:7], [1, 0, 1, 0, 0, 0, 0])
    environment.step(np.int64(2))
    with pytest.raises(ValueError):
        environment.reset(options={"initial_resistance_state": (0, 1)})


def test_gymnasium_interface():
    check_env(DeterministicReferenceEnvironment(), skip_render_check=True)