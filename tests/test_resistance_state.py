import pytest

from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def test_valid_resistance_state():
    state = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    assert len(state.resistance) == 7
    assert state.is_resistant("NITROFURANTOIN")
    assert state.is_resistant("TRIMETHOPRIM")
    assert state.is_resistant("CEFTAZIDIME")


def test_susceptible_antibiotic():
    state = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    assert state.is_susceptible("CIPROFLOXACIN")
    assert state.is_susceptible("FOSFOMYCIN")


def test_resistant_antibiotics():
    state = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    assert state.resistant_antibiotics() == (
        "NITROFURANTOIN",
        "TRIMETHOPRIM",
        "CEFTAZIDIME",
    )


def test_wrong_number_of_values():
    with pytest.raises(ValueError):
        ResistanceState((0, 1, 0))


def test_invalid_resistance_value():
    with pytest.raises(ValueError):
        ResistanceState((0, 1, 0, 1, 0, 0, 2))


def test_unknown_antibiotic():
    state = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    with pytest.raises(ValueError):
        state.is_resistant("UNKNOWN_DRUG")


def test_antibiotic_order_is_fixed():
    assert ANTIBIOTICS == (
        "CIPROFLOXACIN",
        "NITROFURANTOIN",
        "FOSFOMYCIN",
        "TRIMETHOPRIM",
        "GENTAMICIN",
        "MECILLINAM",
        "CEFTAZIDIME",
    )
def test_state_serializes_to_dict():
    state = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    assert state.to_dict() == {
        "resistance": [0, 1, 0, 1, 0, 0, 1]
    }


def test_state_can_be_restored_from_dict():
    original = ResistanceState((0, 1, 0, 1, 0, 0, 1))

    restored = ResistanceState.from_dict(original.to_dict())

    assert restored == original


def test_with_resistance_sets_antibiotic_as_resistant():
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    updated = state.with_resistance("GENTAMICIN", True)

    assert updated == ResistanceState((0, 0, 0, 0, 1, 0, 0))
    assert state == ResistanceState((0, 0, 0, 0, 0, 0, 0))


def test_with_resistance_sets_antibiotic_as_susceptible():
    state = ResistanceState((0, 0, 0, 0, 1, 0, 0))

    updated = state.with_resistance("GENTAMICIN", False)

    assert updated == ResistanceState((0, 0, 0, 0, 0, 0, 0))


def test_with_resistance_rejects_unknown_antibiotic():
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    with pytest.raises(ValueError):
        state.with_resistance("UNKNOWN", True)