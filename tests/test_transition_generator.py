from simulation.candidate_transition import CandidateTransition
from simulation.transition_generator import CandidateTransitionGenerator
from simulation.resistance_state import ResistanceState


def test_cross_resistance_generates_candidate():
    generator = CandidateTransitionGenerator()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidates = generator.generate(
        state,
        action=0,
    )

    assert CandidateTransition(
        target_drug="CEFTAZIDIME",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    ) in candidates


def test_collateral_sensitivity_generates_candidate_when_target_is_resistant():
    generator = CandidateTransitionGenerator()

    state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    candidates = generator.generate(
        state,
        action=0,
    )

    assert CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    ) in candidates


def test_collateral_sensitivity_does_not_generate_when_target_is_susceptible():
    generator = CandidateTransitionGenerator()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidates = generator.generate(
        state,
        action=0,
    )

    assert not any(
        candidate.target_drug == "GENTAMICIN"
        and candidate.outcome == "collateral_sensitivity"
        for candidate in candidates
    )


def test_cross_resistance_does_not_generate_when_target_is_already_resistant():
    generator = CandidateTransitionGenerator()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 1)
    )

    candidates = generator.generate(
        state,
        action=0,
    )

    assert not any(
        candidate.target_drug == "CEFTAZIDIME"
        and candidate.outcome == "cross_resistance"
        for candidate in candidates
    )


def test_unknown_directionality_is_not_used_as_sequential_transition():
    generator = CandidateTransitionGenerator()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    candidates = generator.generate(
        state,
        action=6,
    )

    assert not any(
        candidate.source_ids == ("SAK2025",)
        for candidate in candidates
    )