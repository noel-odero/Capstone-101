import random

from gymnasium.spaces import Discrete


class RandomPolicy:
    """Uniformly select actions without using susceptibility or treatment history.

    The policy owns its RNG; its seed does not seed or mutate the environment.
    Recreate it with the same seed to replay the same action sequence.
    """

    def __init__(self, action_space: Discrete, seed: int | None = None):
        if not isinstance(action_space, Discrete):
            raise TypeError("RandomPolicy requires a Discrete action space.")

        self.action_space = action_space
        self._random = random.Random(seed)

    def select_action(self, observation: object = None) -> int:
        """Return a Python integer action, independently of the observation."""
        return self._random.randrange(
            int(self.action_space.start),
            int(self.action_space.start + self.action_space.n),
        )