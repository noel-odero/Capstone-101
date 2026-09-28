import pytest

from simulation.encoder import (
    OBSERVATION_VECTOR_SIZE,
    encode_observation,
)
from simulation.observation import Observation


def test_valid_observation_produces_fixed_size_vector():
    observation = Observation(
        susceptibility=(0, 1, 0, -1, 0, 1, 0),
        last_action=(1, 0, 0, 0, 0, 0, 0),
        treatment_step=3,
    )

    vector = encode_observation(observation)

    assert len(vector) == OBSERVATION_VECTOR_SIZE
    assert len(vector) == 15


def test_encoding_is_deterministic():
    observation = Observation(
        susceptibility=(0, 1, 0, -1, 0, 1, 0),
        last_action=(1, 0, 0, 0, 0, 0, 0),
        treatment_step=3,
    )

    assert encode_observation(observation) == encode_observation(observation)


def test_encoding_preserves_observation_values():
    observation = Observation(
        susceptibility=(0, 1, 0, -1, 0, 1, 0),
        last_action=(1, 0, 0, 0, 0, 0, 0),
        treatment_step=3,
    )

    assert encode_observation(observation) == (
        0, 1, 0, -1, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0,
        3,
    )


def test_vector_size_is_documented():
    assert OBSERVATION_VECTOR_SIZE == 15
