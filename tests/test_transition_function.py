import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.transition_function import ResistanceTransitionFunction


def test_cross_resistance_makes_target_resistant():
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    next_state = ResistanceTransitionFunction().apply(
        state,
        candidate,
    )

    assert next_state == ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )


def test_collateral_sensitivity_makes_target_susceptible():
    state = ResistanceState((0, 0, 0, 0, 1, 0, 0))

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    next_state = ResistanceTransitionFunction().apply(
        state,
        candidate,
    )

    assert next_state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )


def test_neutral_transition_preserves_state():
    state = ResistanceState((0, 0, 0, 0, 1, 0, 0))

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="neutral",
        source_ids=("JAMES2024",),
    )

    next_state = ResistanceTransitionFunction().apply(
        state,
        candidate,
    )

    assert next_state == state


def test_unknown_transition_outcome_is_rejected():
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="something_unknown",
        source_ids=("TEST",),
    )

    with pytest.raises(ValueError):
        ResistanceTransitionFunction().apply(
            state,
            candidate,
        )


def test_transition_does_not_mutate_original_state():
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    ResistanceTransitionFunction().apply(
        state,
        candidate,
    )

    assert state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )