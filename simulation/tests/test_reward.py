import pytest

from simulation.resistance_state import ResistanceState
from simulation.reward import RewardFunction, RewardSpecification


def test_reward_is_negative_normalized_post_transition_resistance_burden():
    reward_function = RewardFunction()

    assert reward_function.calculate(ResistanceState((0,) * 7)) == 0.0
    assert reward_function.calculate(ResistanceState((1, 0, 0, 0, 0, 0, 0))) == pytest.approx(-1 / 7)
    assert reward_function.calculate(ResistanceState((1, 1, 1, 1, 0, 0, 0))) == pytest.approx(-4 / 7)


def test_all_resistant_terminal_state_is_charged_through_remaining_horizon():
    reward_function = RewardFunction()

    assert reward_function.calculate(
        ResistanceState((1,) * 7), remaining_horizon_steps=3
    ) == pytest.approx(-4.0)


@pytest.mark.parametrize("remaining_horizon_steps", [-1, True, 1.5])
def test_remaining_horizon_steps_must_be_nonnegative_integer(remaining_horizon_steps):
    with pytest.raises(ValueError, match="nonnegative integer"):
        RewardFunction().calculate(
            ResistanceState((1,) * 7),
            remaining_horizon_steps=remaining_horizon_steps,
        )


def test_reward_specification_names_objective_and_terminal_convention():
    assert RewardSpecification().to_dict() == {
        "objective": "normalized_resistance_burden",
        "normalization": 7,
        "terminal_convention": "all_resistant_state_persists_to_horizon",
    }