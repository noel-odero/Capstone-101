import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.transition_sampler import (
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


def test_empty_candidates_are_rejected():
    with pytest.raises(ValueError):
        TransitionSampler().sample(
            (),
            seed=42,
        )


def test_multiple_candidates_are_rejected_until_probabilities_are_configured():
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

    with pytest.raises(ValueError):
        TransitionSampler().sample(
            (candidate_one, candidate_two),
            seed=42,
        )


def test_seed_does_not_change_single_candidate_selection():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("POD2018",),
    )

    result_one = TransitionSampler().sample(
        (candidate,),
        seed=1,
    )

    result_two = TransitionSampler().sample(
        (candidate,),
        seed=999,
    )

    assert result_one == result_two