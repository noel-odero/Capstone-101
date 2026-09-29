import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.cross_resistance import CrossResistanceTransition
from simulation.resistance_state import ResistanceState


def test_cross_resistance_adds_target_resistance():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    next_state = CrossResistanceTransition().apply(
        state,
        candidate,
    )

    assert next_state == ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )


def test_cross_resistance_requires_target_susceptibility():
    state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        CrossResistanceTransition().apply(
            state,
            candidate,
        )


def test_non_cr_candidate_is_rejected():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        CrossResistanceTransition().apply(
            state,
            candidate,
        )


def test_cross_resistance_does_not_mutate_original_state():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    CrossResistanceTransition().apply(
        state,
        candidate,
    )

    assert state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )