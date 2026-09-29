from simulation.action_space import ActionSpace
from simulation.resistance_state import ResistanceState
from simulation.treatment_action import TreatmentActionResult
from simulation.treatment_effectiveness import TreatmentEffectiveness


class TreatmentActionExecutor:
    def __init__(
        self,
        action_space: ActionSpace | None = None,
        treatment_effectiveness: TreatmentEffectiveness | None = None,
    ):
        self.action_space = action_space or ActionSpace()
        self.treatment_effectiveness = (
            treatment_effectiveness
            or TreatmentEffectiveness(self.action_space)
        )

    def execute(
        self,
        state: ResistanceState,
        action: int,
    ) -> TreatmentActionResult:
        antibiotic = self.action_space.antibiotic_for(action)

        effective = self.treatment_effectiveness.is_effective(
            state,
            action,
        )

        return TreatmentActionResult(
            action=action,
            antibiotic=antibiotic,
            effective=effective,
        )