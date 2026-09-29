from dataclasses import dataclass

from simulation.resistance_state import ResistanceState


@dataclass(frozen=True)
class EpisodeState:
    resistance_state: ResistanceState
    treatment_step: int = 0

    def advance(
        self,
        next_resistance_state: ResistanceState,
    ) -> "EpisodeState":
        return EpisodeState(
            resistance_state=next_resistance_state,
            treatment_step=self.treatment_step + 1,
        )