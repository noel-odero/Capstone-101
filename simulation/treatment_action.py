from dataclasses import dataclass


@dataclass(frozen=True)
class TreatmentActionResult:
    action: int
    antibiotic: str
    effective: bool