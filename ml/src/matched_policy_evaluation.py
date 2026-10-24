"""Policy adapter and burden calculation shared by inference and the three-strategy benchmark."""
import numpy as np
from gymnasium.spaces import Discrete
from sb3_contrib import MaskablePPO

from simulation.resistance_state import ANTIBIOTICS


class MaskablePPOObservationPolicy:
    """Adapt a loaded MaskablePPO model to the observation-policy API."""

    def __init__(self, action_space: Discrete, model: MaskablePPO, seed: int | None = None):
        if not isinstance(action_space, Discrete):
            raise TypeError("PPO observation policy requires a Discrete action space.")
        if action_space.start != 0 or action_space.n != len(ANTIBIOTICS):
            raise ValueError("PPO action space must match the canonical seven actions.")
        self.action_space = action_space
        self.model = model

    def select_action(self, observation: np.ndarray) -> int:
        observation = np.asarray(observation, dtype=np.float32)
        if observation.shape != (15,) or not np.isfinite(observation).all():
            raise ValueError("PPO requires a finite 15-value observation.")
        action_mask = observation[:len(ANTIBIOTICS)] == 0
        if not action_mask.any():
            raise ValueError("A terminal all-resistant observation has no feasible action.")
        action, _ = self.model.predict(
            observation,
            deterministic=True,
            action_masks=action_mask,
        )
        action = int(np.asarray(action).reshape(-1)[0])
        if not self.action_space.contains(action) or not action_mask[action]:
            raise RuntimeError("MaskablePPO selected an infeasible action.")
        return action


def _episode_burden(episode) -> float:
    return -episode.cumulative_reward
