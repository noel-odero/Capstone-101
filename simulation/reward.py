from dataclasses import dataclass

from simulation.action_space import ActionSpace
from simulation.resistance_state import ResistanceState


@dataclass(frozen=True)
class RewardWeights:
    effectiveness: float = 1.0
    resistance: float = 0.5
    exposure: float = 0.1


class RewardFunction:
    def __init__(
        self,
        weights: RewardWeights | None = None,
        action_space: ActionSpace | None = None,
    ):
        self.weights = weights or RewardWeights()
        self.action_space = action_space or ActionSpace()

    def effectiveness_reward(
        self,
        state: ResistanceState,
        action: int,
    ) -> float:
        antibiotic = self.action_space.antibiotic_for(action)

        if state.is_susceptible(antibiotic):
            return 1.0

        return -1.0

    def resistance_reward(
        self,
        previous_state: ResistanceState,
        next_state: ResistanceState,
    ) -> float:
        previous_resistant = len(
            previous_state.resistant_antibiotics()
        )
        next_resistant = len(
            next_state.resistant_antibiotics()
        )

        resistance_change = next_resistant - previous_resistant

        return -float(resistance_change)

    def exposure_reward(self) -> float:
        return -1.0

    def calculate(
        self,
        previous_state: ResistanceState,
        next_state: ResistanceState,
        action: int,
    ) -> float:
        effectiveness = self.effectiveness_reward(
            previous_state,
            action,
        )

        resistance = self.resistance_reward(
            previous_state,
            next_state,
        )

        exposure = self.exposure_reward()

        return (
            self.weights.effectiveness * effectiveness
            + self.weights.resistance * resistance
            + self.weights.exposure * exposure
        )