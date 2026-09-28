import pytest

from simulation.resistance_state import ResistanceState
from simulation.reward import RewardFunction, RewardWeights


def test_effective_treatment_gets_positive_reward():
    reward_function = RewardFunction()

    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    assert reward_function.effectiveness_reward(state, 0) == 1.0


def test_ineffective_treatment_gets_negative_reward():
    reward_function = RewardFunction()

    state = ResistanceState((1, 0, 0, 0, 0, 0, 0))

    assert reward_function.effectiveness_reward(state, 0) == -1.0


def test_resistance_increase_is_penalized():
    reward_function = RewardFunction()

    previous = ResistanceState((0, 0, 0, 0, 0, 0, 0))
    next_state = ResistanceState((1, 0, 0, 0, 0, 0, 0))

    assert reward_function.resistance_reward(previous, next_state) == -1.0


def test_resistance_decrease_is_rewarded():
    reward_function = RewardFunction()

    previous = ResistanceState((1, 0, 0, 0, 0, 0, 0))
    next_state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    assert reward_function.resistance_reward(previous, next_state) == 1.0


def test_no_resistance_change_has_zero_resistance_reward():
    reward_function = RewardFunction()

    previous = ResistanceState((1, 0, 0, 0, 0, 0, 0))
    next_state = ResistanceState((1, 0, 0, 0, 0, 0, 0))

    assert reward_function.resistance_reward(previous, next_state) == 0.0


def test_exposure_has_negative_reward():
    reward_function = RewardFunction()

    assert reward_function.exposure_reward() == -1.0


def test_weights_are_configurable():
    weights = RewardWeights(
        effectiveness=2.0,
        resistance=3.0,
        exposure=0.5,
    )

    reward_function = RewardFunction(weights=weights)

    assert reward_function.weights == weights


def test_combined_reward():
    reward_function = RewardFunction()

    previous = ResistanceState((0, 0, 0, 0, 0, 0, 0))
    next_state = ResistanceState((1, 0, 0, 0, 0, 0, 0))

    reward = reward_function.calculate(
        previous_state=previous,
        next_state=next_state,
        action=0,
    )

    # +1 effectiveness
    # -0.5 resistance increase
    # -0.1 exposure
    # = 0.4
    assert reward == pytest.approx(0.4)