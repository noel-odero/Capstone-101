from dataclasses import dataclass

ANTIBIOTICS = (
    "CIPROFLOXACIN",
    "NITROFURANTOIN",
    "FOSFOMYCIN",
    "TRIMETHOPRIM",
    "GENTAMICIN",
    "MECILLINAM",
    "CEFTAZIDIME",
)


@dataclass(frozen=True)
class ResistanceState:
    resistance: tuple[int, ...]

    def __post_init__(self):
        if len(self.resistance) != len(ANTIBIOTICS):
            raise ValueError(
                f"Expected {len(ANTIBIOTICS)} resistance values, "
                f"got {len(self.resistance)}."
            )

        if any(value not in (0, 1) for value in self.resistance):
            raise ValueError("Resistance values must be 0 or 1.")

    def is_resistant(self, antibiotic: str) -> bool:
        try:
            index = ANTIBIOTICS.index(antibiotic)
        except ValueError:
            raise ValueError(f"Unknown antibiotic: {antibiotic}")

        return bool(self.resistance[index])

    def is_susceptible(self, antibiotic: str) -> bool:
        return not self.is_resistant(antibiotic)

    def resistant_antibiotics(self) -> tuple[str, ...]:
        return tuple(
            antibiotic
            for antibiotic, value in zip(ANTIBIOTICS, self.resistance)
            if value == 1
        )

    def to_dict(self) -> dict:
        return {
            "resistance": list(self.resistance),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResistanceState":
        return cls(tuple(data["resistance"]))
