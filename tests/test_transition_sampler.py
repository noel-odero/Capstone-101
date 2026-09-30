import random

import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.transition_sampler import (
    REFERENCE_SCENARIO_ID,
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


def test_empty_candidates_are_rejected():
    with pytest.raises(ValueError):
        TransitionSampler().sample(
            (),
            seed=42,
        )


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