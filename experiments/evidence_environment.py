"""Shared evidence-restricted environment for offline training and frozen-policy inference."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from functools import cache
from itertools import product
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch

from ml.src.masked_dqn import MaskedDQN, susceptible_mask
from simulation.environment import AntibioticEnvironment
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_function import ResistanceTransitionFunction
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.transition_sampler import REFERENCE_SCENARIO_ID, TransitionSampler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/empirical_interactions.csv"
PROFILES = tuple(product((0, 1), repeat=7))
WEIGHTS = np.array([64, 32, 16, 8, 4, 2, 1])
MASK_RULE = "susceptible_actions_with_candidate_transitions"


@dataclass(frozen=True)
class EvidenceSpec:
    variant: str = "supported"
    horizon: int = 8
    scenario_id: str = REFERENCE_SCENARIO_ID
    supported_only: bool = True
    repetition_penalty: float = 0.0

    def __post_init__(self):
        if isinstance(self.horizon, bool) or not isinstance(self.horizon, int) or self.horizon < 1:
            raise ValueError("Horizon must be a positive integer.")
        if not isinstance(self.supported_only, bool):
            raise ValueError("supported_only must be boolean.")
        if isinstance(self.repetition_penalty, bool) or not np.isfinite(self.repetition_penalty) or self.repetition_penalty < 0:
            raise ValueError("Repetition penalty must be finite and nonnegative.")
        TransitionSampler(self.scenario_id)

    def boundary_cost(self, remaining: int) -> float:
        # Upper bound on every remaining normalized burden + repetition cost.
        # This is an uncertainty cost, NOT a prediction that all drugs become resistant.
        return remaining * (1.0 + self.repetition_penalty)


VARIANTS = {
    "legacy": EvidenceSpec(variant="legacy", supported_only=False),
    "supported": EvidenceSpec(),
    **{f"q{value:03}": EvidenceSpec(variant=f"q{value:03}", scenario_id=f"SENSITIVITY_Q_{value:03}")
       for value in (0, 25, 50, 75, 100)},
    **{f"repeat{value:03}": EvidenceSpec(variant=f"repeat{value:03}", repetition_penalty=value / 100)
       for value in (5, 10)},
}


class EvidenceKernel:
    def __init__(self, spec: EvidenceSpec, data: Path = DATA):
        self.spec = spec
        self.data = Path(data)
        self.generator = CandidateTransitionGenerator(interactions_file=self.data)
        self.sampler = TransitionSampler(spec.scenario_id)
        transition = ResistanceTransitionFunction()
        self.mask_table = np.zeros((128, 7), dtype=bool)
        self.distributions = {}
        self.candidates = {}
        for profile in PROFILES:
            state = ResistanceState(profile)
            for action, bit in enumerate(profile):
                if bit:
                    continue
                sampled = self.sampler.sample(self.generator.generate(state, action), seed=0)
                key = (profile, action)
                self.candidates[key] = sampled.candidates
                self.mask_table[int("".join(map(str, profile)), 2), action] = bool(sampled.candidates) or not spec.supported_only
                distribution = Counter()
                if not sampled.candidates:
                    distribution[profile] = 1.0
                else:
                    for candidate, probability in zip(sampled.candidates, sampled.candidate_probabilities):
                        distribution[transition.apply(state, candidate).resistance] += probability
                    distribution[profile] += sampled.no_transition_probability or 0.0
                if abs(sum(distribution.values()) - 1.0) > 1e-12:
                    raise ValueError("Invalid transition distribution.")
                self.distributions[key] = tuple((after, p) for after, p in distribution.items() if p > 0)
        self.optimal = cache(self._optimal)

    def mask(self, profile) -> np.ndarray:
        return self.mask_table[int(np.asarray(profile, dtype=int) @ WEIGHTS)].copy()

    def actions(self, profile) -> tuple[int, ...]:
        return tuple(int(action) for action in np.flatnonzero(self.mask(profile)))

    def boundary(self, profile) -> bool:
        return not all(profile) and not self.actions(profile)

    @property
    def reward_specification(self):
        return {"objective": "evidence_restricted_normalized_resistance_burden", "normalization": 7,
                "terminal_convention": "all_resistant_state_persists_to_horizon",
                "evidence_boundary": "pessimistic_remaining_cost", "repetition_penalty": self.spec.repetition_penalty}

    def immediate_cost(self, after, action: int, previous: int | None) -> float:
        return sum(after) / 7 + self.spec.repetition_penalty * (action == previous)

    def _optimal(self, profile: tuple, previous: int | None, remaining: int) -> float:
        if remaining == 0:
            return 0.0
        if all(profile):
            return float(remaining)
        actions = self.actions(profile)
        if not actions:
            return self.spec.boundary_cost(remaining)
        return min(self.action_value(profile, action, previous, remaining) for action in actions)

    def action_value(self, profile, action, previous, remaining) -> float:
        return sum(p * (self.immediate_cost(after, action, previous) + self.optimal(after, action, remaining - 1))
                   for after, p in self.distributions[(profile, action)])

    def select_myopic(self, profile, previous) -> int:
        return min(self.actions(profile), key=lambda action: (
            sum(p * self.immediate_cost(after, action, previous) for after, p in self.distributions[(profile, action)]), action,
        ))

    def select_optimal(self, profile, previous, remaining) -> int:
        return min(self.actions(profile), key=lambda action: (self.action_value(profile, action, previous, remaining), action))

    def expected_score(self, choose, profile: tuple) -> float:
        @cache
        def value(state, previous, remaining):
            if remaining == 0:
                return 0.0
            if all(state):
                return float(remaining)
            if self.boundary(state):
                return self.spec.boundary_cost(remaining)
            action = choose(state, previous, self.spec.horizon - remaining)
            if action not in self.actions(state):
                raise ValueError("Policy selected an action outside the experiment mask.")
            return sum(p * (self.immediate_cost(after, action, previous) + value(after, action, remaining - 1))
                       for after, p in self.distributions[(state, action)])
        return value(profile, None, self.spec.horizon)

    def manifest(self) -> dict:
        semantic = json.dumps(self.generator.interactions, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return {
            "specification": asdict(self.spec),
            "interaction_data_sha256": hashlib.sha256(semantic).hexdigest(),
            "csv_sha256": hashlib.sha256(self.data.read_bytes()).hexdigest(),
            "mask_table_sha256": hashlib.sha256(self.mask_table.tobytes()).hexdigest(),
            "action_names": list(ANTIBIOTICS), "observation_size": 15,
            "training_profiles": ["".join(map(str, p)) for p in PROFILES if self.actions(p)],
            "evaluation_profiles": 128,
            "boundary_rule": "terminate_with_pessimistic_remaining_training_cost; raw_future_burden_unknown",
            "selection_rule": "final_checkpoint; no promotion or automatic winner",
            "neutral_candidates": "retained, including states with neutral-only applicable outcomes",
            "limitations": [
                "Candidate availability is not proof of biological validity or clinical efficacy.",
                "No selected-drug self-resistance, bacterial clearance, dosing or stopping decision is modeled.",
                "Repetition penalties and occurrence probabilities are experimental assumptions, not measurements.",
            ],
        }


class EvidenceEnvironment(AntibioticEnvironment):
    def __init__(self, kernel: EvidenceKernel):
        self.kernel = kernel
        transition = StochasticTransitionModel(candidate_generator=kernel.generator, sampler=kernel.sampler)
        super().__init__(episode_progression=EpisodeProgression(episode_step=EpisodeStep(transition_model=transition)),
                         max_steps=kernel.spec.horizon)
        self.finished = False

    @property
    def research_reward_specification(self):
        return self.kernel.reward_specification

    @property
    def research_mask_configuration(self):
        return {"enabled": True, "rule": MASK_RULE if self.kernel.spec.supported_only else "susceptible_actions_only"}

    def action_masks(self) -> np.ndarray:
        if self.episode is None:
            return np.ones(7, dtype=bool)
        return self.kernel.mask(self.episode.resistance_state.resistance)

    def reset(self, *, seed=None, options=None):
        observation, info = super().reset(seed=seed, options=options)
        profile = self.episode.resistance_state.resistance
        self.finished = not self.action_masks().any()
        return observation, {**info, "evidence_boundary": self.kernel.boundary(profile)}

    def step(self, action):
        if self.finished:
            raise RuntimeError("Episode ended; reset before selecting an action.")
        if isinstance(action, (bool, np.bool_)) or not isinstance(action, (int, np.integer)) or not 0 <= action < 7:
            raise ValueError("Action must be a canonical integer index.")
        if not self.action_masks()[action]:
            raise ValueError("Action has no applicable transition or is resistant.")
        previous = next((index for index, bit in enumerate(self.last_action) if bit), None)
        observation, base_reward, terminated, truncated, info = super().step(action)
        remaining = self.kernel.spec.horizon - self.episode.treatment_step
        profile = self.episode.resistance_state.resistance
        boundary = not terminated and self.kernel.boundary(profile)
        repetition = self.kernel.spec.repetition_penalty * (action == previous)
        continuation = self.kernel.spec.boundary_cost(remaining) if boundary else 0.0
        self.finished = bool(terminated or truncated or boundary)
        return observation, base_reward - repetition - continuation, self.finished, truncated, {
            **info, "observed_burden": sum(profile) / 7, "repeated_action": action == previous,
            "repetition_cost": repetition, "uncertainty_continuation_cost": continuation,
            "evidence_boundary": boundary, "unobserved_steps": remaining if boundary else 0,
        }


class EvidenceDQN(MaskedDQN):
    """Persist the same state-derived evidence mask for exploration and replay targets."""
    def __init__(self, *args, evidence_mask_table=None, **kwargs):
        self.evidence_mask_table = None if evidence_mask_table is None else np.asarray(evidence_mask_table, dtype=bool)
        super().__init__(*args, **kwargs)

    def _action_masks(self, observations: torch.Tensor) -> torch.Tensor:
        susceptible = susceptible_mask(observations)
        if self.evidence_mask_table is None or self.evidence_mask_table.shape != (128, 7):
            raise ValueError("EvidenceDQN requires its archived 128 by 7 mask table.")
        weights = torch.as_tensor(WEIGHTS, device=observations.device)
        indices = (observations[:, :7].long() * weights).sum(dim=1)
        mask = torch.as_tensor(self.evidence_mask_table, device=observations.device)[indices]
        if (mask & ~susceptible).any():
            raise ValueError("Evidence masks cannot permit resistant actions.")
        return mask


@dataclass(frozen=True)
class EvidenceRuntimeConfig:
    kernel: EvidenceKernel

    @property
    def scenario_id(self):
        return self.kernel.spec.scenario_id

    @property
    def horizon(self):
        return self.kernel.spec.horizon

    @property
    def reward_configuration(self):
        return self.kernel.reward_specification

    @property
    def action_mask_configuration(self):
        return {"enabled": True, "rule": MASK_RULE}


class EvidenceObservationPolicy:
    def __init__(self, model, kernel):
        self.model, self.kernel = model, kernel

    def select_action(self, observation):
        kwargs = {} if isinstance(self.model, EvidenceDQN) else {"action_masks": self.kernel.mask(observation[:7])}
        action, _ = self.model.predict(observation, deterministic=True, **kwargs)
        return int(action)


class EvidenceRandomPolicy:
    def __init__(self, kernel, seed):
        self.kernel = kernel
        self.rng = random.Random(seed)

    def select_action(self, observation):
        return self.rng.choice(self.kernel.actions(tuple(int(bit) for bit in observation[:7])))
