import random


class Randomness:
    def __init__(self, seed: int | None = None):
        self.seed = seed
        self._random = random.Random(seed)

    def choice(self, values):
        if not values:
            raise ValueError("Cannot choose from an empty sequence.")

        return self._random.choice(values)