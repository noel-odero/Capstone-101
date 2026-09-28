from simulation.action_space import ActionSpace
from simulation.resistance_state import ResistanceState


class TreatmentEffectiveness:
    def __init__(self, action_space: ActionSpace | None = None):
        self.action_space = action_space or ActionSpace()

    def is_effective(
        self,
        state: ResistanceState,
        action: int,
    ) -> bool:
        antibiotic = self.action_space.antibiotic_for(action)
        return state.is_susceptible(antibiotic)