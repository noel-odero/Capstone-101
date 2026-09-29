import csv
from pathlib import Path

from simulation.action_space import ActionSpace
from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState


EMPIRICAL_INTERACTIONS_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "empirical_interactions.csv"
)


class CandidateTransitionGenerator:
    def __init__(
        self,
        action_space: ActionSpace | None = None,
    ):
        self.action_space = action_space or ActionSpace()
        self.interactions = self._load_interactions()

    def _load_interactions(self) -> tuple[dict[str, str], ...]:
        with EMPIRICAL_INTERACTIONS_FILE.open(
            newline="",
            encoding="utf-8-sig",
        ) as file:
            rows = list(csv.DictReader(file))

        required_columns = {
            "source_id",
            "from_drug",
            "to_drug",
            "relationship",
            "directionality",
        }

        if not rows:
            raise ValueError("Empirical interactions file is empty.")

        if not required_columns.issubset(rows[0].keys()):
            raise ValueError(
                "Empirical interactions CSV is missing required columns."
            )

        return tuple(rows)

    def generate(
        self,
        state: ResistanceState,
        action: int,
    ) -> tuple[CandidateTransition, ...]:
        selected_drug = self.action_space.antibiotic_for(action)
        candidates: list[CandidateTransition] = []

        for interaction in self.interactions:
            if interaction["directionality"] != "A_to_B":
                continue

            if interaction["from_drug"] != selected_drug.lower():
                continue

            target_drug = interaction["to_drug"].upper()
            relationship = interaction["relationship"]

            target_resistant = state.is_resistant(target_drug)

            if relationship == "CR" and not target_resistant:
                candidates.append(
                    CandidateTransition(
                        target_drug=target_drug,
                        outcome="cross_resistance",
                        source_ids=(interaction["source_id"],),
                    )
                )

            elif relationship == "CS" and target_resistant:
                candidates.append(
                    CandidateTransition(
                        target_drug=target_drug,
                        outcome="collateral_sensitivity",
                        source_ids=(interaction["source_id"],),
                    )
                )

            elif relationship == "neutral":
                candidates.append(
                    CandidateTransition(
                        target_drug=target_drug,
                        outcome="neutral",
                        source_ids=(interaction["source_id"],),
                    )
                )

        return tuple(candidates)