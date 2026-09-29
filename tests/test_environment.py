import numpy as np
import pytest

from simulation.episode import EpisodeState
from simulation.environment import AntibioticEnvironment


class StubEpisodeProgression:
    def step(self, episode, action, seed=None):
        return episode.advance(episode.resistance_state)


def test_environment_has_correct_action_space():
    environment = AntibioticEnvironment()

    assert environment.action_space.n == 7


def test_environment_has_correct_observation_space():
    environment = AntibioticEnvironment()

    assert environment.observation_space.shape == (15,)


def test_reset_returns_initial_observation():
    environment = AntibioticEnvironment()

    observation, info = environment.reset(seed=42)

    assert observation.shape == (15,)
    assert observation.dtype == np.float32
    assert info == {}


def test_initial_observation_is_fully_susceptible():
    environment = AntibioticEnvironment()

    observation, _ = environment.reset(seed=42)

    susceptibility = observation[:7]
    last_action = observation[7:14]
    treatment_step = observation[14]

    assert np.array_equal(
        susceptibility,
        np.zeros(7),
    )

    assert np.array_equal(
        last_action,
        np.zeros(7),
    )

    assert treatment_step == 0


def test_step_returns_gymnasium_transition():
    environment = AntibioticEnvironment(
        episode_progression=StubEpisodeProgression()
    )

    environment.reset(seed=42)

    observation, reward, terminated, truncated, info = (
        environment.step(0)
    )

    assert observation.shape == (15,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_step_records_selected_action():
    environment = AntibioticEnvironment(
        episode_progression=StubEpisodeProgression()
    )

    environment.reset(seed=42)

    observation, _, _, _, info = environment.step(2)

    assert np.array_equal(
        observation[7:14],
        np.array([0, 0, 1, 0, 0, 0, 0]),
    )

    assert info["antibiotic"] == "FOSFOMYCIN"


def test_step_increments_treatment_step():
    environment = AntibioticEnvironment(
        episode_progression=StubEpisodeProgression()
    )

    environment.reset(seed=42)

    observation, _, _, _, _ = environment.step(0)

    assert observation[14] == 1


def test_step_before_reset_is_rejected():
    environment = AntibioticEnvironment()

    with pytest.raises(RuntimeError):
        environment.step(0)


def test_invalid_action_is_rejected():
    environment = AntibioticEnvironment()

    environment.reset(seed=42)

    with pytest.raises(Exception):
        environment.step(7)