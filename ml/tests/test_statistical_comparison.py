from copy import deepcopy
from dataclasses import replace
from itertools import product
import json

import numpy as np
import pytest
from scipy.stats import rankdata

from ml.src.evaluation_runner import EpisodeResult, EvaluationResult, StepResult
from ml.src.metrics import calculate_metrics
from ml.src.multi_seed_evaluation import MultiSeedResult, SeedRunResult
from ml.src.multi_seed_evaluation import run_multi_seed_evaluation
from ml.src.greedy_policy import GreedyPolicy
from ml.src.random_policy import RandomPolicy
from simulation.environment import AntibioticEnvironment
from ml.src.statistical_comparison import (
    ComparisonConfig, adjust_holm, compare_paired_metric, compare_strategies,
    match_run_pairs, paired_bootstrap_interval,
)


def make_result(name, effective_counts, *, profile=(0,) * 7, run_ids=None):
    weights = {"effectiveness": 1.0, "resistance": 0.5, "exposure": 0.1}
    configuration = {
        "scenario_id": "TEST", "horizon": 4, "reward_weights": weights,
        "interaction_data_sha256": "fixed_fixture", "action_mappings": list(range(7)),
    }
    runs = []
    seeds = []
    for index, count in enumerate(effective_counts):
        base = 10 * (index + 1)
        observations = [tuple(profile) + (0,) * 7 + (step,) for step in range(5)]
        steps = tuple(StepResult(
            observations[step], 0, observations[step + 1], float(count), step == 3, False,
            {"effective": step < count, "scenario_id": "TEST"},
        ) for step in range(4))
        episode = EpisodeResult(
            0, base, base + 100, name, profile, profile, observations[0], {},
            steps, True, False, "maximum_horizon",
        )
        evaluation = EvaluationResult("TEST", 4, weights.copy(), (episode,))
        run_id = index if run_ids is None else run_ids[index]
        runs.append(SeedRunResult(run_id, base, base + 100, evaluation, calculate_metrics(evaluation)))
        seeds.append((base, base + 100))
    return MultiSeedResult(tuple(seeds), (profile,), configuration, tuple(runs))


def inference_config(**kwargs):
    return ComparisonConfig(
        independent_runs_assumed=True, symmetric_differences_assumed=True,
        bootstrap_resamples=200, permutation_resamples=199, **kwargs,
    )


def test_pairing_uses_seed_design_not_positional_ids():
    first = make_result("A", [2, 3, 1])
    second = make_result("B", [1, 2, 0], run_ids=[90, 80, 70])
    second = replace(second, runs=tuple(reversed(second.runs)), seed_pairs=tuple(reversed(second.seed_pairs)))
    matched = match_run_pairs(first, second)
    assert [(pair.run_a.run_id, pair.run_b.run_id) for pair in matched.pairs] == [(0, 90), (1, 80), (2, 70)]


def test_missing_runs_strict_and_explicit_intersection():
    first = make_result("A", [2, 3, 1])
    second = make_result("B", [1, 2])
    with pytest.raises(ValueError, match="Unmatched"):
        match_run_pairs(first, second)
    matched = match_run_pairs(first, second, allow_missing=True)
    assert len(matched.pairs) == 2
    assert matched.unmatched_a == ((30, 130),)


def test_configuration_and_profiles_not_silently_pooled():
    first = make_result("A", [2])
    second = make_result("B", [1])
    changed = deepcopy(second.environment_configuration)
    changed["interaction_data_sha256"] = "changed"
    with pytest.raises(ValueError, match="configuration"):
        match_run_pairs(first, replace(second, environment_configuration=changed))
    with pytest.raises(ValueError, match="profile"):
        match_run_pairs(first, make_result("B", [1], profile=(1, 0, 0, 0, 0, 0, 0)))


