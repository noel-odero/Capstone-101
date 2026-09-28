from simulation.observation import Observation


OBSERVATION_VECTOR_SIZE = 15


def encode_observation(observation: Observation) -> tuple[int, ...]:
    vector = observation.to_vector()

    if len(vector) != OBSERVATION_VECTOR_SIZE:
        raise ValueError(
            f"Expected observation vector of size "
            f"{OBSERVATION_VECTOR_SIZE}, got {len(vector)}."
        )

    return vector
