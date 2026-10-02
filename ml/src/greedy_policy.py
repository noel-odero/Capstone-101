import random
from collections.abc import Sequence

from gymnasium.spaces import Discrete

from simulation.decoder import decode_observation
from simulation.resistance_state import ANTIBIOTICS


class GreedyPolicy:
    """Computational current-susceptibility baseline, not prescribing advice.

    Uniform tie-breaking uses a private RNG independent of the environment.
    Unknown susceptibility is not treated as evidence of effectiveness.
    """

    def __init__(self, action_space: Discrete, seed: int | None = None):
        if not isinstance(action_space, Discrete):
            raise TypeError("GreedyPolicy requires a Discrete action space.")
        if action_space.start != 0 or action_space.n != len(ANTIBIOTICS):
            raise ValueError("Action space must match the canonical seven actions.")

        self._random = random.Random(seed)

    def select_action(self, observation: Sequence[int]) -> int:
        """Choose an observed susceptible action or raise ValueError if none exist.

        Accepts the environment's encoded observation in canonical drug order.
        Treatment history and step do not affect selection.
        """
        decoded = decode_observation(tuple(observation))
        susceptible_actions = tuple(
            action
            for action, susceptibility in enumerate(decoded.susceptibility)
            if susceptibility == 0
        )

        if not susceptible_actions:
            raise ValueError("No antibiotic is marked susceptible in the observation.")

        return self._random.choice(susceptible_actions)