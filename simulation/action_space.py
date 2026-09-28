from simulation.resistance_state import ANTIBIOTICS


class ActionSpace:
    def __init__(self):
        self.actions = ANTIBIOTICS

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