def test_duplicate_and_corrupt_metrics_rejected():
    first = make_result("A", [2, 3])
    duplicate = replace(first, runs=(first.runs[0], first.runs[0]), seed_pairs=(first.seed_pairs[0],) * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        match_run_pairs(duplicate, first)
    run = first.runs[0]
    metrics = replace(run.metrics, summary=replace(run.metrics.summary, mean_cumulative_reward=999))
    with pytest.raises(ValueError, match="Stored metrics"):
        match_run_pairs(replace(first, runs=(replace(run, metrics=metrics), first.runs[1])), first)


def test_original_unit_mean_and_median_and_conservative_withholding():
    matched = match_run_pairs(make_result("A", [4, 2, 1]), make_result("B", [2, 1, 1]))
    result = compare_paired_metric(matched, "treatment_effectiveness_rate", strategy_a="A", strategy_b="B")
    assert result.mean_difference == pytest.approx(0.25)
    assert result.median_difference == 0.25
    assert result.zero_count == 1
    assert result.sample_count == 3
    assert result.raw_p_value is None
    assert result.bootstrap.mean_lower is None
    assert "independence" in result.test_status


def test_wilcoxon_ties_zeros_match_exhaustive_sign_flip_calculation():
    differences = np.array([0.0, 0.25, 0.25, 0.25, -0.25, -0.25, -0.25])
    a = make_result("A", [1, 2, 2, 2, 0, 0, 0])
    b = make_result("B", [1] * 7)
    result = compare_paired_metric(match_run_pairs(a, b), "treatment_effectiveness_rate",
                                   strategy_a="A", strategy_b="B", config=inference_config())
    ranks = rankdata(np.abs(differences))
    observed_positive = np.sum(ranks[differences > 0])
    possible = [sum(rank for rank, sign in zip(ranks[1:], signs) if sign > 0)
                for signs in product((-1, 1), repeat=6)]
    expected = min(1.0, 2 * min(
        sum(value <= observed_positive for value in possible) / len(possible),
        sum(value >= observed_positive for value in possible) / len(possible),
    ))
    assert result.raw_p_value == pytest.approx(expected)
    assert result.zero_count == 1 and result.nonzero_count == 6
    assert result.tied_absolute_difference_count == 5
    assert "exhaustive" in result.test_method


def test_all_zero_and_small_samples_withhold_tests():
    for counts, expected in [([1] * 7, "all_zero"), ([2] * 3, "insufficient")]:
        matched = match_run_pairs(make_result("A", counts), make_result("B", [1] * len(counts)))
        result = compare_paired_metric(matched, "treatment_effectiveness_rate",
                                      strategy_a="A", strategy_b="B", config=inference_config())
        assert result.raw_p_value is None
        assert expected in result.test_status


def test_seeded_permutation_branch_is_reproducible():
    matched = match_run_pairs(
        make_result("A", [2] * 9 + [0] * 8), make_result("B", [1] * 17),
    )
    config = inference_config(permutation_seed=42)
    first = compare_paired_metric(
        matched, "treatment_effectiveness_rate", strategy_a="A", strategy_b="B", config=config,
    )
    second = compare_paired_metric(
        matched, "treatment_effectiveness_rate", strategy_a="A", strategy_b="B", config=config,
    )
    assert first == second
    assert first.test_method == "wilcoxon_pratt_seeded_sign_permutation"
    assert 0 <= first.raw_p_value <= 1


def test_real_pipeline_pairs_runs_not_individual_episodes():
    seed_pairs = [(10, 100), (20, 200)]
    profiles = [(0,) * 7, (1,) * 7]
    def factory():
        return AntibioticEnvironment(max_steps=2)

    inputs = {
        "random": run_multi_seed_evaluation(factory, RandomPolicy, seed_pairs, initial_states=profiles),
        "greedy": run_multi_seed_evaluation(factory, GreedyPolicy, seed_pairs, initial_states=profiles),
    }
    report = compare_strategies(inputs, [("random", "greedy")], family_id="real_primary")
    assert report.family_size == 4
    for comparison in report.comparisons:
        assert comparison.matched_pairs == comparison.sample_count == 2
        assert len(comparison.pair_records[0]["episode_ids_a"]) == 2
        assert comparison.raw_p_value is None
    assert report.scenario_id == "REF_UNIFORM_SUPPORTED"
    json.dumps(report.to_dict(), allow_nan=False)


def test_symmetry_assumption_and_skew_diagnostic_gate_inference():
    matched = match_run_pairs(make_result("A", [2] * 6), make_result("B", [1] * 6))
    config = ComparisonConfig(independent_runs_assumed=True, bootstrap_resamples=50)
    result = compare_paired_metric(matched, "treatment_effectiveness_rate", strategy_a="A", strategy_b="B", config=config)
    assert "symmetry" in result.test_status and result.raw_p_value is None
    matched = match_run_pairs(make_result("A", [2] * 9 + [4]), make_result("B", [1] * 10))
    result = compare_paired_metric(matched, "treatment_effectiveness_rate", strategy_a="A", strategy_b="B", config=inference_config())
    assert "skew" in result.test_status and result.raw_p_value is None


def test_seeded_pair_bootstrap_matches_direct_complete_pair_resampling():
    values = [-1.0, 0.0, 2.0, 4.0]
    result = paired_bootstrap_interval(values, seed=42, resamples=100, independent_runs_assumed=True)
    sampled = np.asarray(values)[np.random.default_rng(42).integers(0, 4, size=(100, 4))]
    means = np.quantile(np.mean(sampled, axis=1), [.025, .975])
    medians = np.quantile(np.median(sampled, axis=1), [.025, .975])
    assert (result.mean_lower, result.mean_upper) == pytest.approx(means)
    assert (result.median_lower, result.median_upper) == pytest.approx(medians)
    assert result == paired_bootstrap_interval(values, seed=42, resamples=100, independent_runs_assumed=True)


def test_bootstrap_insufficient_and_zero_differences():
    assert paired_bootstrap_interval([1.0], seed=1, independent_runs_assumed=True).mean_lower is None
    assert paired_bootstrap_interval([1.0, 2.0], seed=1).mean_lower is None
    zero = paired_bootstrap_interval([0.0] * 4, seed=1, resamples=20, independent_runs_assumed=True)
    assert zero.mean_lower == zero.mean_upper == zero.median_lower == zero.median_upper == 0.0


def test_holm_known_family_and_untested_slots():
    assert adjust_holm([0.01, 0.04, 0.03, None]) == pytest.approx((0.04, 0.09, 0.09, None))
    assert adjust_holm([]) == ()
    with pytest.raises(ValueError):
        adjust_holm([float("nan")])


def test_family_report_reproducible_export_and_no_mutation():
    inputs = {"A": make_result("A", [3] * 9), "B": make_result("B", [1] * 9)}
    before = deepcopy(inputs)
    config = inference_config()
    report = compare_strategies(inputs, [("A", "B")], family_id="primary_TEST", config=config)
    assert report == compare_strategies(inputs, [("A", "B")], family_id="primary_TEST", config=config)
    assert inputs == before
    assert report.family_size == 4
    assert len(report.comparisons) == 4
    ter = report.comparisons[0]
    assert ter.mean_difference == 0.5
    assert ter.raw_p_value == pytest.approx(2 / 512)
    assert ter.adjusted_p_value == pytest.approx(4 * ter.raw_p_value)
    assert ter.reject_null is True
    assert ter.pair_records[0]["episode_ids_a"] == ((0, 0),)
    assert report.software_versions["scipy"]
    assert report.input_sha256["A"] != report.input_sha256["B"]
    json.dumps(report.to_dict(), allow_nan=False)


def test_undefined_run_rates_remain_missing_not_zero():
    a = make_result("A", [1, 1])
    b = make_result("B", [1, 1])
    def zero_steps(source):
        runs = []
        for run in source.runs:
            episode = replace(run.evaluation.episodes[0], steps=(), termination_reason="no_effective_antibiotic")
            evaluation = replace(run.evaluation, episodes=(episode,))
            runs.append(replace(run, evaluation=evaluation, metrics=calculate_metrics(evaluation)))
        return replace(source, runs=tuple(runs))
    result = compare_paired_metric(match_run_pairs(zero_steps(a), zero_steps(b)),
                                  "treatment_effectiveness_rate", strategy_a="A", strategy_b="B", config=inference_config())
    assert result.sample_count == 0 and result.matched_pairs == 2
    assert result.mean_difference is None
    assert result.pair_records[0]["missing_a"] and result.pair_records[0]["missing_b"]


@pytest.mark.parametrize("kwargs", [
    {"alpha": 0}, {"confidence_level": 1}, {"bootstrap_seed": -1},
    {"rank_decimal_places": 16}, {"minimum_nonzero_pairs": 1},
    {"bootstrap_resamples": 1},
])
def test_invalid_test_configuration(kwargs):
    with pytest.raises(ValueError):
        ComparisonConfig(**kwargs)


def test_duplicate_contrasts_and_cross_scenario_family_rejected():
    inputs = {"A": make_result("A", [1]), "B": make_result("B", [2])}
    with pytest.raises(ValueError, match="Duplicate"):
        compare_strategies(inputs, [("A", "B"), ("B", "A")], family_id="TEST")
    changed = deepcopy(inputs["B"].environment_configuration)
    changed["scenario_id"] = "SENSITIVITY"
    inputs["B"] = replace(inputs["B"], environment_configuration=changed)
    with pytest.raises(ValueError):
        compare_strategies(inputs, [("A", "B")], family_id="TEST")