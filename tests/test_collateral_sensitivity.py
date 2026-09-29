import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.collateral_sensitivity import (
    CollateralSensitivityTransition,
)
from simulation.resistance_state import ResistanceState


def test_collateral_sensitivity_removes_target_resistance():
    state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    next_state = CollateralSensitivityTransition().apply(
        state,
        candidate,
    )

    assert next_state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )


def test_collateral_sensitivity_requires_target_resistance():
    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        CollateralSensitivityTransition().apply(
            state,
            candidate,
        )


def test_non_cs_candidate_is_rejected():
    state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        CollateralSensitivityTransition().apply(
            state,
            candidate,
        )


def test_collateral_sensitivity_does_not_mutate_original_state():
    state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    CollateralSensitivityTransition().apply(
        state,
        candidate,
    )

    assert state == ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )