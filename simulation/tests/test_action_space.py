import pytest

from simulation.action_space import ActionSpace


def test_action_space_has_seven_actions():
    action_space = ActionSpace()

    assert action_space.size == 7


def test_action_maps_to_antibiotic():
    action_space = ActionSpace()

    assert action_space.antibiotic_for(0) == "CIPROFLOXACIN"
    assert action_space.antibiotic_for(1) == "NITROFURANTOIN"
    assert action_space.antibiotic_for(2) == "FOSFOMYCIN"
    assert action_space.antibiotic_for(3) == "TRIMETHOPRIM"
    assert action_space.antibiotic_for(4) == "GENTAMICIN"
    assert action_space.antibiotic_for(5) == "MECILLINAM"
    assert action_space.antibiotic_for(6) == "CEFTAZIDIME"


def test_antibiotic_maps_to_action():
    action_space = ActionSpace()

    assert action_space.action_for("CIPROFLOXACIN") == 0
    assert action_space.action_for("NITROFURANTOIN") == 1
    assert action_space.action_for("CEFTAZIDIME") == 6


def test_action_mapping_is_reversible():
    action_space = ActionSpace()

    for action in range(action_space.size):
        antibiotic = action_space.antibiotic_for(action)
        assert action_space.action_for(antibiotic) == action


def test_negative_action_is_rejected():
    action_space = ActionSpace()

    with pytest.raises(ValueError):
        action_space.antibiotic_for(-1)


def test_out_of_range_action_is_rejected():
    action_space = ActionSpace()

    with pytest.raises(ValueError):
        action_space.antibiotic_for(7)


def test_non_integer_action_is_rejected():
    action_space = ActionSpace()

    with pytest.raises(ValueError):
        action_space.antibiotic_for("CIPROFLOXACIN")


def test_unknown_antibiotic_is_rejected():
    action_space = ActionSpace()

    with pytest.raises(ValueError):
        action_space.action_for("UNKNOWN_DRUG")