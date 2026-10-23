"""Frozen policy inference contract: one validated state context in, one feasible action out.

The context carries the full observation state (resistance profile, last action, treatment step), so
callers cannot rebuild an observation with a zeroed previous action or a reset step. Simulator,
mask, reward and termination rules are reused from ``simulation`` and ``ml.src``, never copied.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import hashlib
import io
import json
from pathlib import Path
import threading
from typing import Any

import numpy as np
from sb3_contrib import MaskablePPO

from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.masked_dqn import DQNObservationPolicy, MaskedDQN
from ml.src.ppo_training import PPOConfig, environment_manifest, make_training_environment
from simulation.episode import EpisodeState
from simulation.episode_termination import EpisodeTermination
from simulation.observation import OBSERVATION_VECTOR_SIZE, Observation, encode_observation
from simulation.resistance_state import ANTIBIOTICS, ResistanceState

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "ml" / "frozen_ppo_manifest.json"

# The status string matches the simulator's own label for an action with no candidate transition.
NO_CANDIDATE_STATUS = "unsupported_no_candidate"
CANDIDATES_AVAILABLE_STATUS = "candidate_transition_available"


class InferenceError(Exception):
    """Base class for every explicit inference failure."""


class InvalidContextError(InferenceError, ValueError):
    """The state context is malformed or not reachable in the simulator."""


class TerminalStateError(InferenceError):
    """The episode has ended, so there is no action to recommend."""

    def __init__(self, reason: str):
        super().__init__(f"Terminal state ({reason}); no action can be recommended.")
        self.reason = reason


class EmptyActionMaskError(InferenceError):
    """A non-terminal context has no feasible action."""


class InfeasibleActionError(InferenceError, RuntimeError):
    """The policy returned an action outside the feasibility mask."""


class CheckpointIntegrityError(InferenceError):
    """The checkpoint is missing or its SHA-256 differs from the pinned value."""


class ContractMismatchError(InferenceError):
    """The manifest, simulator, or loaded model disagree on the inference contract."""


def _is_integer(value: Any) -> bool:
    return isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_))


@dataclass(frozen=True)
class InferenceContext:
    """Full state at one decision point.

    ``resistance_profile`` follows ``ANTIBIOTICS`` order with 0 = susceptible and 1 = resistant.
    ``last_action`` is the previous action id, or None only at treatment step 0, matching the
    simulator, which emits an all-zero one-hot only from ``reset``.
    """

    resistance_profile: tuple[int, ...]
    last_action: int | None
    treatment_step: int

    def __post_init__(self) -> None:
        profile = self.resistance_profile
        if isinstance(profile, (str, bytes)) or not isinstance(profile, (tuple, list, np.ndarray)):
            raise InvalidContextError("resistance_profile must be a sequence of seven 0/1 integers.")
        if len(profile) != len(ANTIBIOTICS):
            raise InvalidContextError(
                f"resistance_profile must have {len(ANTIBIOTICS)} values, got {len(profile)}."
            )
        if not all(_is_integer(value) and value in (0, 1) for value in profile):
            raise InvalidContextError("resistance_profile values must be the integers 0 or 1.")
        if self.last_action is not None and not (
            _is_integer(self.last_action) and 0 <= self.last_action < len(ANTIBIOTICS)
        ):
            raise InvalidContextError("last_action must be None or an integer action id from 0 to 6.")
        if not _is_integer(self.treatment_step) or self.treatment_step < 0:
            raise InvalidContextError("treatment_step must be a nonnegative integer.")
        if (self.last_action is None) != (self.treatment_step == 0):
            raise InvalidContextError(
                "last_action must be None exactly when treatment_step is 0, as in the simulator."
            )
        object.__setattr__(self, "resistance_profile", tuple(int(value) for value in profile))
        object.__setattr__(
            self, "last_action", None if self.last_action is None else int(self.last_action)
        )
        object.__setattr__(self, "treatment_step", int(self.treatment_step))

    @property
    def resistance_state(self) -> ResistanceState:
        return ResistanceState(self.resistance_profile)

    def to_observation(self) -> np.ndarray:
        """Encode with the simulator's own ``Observation``/``encode_observation``."""
        last_action = tuple(
            1 if index == self.last_action else 0 for index in range(len(ANTIBIOTICS))
        )
        observation = Observation(
            susceptibility=self.resistance_profile,
            last_action=last_action,
            treatment_step=self.treatment_step,
        )
        return np.asarray(encode_observation(observation), dtype=np.float32)

    @classmethod
    def from_observation(cls, observation: Any) -> InferenceContext:
        """Recover the context from an environment observation, so ``step()`` output can be fed back."""
        try:
            values = np.asarray(observation, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise InvalidContextError("Observation must be a numeric vector.") from error
        if values.shape != (OBSERVATION_VECTOR_SIZE,) or not np.isfinite(values).all():
            raise InvalidContextError(
                f"Observation must be a finite vector of {OBSERVATION_VECTOR_SIZE} values."
            )
        if not np.array_equal(values, np.round(values)):
            raise InvalidContextError("Observation values must be integral.")
        integers = [int(value) for value in values]
        one_hot = integers[len(ANTIBIOTICS):2 * len(ANTIBIOTICS)]
        if any(value not in (0, 1) for value in one_hot) or sum(one_hot) > 1:
            raise InvalidContextError("Observation last-action entries must be a one-hot or all zeros.")
        return cls(
            resistance_profile=tuple(integers[:len(ANTIBIOTICS)]),
            last_action=one_hot.index(1) if any(one_hot) else None,
            treatment_step=integers[-1],
        )


@dataclass(frozen=True)
class InferenceResult:
    """One recommendation.

    ``transition_status`` reports only whether the simulator has a candidate transition for the
    selected action in this state. ``unsupported_no_candidate`` leaves the state unchanged in the
    simulator, and that is a data gap, not evidence that the antibiotic is effective. Likewise
    ``candidate_transition_available`` only says the simulator has modeled outcomes (which may include
    cross-resistance); it is not a guarantee of efficacy, and this is a simulation result, not advice.
    """

    action_id: int
    antibiotic: str
    context: InferenceContext
    observation: tuple[float, ...]
    feasible_action_ids: tuple[int, ...]
    feasible_antibiotics: tuple[str, ...]
    transition_status: str
    has_candidate_transition: bool
    model_id: str
    checkpoint_sha256: str


def _feasibility_mask(state: ResistanceState) -> np.ndarray:
    """Same rule as ``AntibioticEnvironment.action_masks``: susceptible drugs only."""
    return np.asarray([state.is_susceptible(antibiotic) for antibiotic in ANTIBIOTICS], dtype=bool)


class FrozenPolicyInferenceEngine:
    """Deterministic, mask-enforcing recommendation from a loaded policy.

    ``policy`` must provide ``select_action(observation)``, as ``MaskablePPOObservationPolicy`` does.
    """

    def __init__(
        self,
        *,
        policy: Any,
        candidate_generator: Any,
        horizon: int,
        model_id: str,
        checkpoint_sha256: str,
    ):
        self._policy = policy
        self._candidate_generator = candidate_generator
        self._horizon = horizon
        self._termination = EpisodeTermination(max_steps=horizon)
        self.model_id = model_id
        self.checkpoint_sha256 = checkpoint_sha256
        # Torch module state is shared across requests, so serialize predictions.
        self._lock = threading.Lock()

    @property
    def horizon(self) -> int:
        return self._horizon

    def has_candidate_transition(self, context: InferenceContext, action_id: int) -> bool:
        return bool(self._candidate_generator.generate(context.resistance_state, action_id))

    def recommend(self, context: InferenceContext) -> InferenceResult:
        if not isinstance(context, InferenceContext):
            raise InvalidContextError("recommend requires an InferenceContext.")
        if context.treatment_step > self._horizon:
            raise InvalidContextError(
                f"treatment_step {context.treatment_step} exceeds the horizon {self._horizon}."
            )
        state = context.resistance_state
        if self._termination.is_terminated(EpisodeState(state, context.treatment_step)):
            reason = (
                "no_effective_antibiotic"
                if len(state.resistant_antibiotics()) == len(ANTIBIOTICS)
                else "maximum_horizon"
            )
            raise TerminalStateError(reason)

        mask = _feasibility_mask(state)
        if not mask.any():
            raise EmptyActionMaskError("No feasible action exists for a non-terminal context.")
        feasible_ids = tuple(int(action) for action in np.flatnonzero(mask))

        observation = context.to_observation()
        with self._lock:
            action = self._policy.select_action(observation)
        if not _is_integer(action) or int(action) not in feasible_ids:
            raise InfeasibleActionError("The policy selected an action outside the feasibility mask.")
        action = int(action)

        has_candidate = self.has_candidate_transition(context, action)
        return InferenceResult(
            action_id=action,
            antibiotic=ANTIBIOTICS[action],
            context=context,
            observation=tuple(float(value) for value in observation),
            feasible_action_ids=feasible_ids,
            feasible_antibiotics=tuple(ANTIBIOTICS[index] for index in feasible_ids),
            transition_status=CANDIDATES_AVAILABLE_STATUS if has_candidate else NO_CANDIDATE_STATUS,
            has_candidate_transition=has_candidate,
            model_id=self.model_id,
            checkpoint_sha256=self.checkpoint_sha256,
        )


@dataclass(frozen=True)
class FrozenCheckpointManifest:
    model_id: str
    checkpoint_path: Path
    checkpoint_sha256: str
    scenario_id: str
    horizon: int
    device: str
    training_config_path: Path
    interaction_data_sha256: str
    interaction_data_path: str | None = None
    algorithm: str = "MaskablePPO"


def load_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> FrozenCheckpointManifest:
    """Read the version-controlled manifest and check its static contract against the simulator."""
    with Path(manifest_path).open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ContractMismatchError(f"Frozen manifest contract violation: {message}")

    try:
        require(manifest["manifest_version"] == 1, "unsupported manifest_version")
        require(manifest["algorithm"] in ("MaskablePPO", "MaskedDQN"), "algorithm must be MaskablePPO or MaskedDQN")
        require(
            tuple(manifest["simulator"]["action_names"]) == ANTIBIOTICS,
            "action_names must equal the simulator's ANTIBIOTICS order",
        )
        require(manifest["observation"]["shape"] == [OBSERVATION_VECTOR_SIZE], "observation shape")
        require(manifest["observation"]["dtype"] == "float32", "observation dtype")
        action_count = len(ANTIBIOTICS)
        require(
            manifest["observation"]["layout"]
            == {
                "resistance_indicators": [0, action_count],
                "last_action_one_hot": [action_count, 2 * action_count],
                "treatment_step": [2 * action_count, OBSERVATION_VECTOR_SIZE],
            },
            "observation layout",
        )
        require(
            manifest["observation"]["resistance_encoding"] == {"susceptible": 0, "resistant": 1},
            "resistance encoding",
        )
        require(
            manifest["action_space"] == {"type": "Discrete", "n": action_count},
            "action space",
        )
        require(
            manifest["action_masking"]["rule"]
            == PPOConfig().action_mask_configuration["rule"]
            == "susceptible_actions_only",
            "action masking rule",
        )
        require(manifest["inference"]["deterministic"] is True, "inference must be deterministic")
        horizon = manifest["simulator"]["horizon"]
        require(_is_integer(horizon) and horizon > 0, "horizon must be a positive integer")
        checkpoint_path = REPO_ROOT / manifest["checkpoint"]["path"]
        return FrozenCheckpointManifest(
            model_id=manifest["model_id"],
            checkpoint_path=checkpoint_path,
            checkpoint_sha256=str(manifest["checkpoint"]["sha256"]).lower(),
            scenario_id=manifest["simulator"]["scenario_id"],
            horizon=int(horizon),
            device=manifest["inference"]["device"],
            training_config_path=REPO_ROOT / manifest["provenance"]["config"],
            interaction_data_sha256=str(manifest["simulator"]["interaction_data_sha256"]).lower(),
            interaction_data_path=manifest["simulator"].get("interaction_data_path"),
            algorithm=manifest["algorithm"],
        )
    except (KeyError, TypeError) as error:
        raise ContractMismatchError(f"Frozen manifest is missing or malformed: {error!r}") from error


def read_verified_checkpoint(checkpoint_path: str | Path, expected_sha256: str) -> tuple[bytes, str]:
    """Read the file once and return (bytes, SHA-256), or raise; the expected value is never updated."""
    path = Path(checkpoint_path)
    if not path.is_file():
        raise CheckpointIntegrityError(f"Checkpoint file not found: {path}")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256.lower():
        raise CheckpointIntegrityError(
            f"Checkpoint SHA-256 mismatch for {path}: expected {expected_sha256.lower()}, got {actual}."
        )
    return data, actual


def verify_checkpoint_sha256(checkpoint_path: str | Path, expected_sha256: str) -> str:
    return read_verified_checkpoint(checkpoint_path, expected_sha256)[1]


def _load_model_from_bytes(checkpoint_bytes: bytes, device: str) -> MaskablePPO:
    """Same ``MaskablePPO.load`` as ``load_ppo_model``, fed the bytes that were hash-verified."""
    return MaskablePPO.load(io.BytesIO(checkpoint_bytes), device=device)


def _check_live_contract(manifest: FrozenCheckpointManifest, live_manifest: dict[str, Any]) -> None:
    """Compare the pinned manifest with the live simulator and the checkpoint's training config."""
    if live_manifest["interaction_data_sha256"] != manifest.interaction_data_sha256:
        raise ContractMismatchError(
            "Transition data differs from the pinned interaction_data_sha256; "
            "candidate-transition status would not match the audited simulator."
        )
    try:
        with manifest.training_config_path.open(encoding="utf-8") as config_file:
            training_config = json.load(config_file)
        if manifest.algorithm == "MaskedDQN":
            training_config = training_config["shared"]
    except (OSError, ValueError, KeyError) as error:
        raise ContractMismatchError(f"Training config is unreadable: {manifest.training_config_path}") from error
    expected = {
        "scenario_id": manifest.scenario_id,
        "horizon": manifest.horizon,
    }
    for key, value in expected.items():
        if training_config.get(key) != value:
            raise ContractMismatchError(f"Manifest {key} differs from the checkpoint's training config.")
    if training_config.get("action_mask_configuration", {}).get("rule") != "susceptible_actions_only":
        raise ContractMismatchError("Checkpoint was not trained with susceptible_actions_only masking.")
    if training_config.get("reward_configuration") != live_manifest["reward_specification"]:
        raise ContractMismatchError("Checkpoint reward specification differs from the simulator.")


def load_frozen_engine(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> FrozenPolicyInferenceEngine:
    """Verify the hash, then load those same bytes and check them against the live simulator."""
    manifest = load_manifest(manifest_path)
    checkpoint_bytes, digest = read_verified_checkpoint(
        manifest.checkpoint_path, manifest.checkpoint_sha256
    )

    config = PPOConfig(
        scenario_id=manifest.scenario_id, horizon=manifest.horizon, device=manifest.device,
        interaction_data_path=manifest.interaction_data_path,
    )
    _check_live_contract(manifest, environment_manifest(config))
    environment = make_training_environment(config)
    try:
        model = (_load_model_from_bytes(checkpoint_bytes, manifest.device) if manifest.algorithm == "MaskablePPO"
                 else MaskedDQN.load(io.BytesIO(checkpoint_bytes), device=manifest.device))
        if model.action_space != environment.action_space:
            raise ContractMismatchError("Checkpoint action space does not match the simulator.")
        if model.observation_space != environment.observation_space:
            raise ContractMismatchError("Checkpoint observation space does not match the simulator.")
        candidate_generator = (
            environment.episode_progression.episode_step.transition_model.candidate_generator
        )
        adapter = MaskablePPOObservationPolicy if manifest.algorithm == "MaskablePPO" else DQNObservationPolicy
        policy = adapter(environment.action_space, model)
    finally:
        environment.close()

    return FrozenPolicyInferenceEngine(
        policy=policy,
        candidate_generator=candidate_generator,
        horizon=manifest.horizon,
        model_id=manifest.model_id,
        checkpoint_sha256=digest,
    )


@functools.lru_cache(maxsize=None)
def _load_cached(manifest_path: str) -> FrozenPolicyInferenceEngine:
    return load_frozen_engine(manifest_path)


def get_frozen_engine(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> FrozenPolicyInferenceEngine:
    """Process-wide engine: the checkpoint is verified and loaded once, not per request."""
    return _load_cached(str(Path(manifest_path).resolve()))
