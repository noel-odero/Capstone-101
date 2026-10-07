from dataclasses import asdict, dataclass

from simulation.resistance_state import ANTIBIOTICS, ResistanceState


@dataclass(frozen=True)
class RewardSpecification:
    objective: str = "normalized_resistance_burden"
    normalization: int = len(ANTIBIOTICS)
    terminal_convention: str = "all_resistant_state_persists_to_horizon"

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class RewardFunction:
    """Minimize resistance burden subject to an external susceptibility mask."""

    def __init__(self, specification: RewardSpecification | None = None):
        self.specification = specification or RewardSpecification()

    def calculate(
        self,
        next_state: ResistanceState,
        *,
        remaining_horizon_steps: int = 0,
    ) -> float:
        if (
            isinstance(remaining_horizon_steps, bool)
            or not isinstance(remaining_horizon_steps, int)
            or remaining_horizon_steps < 0
        ):
            raise ValueError("Remaining horizon steps must be a nonnegative integer.")

        resistant_count = len(next_state.resistant_antibiotics())
        charged_steps = 1
        if resistant_count == len(ANTIBIOTICS):
            charged_steps += remaining_horizon_steps

        return -resistant_count * charged_steps / self.specification.normalization