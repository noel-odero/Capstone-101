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


def test_public_measurements_supply_candidates_for_previously_missing_origins():
    generator = CandidateTransitionGenerator()
    cases = (
        ((0, 0, 0, 1, 0, 0, 0), 2, "TRIMETHOPRIM", "collateral_sensitivity", "SAK2025_EXP"),
        ((0,) * 7, 4, "FOSFOMYCIN", "cross_resistance", "IBACACHE2018"),
        ((0,) * 7, 6, "CIPROFLOXACIN", "cross_resistance", "PHILLIPS2026"),
    )
    for profile, action, target, outcome, source in cases:
        assert CandidateTransition(target, outcome, (source,)) in generator.generate(ResistanceState(profile), action)


def test_mixed_lineage_outcomes_remain_distinct_and_support_is_merged():
    from simulation.transition_sampler import TransitionSampler

    generator = CandidateTransitionGenerator()
    state = ResistanceState((0, 0, 0, 1, 0, 0, 0))
    result = TransitionSampler().sample(generator.generate(state, action=5), seed=1)
    tmp = [candidate for candidate in result.candidates if candidate.target_drug == "TRIMETHOPRIM"]
    assert {candidate.outcome for candidate in tmp} == {"neutral", "collateral_sensitivity"}

    state = ResistanceState((0,) * 7)
    result = TransitionSampler().sample(generator.generate(state, action=5), seed=1)
    tmp = [candidate for candidate in result.candidates if candidate.target_drug == "TRIMETHOPRIM"]
    assert len(tmp) == 2
    cross_resistance = next(candidate for candidate in tmp if candidate.outcome == "cross_resistance")
    assert cross_resistance.source_ids == ("POD2018", "SAK2025_EXP")
