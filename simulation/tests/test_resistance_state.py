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