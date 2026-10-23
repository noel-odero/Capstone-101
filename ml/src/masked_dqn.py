"""DQN for the simulator's susceptible-only action space (SB3 2.9).

The mask is derived from each raw observation, including replay next states.
Warm-up, epsilon exploration, greedy inference and Bellman targets all use it.
The training path adapts Stable-Baselines3 DQN; see ml/third-party-notices.txt.
"""
from __future__ import annotations

import numpy as np
import torch
from torch.nn import functional as F
from stable_baselines3 import DQN

from simulation.observation import OBSERVATION_VECTOR_SIZE
from simulation.resistance_state import ANTIBIOTICS


def susceptible_mask(observations: torch.Tensor) -> torch.Tensor:
    if observations.ndim != 2 or observations.shape[1] != OBSERVATION_VECTOR_SIZE:
        raise ValueError("Masked DQN requires batches of 15-value observations.")
    if not torch.isfinite(observations).all():
        raise ValueError("DQN observations must be finite.")
    profiles = observations[:, :len(ANTIBIOTICS)]
    if not ((profiles == 0) | (profiles == 1)).all():
        raise ValueError("DQN requires binary resistance profiles.")
    return profiles == 0


def masked_bootstrap(
    next_q_values: torch.Tensor, next_observations: torch.Tensor, dones: torch.Tensor,
) -> torch.Tensor:
    """Return legal next-state maxima, with exactly zero bootstrap at termination."""
    mask = susceptible_mask(next_observations)
    terminal = dones.reshape(-1).bool()
    if next_q_values.shape != mask.shape or terminal.shape != mask.shape[:1]:
        raise ValueError("Q-values, next observations and terminal flags must align.")
    if not torch.isfinite(next_q_values).all():
        raise ValueError("DQN produced nonfinite next-state Q-values.")
    if ((~mask.any(dim=1)) & ~terminal).any():
        raise ValueError("A nonterminal replay state has no susceptible action.")
    maxima = next_q_values.masked_fill(~mask, -torch.inf).max(dim=1).values
    # Avoid 0 * -inf for all-resistant terminal states.
    return torch.where(terminal, torch.zeros_like(maxima), maxima).reshape(-1, 1)


class MaskedDQN(DQN):
    """Vanilla DQN with observation-derived action masking, not Double DQN."""

    def _setup_model(self) -> None:
        super()._setup_model()
        if self.observation_space.shape != (OBSERVATION_VECTOR_SIZE,) or (
            self.action_space.n != len(ANTIBIOTICS) or self.action_space.start != 0
        ):
            raise ValueError("MaskedDQN supports only the canonical simulator spaces.")
        if self.gamma != 1.0:
            raise ValueError("The resistance-burden objective requires gamma=1.0.")

    def predict(self, observation, state=None, episode_start=None, deterministic=False):
        self.policy.set_training_mode(False)
        observations, vectorized = self.policy.obs_to_tensor(observation)
        mask = susceptible_mask(observations)
        if not mask.any(dim=1).all():
            raise ValueError("A terminal observation has no susceptible action.")
        with torch.no_grad():
            q_values = self.q_net(observations)
            if not torch.isfinite(q_values).all():
                raise ValueError("DQN produced nonfinite Q-values.")
            actions = q_values.masked_fill(~mask, -torch.inf).argmax(dim=1).cpu().numpy()
        if not deterministic:
            masks = mask.cpu().numpy()
            for index in range(len(actions)):
                if np.random.random() < self.exploration_rate:
                    actions[index] = np.random.choice(np.flatnonzero(masks[index]))
        return (actions if vectorized else actions.reshape(())), state

    def _sample_action(self, learning_starts, action_noise=None, n_envs=1):
        if self._last_obs is None:
            raise RuntimeError("Training must reset the environment before sampling.")
        if self.num_timesteps < learning_starts:
            observations, _ = self.policy.obs_to_tensor(self._last_obs)
            masks = susceptible_mask(observations).cpu().numpy()
            if not masks.any(axis=1).all():
                raise ValueError("A terminal observation has no susceptible action.")
            actions = np.asarray([np.random.choice(np.flatnonzero(mask)) for mask in masks])
        else:
            actions, _ = self.predict(self._last_obs, deterministic=False)
        return actions, actions.copy()

    def train(self, gradient_steps: int, batch_size: int = 100) -> None:
        if self._vec_normalize_env is not None:
            raise ValueError("Observation normalization would invalidate the resistance mask.")
        self.policy.set_training_mode(True)
        self._update_learning_rate(self.policy.optimizer)
        losses = []
        for _ in range(gradient_steps):
            replay = self.replay_buffer.sample(batch_size, env=None)
            with torch.no_grad():
                next_values = masked_bootstrap(
                    self.q_net_target(replay.next_observations),
                    replay.next_observations, replay.dones,
                )
                discounts = replay.discounts if replay.discounts is not None else self.gamma
                targets = replay.rewards + discounts * next_values
            mask = susceptible_mask(replay.observations)
            if not mask.gather(1, replay.actions.long()).all():
                raise ValueError("Replay contains an infeasible action.")
            current = self.q_net(replay.observations).gather(1, replay.actions.long())
            loss = F.smooth_l1_loss(current, targets)
            if not torch.isfinite(loss):
                raise ValueError("DQN training produced a nonfinite loss.")
            self.policy.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            self.policy.optimizer.step()
            losses.append(loss.item())
        self._n_updates += gradient_steps
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        if losses:
            self.logger.record("train/loss", np.mean(losses))
