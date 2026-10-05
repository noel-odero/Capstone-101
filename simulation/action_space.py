#  loads the CSV, checks the action IDs and canonical ordering, 
# and maps between action IDs and antibiotic names.

import csv
from pathlib import Path

from simulation.resistance_state import ANTIBIOTICS


ACTION_SPACE_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "action_space.csv"
)


class ActionSpace:
    def __init__(self):
        self.actions = self._load_actions()

    def _load_actions(self) -> tuple[str, ...]:
        with ACTION_SPACE_FILE.open(
            newline="",
            encoding="utf-8-sig",
        ) as file:
            rows = list(csv.DictReader(file))

        required_columns = {
            "action_id",
            "drug",
            "drug_class",
            "role",
            "clinical_scope",
            "evolutionary_evidence",
            "action_space_status",
            "notes",
        }

        if not required_columns.issubset(rows[0].keys()):
            raise ValueError(
                "Action-space CSV is missing required columns."
            )

        rows.sort(key=lambda row: int(row["action_id"]))

        action_ids = [int(row["action_id"]) for row in rows]

        if action_ids != list(range(len(rows))):
            raise ValueError(
                "Action IDs must be contiguous starting from 0."
            )

        drugs = tuple(row["drug"] for row in rows)

        if len(drugs) != len(set(drugs)):
            raise ValueError("Duplicate drugs found in action space.")

        if drugs != ANTIBIOTICS:
            raise ValueError(
                "CSV drug order does not match the canonical resistance-state order."
            )

        return drugs

    @property
    def size(self) -> int:
        return len(self.actions)

    def antibiotic_for(self, action: int) -> str:
        if not isinstance(action, int):
            raise ValueError("Action must be an integer.")

        if action < 0 or action >= self.size:
            raise ValueError(f"Invalid action: {action}")

        return self.actions[action]

    def action_for(self, antibiotic: str) -> int:
        try:
            return self.actions.index(antibiotic)
        except ValueError:
            raise ValueError(f"Unknown antibiotic: {antibiotic}")
