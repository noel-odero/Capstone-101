import pytest

from simulation.observation import Observation


def test_valid_observation():
    observation = Observation(
        susceptibility=(0, -1, 0, 1, -1, 0, 1),
        last_action=(0, 0, 1, 0, 0, 0, 0),
        treatment_step=3,
    )

    assert observation.treatment_step == 3
    assert len(observation.to_vector()) == 15


def test_observation_vector():
    observation = Observation(
        susceptibility=(0, -1, 0, 1, -1, 0, 1),
        last_action=(0, 0, 1, 0, 0, 0, 0),
        treatment_step=3,
    )

    assert observation.to_vector() == (
        0, -1, 0, 1, -1, 0, 1,
        0, 0, 1, 0, 0, 0, 0,
        3,
    )


def test_initial_observation():
    observation = Observation(
        susceptibility=(0, 0, 0, 0, 0, 0, 0),
        last_action=(0, 0, 0, 0, 0, 0, 0),
        treatment_step=0,
    )

    assert len(observation.to_vector()) == 15


def test_invalid_susceptibility_value():
    with pytest.raises(ValueError):
        Observation(
            susceptibility=(0, 1, 2, 0, 0, 0, 0),
            last_action=(0, 0, 0, 0, 0, 0, 0),
            treatment_step=0,
        )


def test_invalid_susceptibility_length():
    with pytest.raises(ValueError):
        Observation(
            susceptibility=(0, 1, 0),
            last_action=(0, 0, 0, 0, 0, 0, 0),
            treatment_step=0,
        )


def test_invalid_last_action_length():
    with pytest.raises(ValueError):
        Observation(
            susceptibility=(0, 0, 0, 0, 0, 0, 0),
            last_action=(1, 0),
            treatment_step=0,
        )


def test_multiple_last_actions():
    with pytest.raises(ValueError):
        Observation(
            susceptibility=(0, 0, 0, 0, 0, 0, 0),
            last_action=(1, 1, 0, 0, 0, 0, 0),
            treatment_step=0,
        )


def test_invalid_treatment_step():
    with pytest.raises(ValueError):
        Observation(
            susceptibility=(0, 0, 0, 0, 0, 0, 0),
            last_action=(0, 0, 0, 0, 0, 0, 0),
            treatment_step=-1,
        )