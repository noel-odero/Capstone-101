import pytest

from simulation.observation import (
    OBSERVATION_VECTOR_SIZE,
    Observation,
    decode_observation,
    encode_observation,
)


@pytest.mark.parametrize("profile,action,step", [
    ((0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0), 0),
    ((0, 1, 0, -1, 0, 1, 0), (1, 0, 0, 0, 0, 0, 0), 3),
])
def test_observation_codec_preserves_canonical_vector(profile, action, step):
    observation = Observation(profile, action, step)
    vector = encode_observation(observation)

    assert vector == profile + action + (step,)
    assert vector == observation.to_vector()
    assert len(vector) == OBSERVATION_VECTOR_SIZE == 15
    assert decode_observation(vector) == observation


@pytest.mark.parametrize("profile,action,step", [
    ((0, 1, 2, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0), 0),
    ((0, 1, 0), (0, 0, 0, 0, 0, 0, 0), 0),
    ((0, 0, 0, 0, 0, 0, 0), (1, 0), 0),
    ((0, 0, 0, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0), 0),
    ((0, 0, 0, 0, 0, 0, 0), (2, 0, 0, 0, 0, 0, 0), 0),
    ((0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0), -1),
])
def test_invalid_observation_is_rejected(profile, action, step):
    with pytest.raises(ValueError):
        Observation(profile, action, step)
    with pytest.raises(ValueError):
        decode_observation(profile + action + (step,))


@pytest.mark.parametrize("vector", [(), (0, 1, 0), (0,) * 16])
def test_decoder_rejects_wrong_vector_size(vector):
    with pytest.raises(ValueError):
        decode_observation(vector)
