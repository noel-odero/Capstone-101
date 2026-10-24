import random

import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.transition_sampler import (
    REFERENCE_SCENARIO_ID,
    SENSITIVITY_SCENARIOS,
    SampledTransition,
    TransitionSampler,
)


def test_single_candidate_is_selected():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    result = TransitionSampler().sample(
        (candidate,),
        seed=42,
    )

    assert isinstance(result, SampledTransition)
    assert result.candidate == candidate
    assert result.probability == 1.0
    assert result.scenario_id == REFERENCE_SCENARIO_ID
    assert result.candidates == (candidate,)


def test_empty_candidates_report_unsupported_status():
    result = TransitionSampler().sample((), seed=42)

    assert result.candidate is None
    assert result.status == "unsupported_no_candidate"
    assert result.no_transition_probability is None
    assert result.candidates == ()


def test_multiple_candidates_are_sampled():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    result = TransitionSampler().sample(
        (candidate_one, candidate_two),
        seed=42,
    )

    assert result.candidate in {
        candidate_one,
        candidate_two,
    }

    assert result.probability == 0.5
    assert result.scenario_id == REFERENCE_SCENARIO_ID
    assert result.candidates == (
        candidate_one,
        candidate_two,
    )
    assert sum(result.candidate_probabilities) + result.no_transition_probability == 1.0


def test_same_seed_reproduces_same_selection():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    result_one = TransitionSampler().sample(
        (candidate_one, candidate_two),
        seed=42,
    )

    result_two = TransitionSampler().sample(
        (candidate_one, candidate_two),
        seed=42,
    )

    assert result_one == result_two


def test_different_seeds_can_produce_different_selection():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    selections = {
        TransitionSampler().sample(
            (candidate_one, candidate_two),
            seed=seed,
        ).candidate
        for seed in range(20)
    }

    assert selections == {
        candidate_one,
        candidate_two,
    }


def test_duplicate_candidates_are_deduplicated():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    candidate_duplicate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("SAKENOVA2025",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    result = TransitionSampler().sample(
        (
            candidate_one,
            candidate_duplicate,
            candidate_two,
        ),
        seed=42,
    )

    assert len(result.candidates) == 2
    assert result.probability == 0.5
    assert sum(result.candidate_probabilities) == 1.0

    gentamicin_candidates = [
        candidate
        for candidate in result.candidates
        if candidate.target_drug == "GENTAMICIN"
        and candidate.outcome == "cross_resistance"
    ]

    assert len(gentamicin_candidates) == 1
    assert gentamicin_candidates[0].source_ids == (
        "POD2018",
        "SAKENOVA2025",
    )


def test_duplicate_evidence_does_not_create_extra_probability_mass():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    duplicate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("SAKENOVA2025",),
    )

    duplicate_two = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("JAMES2024",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    result = TransitionSampler().sample(
        (
            candidate_one,
            duplicate_one,
            duplicate_two,
            candidate_two,
        ),
        seed=42,
    )

    assert len(result.candidates) == 2
    assert result.probability == 0.5


def test_source_ids_are_sorted_after_merging():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("Z_SOURCE",),
    )

    candidate_two = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("A_SOURCE",),
    )

    result = TransitionSampler().sample(
        (candidate_one, candidate_two),
        seed=42,
    )

    assert result.candidates[0].source_ids == (
        "A_SOURCE",
        "Z_SOURCE",
    )


def test_persistent_rng_produces_reproducible_sequence():
    candidate_one = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    candidate_two = CandidateTransition(
        target_drug="FOSFOMYCIN",
        outcome="collateral_sensitivity",
        source_ids=("POD2018",),
    )

    rng_one = random.Random(42)
    rng_two = random.Random(42)

    sampler = TransitionSampler()

    sequence_one = tuple(
        sampler.sample(
            (candidate_one, candidate_two),
            rng=rng_one,
        ).candidate
        for _ in range(10)
    )

    sequence_two = tuple(
        sampler.sample(
            (candidate_one, candidate_two),
            rng=rng_two,
        ).candidate
        for _ in range(10)
    )

    assert sequence_one == sequence_two


