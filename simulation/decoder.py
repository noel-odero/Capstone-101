from simulation.encoder import OBSERVATION_VECTOR_SIZE
from simulation.observation import Observation


def decode_observation(vector: tuple[int, ...]) -> Observation:
    if len(vector) != OBSERVATION_VECTOR_SIZE:
        raise ValueError(
            f"Expected observation vector of size "
            f"{OBSERVATION_VECTOR_SIZE}, got {len(vector)}."
        )

    susceptibility = vector[:7]
    last_action = vector[7:14]
    treatment_step = vector[14]

    return Observation(
        susceptibility=susceptibility,
        last_action=last_action,
        treatment_step=treatment_step,
    )
