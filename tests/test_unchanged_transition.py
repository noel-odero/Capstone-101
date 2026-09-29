import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.unchanged_transition import UnchangedStateTransition


def test_neutral_transition_preserves_state():
    state = ResistanceState(
        (0, 0, 1, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="neutral",
        source_ids=("JAMES2024",),
    )

    next_state = UnchangedStateTransition().apply(
        state,
        candidate,
    )

    assert next_state == state


def test_neutral_transition_does_not_change_resistance_values():
    state = ResistanceState(
        (1, 0, 1, 0, 0, 1, 0)
    )

    candidate = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="neutral",
        source_ids=("JAMES2024",),
    )

    next_state = UnchangedStateTransition().apply(
        state,
        candidate,
    )

    assert next_state.resistance == (
        1, 0, 1, 0, 0, 1, 0
    )


def test_non_neutral_candidate_is_rejected():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        UnchangedStateTransition().apply(
            state,
            candidate,
        )


def test_neutral_transition_does_not_mutate_state():
    state = ResistanceState(
        (0, 0, 1, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="neutral",
        source_ids=("JAMES2024",),
    )

    UnchangedStateTransition().apply(
        state,
        candidate,
    )

    assert state == ResistanceState(
        (0, 0, 1, 0, 1, 0, 0)
    )