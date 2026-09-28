import pytest

from simulation.decoder import decode_observation
from simulation.encoder import encode_observation
from simulation.observation import Observation


def test_valid_vector_decodes_to_observation():
    vector = (
        0, 1, 0, -1, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0,
        3,
    )

    observation = decode_observation(vector)

    assert observation == Observation(
        susceptibility=(0, 1, 0, -1, 0, 1, 0),
        last_action=(1, 0, 0, 0, 0, 0, 0),
        treatment_step=3,
    )


def test_decoding_is_deterministic():
    vector = (
        0, 1, 0, -1, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0,
        3,
    )

    assert decode_observation(vector) == decode_observation(vector)


def test_encoding_and_decoding_are_reversible():
    observation = Observation(
        susceptibility=(0, 1, 0, -1, 0, 1, 0),
        last_action=(1, 0, 0, 0, 0, 0, 0),
        treatment_step=3,
    )

    decoded = decode_observation(
        encode_observation(observation)
    )

    assert decoded == observation


def test_wrong_vector_size_is_rejected():
    with pytest.raises(ValueError):
        decode_observation((0, 1, 0))


def test_invalid_susceptibility_is_rejected():
    vector = (
        0, 1, 2, -1, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0,
        3,
    )

    with pytest.raises(ValueError):
        decode_observation(vector)


def test_invalid_last_action_is_rejected():
    vector = (
        0, 1, 0, -1, 0, 1, 0,
        1, 1, 0, 0, 0, 0, 0,
        3,
    )

    with pytest.raises(ValueError):
        decode_observation(vector)


def test_negative_treatment_step_is_rejected():
    vector = (
        0, 1, 0, -1, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0,
        -1,
    )

    with pytest.raises(ValueError):
        decode_observation(vector)
