"""Verified PPO and DQN engines sharing one simulator contract."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from ml.src.ppo_inference import (
    CANDIDATES_AVAILABLE_STATUS,
    ContractMismatchError,
    DEFAULT_MANIFEST_PATH,
    NO_CANDIDATE_STATUS,
    FrozenCheckpointManifest,
    FrozenPolicyInferenceEngine,
    InferenceContext,
    TerminalStateError,
    get_frozen_engine,
    load_manifest,
)
from ml.src.ppo_training import PPOConfig
from service import __version__
from simulation.action_space import ACTION_SPACE_FILE, ActionSpace
from simulation.resistance_state import ANTIBIOTICS

logger = logging.getLogger("service")
DQN_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "artifacts/frozen/public-data-v2/dqn/manifest.json"

DISCLAIMER = (
    "Model-derived research analysis only. It is not clinical advice, a validated treatment recommendation, or a "
    "statement about clinical efficacy."
)
INTERPRETATION = (
    "The action is the frozen policy's choice among simulator-feasible (currently susceptible) antibiotics. "
    "Transition support only says whether the simulator has modeled outcomes for this action in this state; "
    "it does not imply the profile will change or that the drug is clinically effective."
)
TRANSITION_STATUS_DEFINITIONS = {
    NO_CANDIDATE_STATUS: (
        "The simulator has no candidate transition for this action in this state and leaves the resistance "
        "profile unchanged. This is a data gap, not evidence that the antibiotic is effective."
    ),
    CANDIDATES_AVAILABLE_STATUS: (
        "The simulator has at least one modeled transition outcome (cross-resistance, collateral sensitivity "
        "or neutral) for this action in this state. The profile may still be unchanged."
    ),
    "cross_resistance": "Sampled outcome: the target drug became resistant.",
    "collateral_sensitivity": "Sampled outcome: the target drug became susceptible.",
    "neutral": "Sampled outcome: a modeled neutral interaction; the profile is unchanged.",
}


@dataclass(frozen=True)
class ModelRuntime:
    engine: FrozenPolicyInferenceEngine
    manifest: FrozenCheckpointManifest
    manifest_document: dict[str, Any]
    config: PPOConfig
    antibiotics: tuple[dict[str, Any], ...]
    dqn_engine: FrozenPolicyInferenceEngine

    def engine_for(self, strategy: str) -> FrozenPolicyInferenceEngine:
        return self.dqn_engine if strategy == "dqn" else self.engine

    def policy_model(self, strategy: str) -> dict[str, str] | None:
        if strategy == "greedy":
            return None
        engine = self.engine_for(strategy)
        return {
            "model_id": engine.model_id,
            "algorithm": "MaskedDQN" if strategy == "dqn" else "MaskablePPO",
            "checkpoint_sha256": engine.checkpoint_sha256,
        }

    def describe_model(self) -> dict[str, Any]:
        document = self.manifest_document
        return {
            "manifest_version": document["manifest_version"],
            "model_id": self.engine.model_id,
            "algorithm": document["algorithm"],
            "checkpoint_sha256": self.engine.checkpoint_sha256,
            "manifest_checkpoint_sha256": self.manifest.checkpoint_sha256,
            "interaction_data_sha256": self.manifest.interaction_data_sha256,
            "scenario_id": self.manifest.scenario_id,
            "horizon": self.engine.horizon,
            "antibiotic_order": list(document["simulator"]["action_names"]),
            "observation": document["observation"],
            "action_space": document["action_space"],
            "action_masking": document["action_masking"],
            "inference": document["inference"],
            "provenance_files": dict(document["provenance"]),
            "transition_status_definitions": TRANSITION_STATUS_DEFINITIONS,
            "service_version": __version__,
            "disclaimer": DISCLAIMER,
            "policies": {strategy: self.policy_model(strategy) for strategy in ("ppo", "dqn")},
        }

    def list_antibiotics(self) -> dict[str, Any]:
        return {
            "antibiotics": [dict(item) for item in self.antibiotics],
            "resistance_encoding": dict(self.manifest_document["observation"]["resistance_encoding"]),
        }

    def feasible_actions(self, context: InferenceContext) -> list[dict[str, Any]]:
        """Susceptible-only rule, identical to the engine's mask; support flags come from the simulator's generator."""
        state = context.resistance_state
        return [
            {
                "action_id": action_id,
                "antibiotic": name,
                "has_candidate_transition": self.engine.has_candidate_transition(context, action_id),
            }
            for action_id, name in enumerate(ANTIBIOTICS)
            if state.is_susceptible(name)
        ]

    def validate_profile(self, resistance_profile: list[int]) -> dict[str, Any]:
        context = InferenceContext(tuple(resistance_profile), None, 0)
        state = context.resistance_state
        resistant = state.resistant_antibiotics()
        susceptible = [name for name in ANTIBIOTICS if name not in resistant]
        is_terminal = not susceptible
        feasible = [] if is_terminal else self.feasible_actions(context)
        return {
            "valid": True,
            "resistance_profile": list(context.resistance_profile),
            "resistant_antibiotics": list(resistant),
            "susceptible_antibiotics": susceptible,
            "resistant_count": len(resistant),
            "susceptible_option_count": len(susceptible),
            "feasible_actions": feasible,
            "feasible_action_ids": [item["action_id"] for item in feasible],
            "is_terminal": is_terminal,
            "terminal_reason": "no_effective_antibiotic" if is_terminal else None,
            "horizon": self.engine.horizon,
        }

    def recommend(
        self, resistance_profile: list[int], last_action: int | None, treatment_step: int
    ) -> dict[str, Any]:
        context = InferenceContext(tuple(resistance_profile), last_action, treatment_step)
        susceptible_count = len(ANTIBIOTICS) - len(context.resistance_state.resistant_antibiotics())
        common = {
            "resistance_profile": list(context.resistance_profile),
            "last_action_id": context.last_action,
            "last_action_antibiotic": None if context.last_action is None else ANTIBIOTICS[context.last_action],
            "treatment_step": context.treatment_step,
            "susceptible_option_count": susceptible_count,
            "model_id": self.engine.model_id,
            "checkpoint_sha256": self.engine.checkpoint_sha256,
            "interpretation": INTERPRETATION,
        }
        try:
            result = self.engine.recommend(context)
        except TerminalStateError as terminal:
            return {
                **common,
                "status": "terminal",
                "is_terminal": True,
                "terminal_reason": terminal.reason,
                "action_id": None,
                "antibiotic": None,
                "feasible_actions": [],
                "feasible_action_ids": [],
                "transition_status": None,
                "has_candidate_transition": None,
            }
        feasible = self.feasible_actions(context)
        return {
            **common,
            "status": "recommended",
            "is_terminal": False,
            "terminal_reason": None,
            "action_id": result.action_id,
            "antibiotic": result.antibiotic,
            "feasible_actions": feasible,
            "feasible_action_ids": list(result.feasible_action_ids),
            "transition_status": result.transition_status,
            "has_candidate_transition": result.has_candidate_transition,
        }


def _load_antibiotics() -> tuple[dict[str, Any], ...]:
    names = ActionSpace().actions  # validated against the canonical order by the existing loader
    with ACTION_SPACE_FILE.open(newline="", encoding="utf-8-sig") as file:
        classes = {row["drug"]: row["drug_class"] for row in csv.DictReader(file)}
    return tuple(
        {"action_id": action_id, "name": name, "drug_class": classes.get(name)}
        for action_id, name in enumerate(names)
    )


def load_runtime(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> ModelRuntime:
    """Verify and load through the existing cached engine; raises the inference layer's own errors."""
    engine = get_frozen_engine(manifest_path)
    manifest = load_manifest(manifest_path)
    with Path(manifest_path).open(encoding="utf-8") as manifest_file:
        document = json.load(manifest_file)
    dqn_engine = get_frozen_engine(DQN_MANIFEST_PATH)
    document_dqn = json.loads(DQN_MANIFEST_PATH.read_text(encoding="utf-8"))
    if document["algorithm"] != "MaskablePPO" or document_dqn["algorithm"] != "MaskedDQN":
        raise ContractMismatchError("The PPO and DQN slots must contain their declared algorithms.")
    for key in ("simulator", "observation", "action_space", "action_masking", "inference"):
        if document[key] != document_dqn[key]:
            raise ContractMismatchError(f"PPO and DQN must share the same {key} contract.")
    return ModelRuntime(
        engine=engine,
        manifest=manifest,
        manifest_document=document,
        config=PPOConfig(
            scenario_id=manifest.scenario_id, horizon=manifest.horizon, device=manifest.device,
            interaction_data_path=manifest.interaction_data_path,
        ),
        antibiotics=_load_antibiotics(),
        dqn_engine=dqn_engine,
    )
