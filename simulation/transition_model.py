from dataclasses import dataclass
from typing import Protocol

from simulation.resistance_state import ResistanceState


@dataclass(frozen=True)
class TransitionResult:
    next_state: ResistanceState
    outcome: str
    source_ids: tuple[str, ...]


class TransitionModel(Protocol):
    def step(
        self,
        state: ResistanceState,
        action: int,
        seed: int | None = None,
    ) -> TransitionResult:
        ...