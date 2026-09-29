from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateTransition:
    target_drug: str
    outcome: str
    source_ids: tuple[str, ...]