def test_seed_and_rng_cannot_be_used_together():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    with pytest.raises(ValueError):
        TransitionSampler().sample(
            (candidate,),
            seed=42,
            rng=random.Random(42),
        )


@pytest.mark.parametrize(
    ("scenario_id", "occurrence_probability"),
    SENSITIVITY_SCENARIOS.items(),
)
def test_sensitivity_probabilities_sum_to_one(
    scenario_id,
    occurrence_probability,
):
    candidates = (
        CandidateTransition("GENTAMICIN", "cross_resistance", ("A",)),
        CandidateTransition("FOSFOMYCIN", "collateral_sensitivity", ("B",)),
        CandidateTransition("TRIMETHOPRIM", "neutral", ("C",)),
    )

    result = TransitionSampler(scenario_id).sample(candidates, seed=11)

    assert result.occurrence_probability == occurrence_probability
    assert sum(result.candidate_probabilities) + result.no_transition_probability == pytest.approx(1.0)
    assert result.candidate_probabilities[-1] == 0.0


def test_sensitivity_q_zero_never_changes_resistance():
    candidate = CandidateTransition("GENTAMICIN", "cross_resistance", ("A",))

    result = TransitionSampler("SENSITIVITY_Q_000").sample(
        (candidate,),
        seed=42,
    )

    assert result.candidate is None
    assert result.status == "no_transition"
    assert result.no_transition_probability == 1.0
    assert result.candidate_probabilities == (0.0,)


def test_sensitivity_q_one_selects_resistance_candidate_not_neutral():
    resistance_candidate = CandidateTransition(
        "GENTAMICIN", "cross_resistance", ("A",)
    )
    second_resistance_candidate = CandidateTransition(
        "NITROFURANTOIN", "collateral_sensitivity", ("C",)
    )
    neutral_candidate = CandidateTransition("FOSFOMYCIN", "neutral", ("B",))

    result = TransitionSampler("SENSITIVITY_Q_100").sample(
        (
            resistance_candidate,
            second_resistance_candidate,
            neutral_candidate,
        ),
        seed=42,
    )

    assert result.candidate in {
        resistance_candidate,
        second_resistance_candidate,
    }
    assert result.status in {
        "cross_resistance",
        "collateral_sensitivity",
    }
    assert result.candidate_probabilities == (0.5, 0.5, 0.0)


def test_sensitivity_neutral_only_is_a_supported_neutral_outcome():
    candidate = CandidateTransition("FOSFOMYCIN", "neutral", ("JAMES2024",))

    result = TransitionSampler("SENSITIVITY_Q_025").sample(
        (candidate,),
        seed=42,
    )

    assert result.candidate == candidate
    assert result.status == "neutral"
    assert result.probability == 1.0


def test_invalid_scenario_is_rejected():
    with pytest.raises(ValueError, match="Unknown transition scenario"):
        TransitionSampler("SENSITIVITY_Q_030")


def test_sensitivity_frequency_is_consistent_with_assumption():
    candidate = CandidateTransition("GENTAMICIN", "cross_resistance", ("A",))
    results = [
        TransitionSampler("SENSITIVITY_Q_050").sample(
            (candidate,),
            seed=seed,
        )
        for seed in range(1000)
    ]
    occurrences = sum(result.status == "cross_resistance" for result in results)

    assert 450 <= occurrences <= 550


def test_sensitivity_scenario_reproduces_with_same_seed():
    candidates = (
        CandidateTransition("GENTAMICIN", "cross_resistance", ("A",)),
        CandidateTransition("FOSFOMYCIN", "collateral_sensitivity", ("B",)),
    )

    first = TransitionSampler("SENSITIVITY_Q_050").sample(
        candidates,
        seed=84,
    )
    second = TransitionSampler("SENSITIVITY_Q_050").sample(
        candidates,
        seed=84,
    )

    assert first == second