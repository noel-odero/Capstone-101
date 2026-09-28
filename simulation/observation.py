from dataclasses import dataclass

from simulation.resistance_state import ANTIBIOTICS


@dataclass(frozen=True)
class Observation:
    susceptibility: tuple[int, ...]
    last_action: tuple[int, ...]
    treatment_step: int

    def __post_init__(self):
        if len(self.susceptibility) != len(ANTIBIOTICS):
            raise ValueError(
                f"Expected {len(ANTIBIOTICS)} susceptibility values, "
                f"got {len(self.susceptibility)}."
            )

        if any(value not in (-1, 0, 1) for value in self.susceptibility):
            raise ValueError("Susceptibility values must be -1, 0, or 1.")

        if len(self.last_action) != len(ANTIBIOTICS):
            raise ValueError(
                f"Expected {len(ANTIBIOTICS)} last-action values, "
                f"got {len(self.last_action)}."
            )

        if any(value not in (0, 1) for value in self.last_action):
            raise ValueError("Last-action values must be 0 or 1.")

        if sum(self.last_action) > 1:
            raise ValueError("Last action must contain at most one selected antibiotic.")

        if self.treatment_step < 0:
            raise ValueError("Treatment step cannot be negative.")

    def to_vector(self) -> tuple[int, ...]:
        return (
            self.susceptibility
            + self.last_action
            + (self.treatment_step,)
        )