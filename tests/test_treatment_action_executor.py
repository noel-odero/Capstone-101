import pytest

from simulation.resistance_state import ResistanceState
from simulation.treatment_action import TreatmentActionResult
from simulation.treatment_action_executor import TreatmentActionExecutor


def test_execute_effective_treatment():
    executor = TreatmentActionExecutor()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result = executor.execute(
        state,
        action=0,
    )

    assert isinstance(result, TreatmentActionResult)
    assert result.action == 0
    assert result.antibiotic == "CIPROFLOXACIN"
    assert result.effective is True


def test_execute_ineffective_treatment():
    executor = TreatmentActionExecutor()

    state = ResistanceState(
        (1, 0, 0, 0, 0, 0, 0)
    )

    result = executor.execute(
        state,
        action=0,
    )

    assert result.action == 0
    assert result.antibiotic == "CIPROFLOXACIN"
    assert result.effective is False


def test_execute_does_not_mutate_state():
    executor = TreatmentActionExecutor()

    state = ResistanceState(
        (1, 0, 0, 0, 0, 0, 0)
    )

    executor.execute(
        state,
        action=0,
    )

    assert state == ResistanceState(
        (1, 0, 0, 0, 0, 0, 0)
    )


@pytest.mark.parametrize("invalid_action", [-1, 7, 100])
def test_invalid_action_is_rejected(invalid_action):
    executor = TreatmentActionExecutor()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    with pytest.raises(ValueError):
        executor.execute(
            state,
            action=invalid_action,
        )