import pytest

from simulation.resistance_state import ResistanceState
from simulation.treatment_effectiveness import TreatmentEffectiveness


def test_susceptible_antibiotic_is_effective():
    state = ResistanceState(
        (0, 1, 0, 1, 0, 0, 1)
    )

    effectiveness = TreatmentEffectiveness()

    assert effectiveness.is_effective(state, 0)


def test_resistant_antibiotic_is_not_effective():
    state = ResistanceState(
        (0, 1, 0, 1, 0, 0, 1)
    )

    effectiveness = TreatmentEffectiveness()

    assert not effectiveness.is_effective(state, 1)


def test_all_susceptible_antibiotics_are_effective():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    effectiveness = TreatmentEffectiveness()

    for action in range(7):
        assert effectiveness.is_effective(state, action)


def test_all_resistant_antibiotics_are_not_effective():
    state = ResistanceState(
        (1, 1, 1, 1, 1, 1, 1)
    )

    effectiveness = TreatmentEffectiveness()

    for action in range(7):
        assert not effectiveness.is_effective(state, action)


def test_invalid_action_is_rejected():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    effectiveness = TreatmentEffectiveness()

    with pytest.raises(ValueError):
        effectiveness.is_effective(state, 7)