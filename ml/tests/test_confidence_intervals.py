from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ml.src.confidence_intervals import (
    METRIC_FIELDS, calculate_confidence_intervals, t_confidence_interval,
)
from ml.src.greedy_policy import GreedyPolicy
from ml.src.multi_seed_evaluation import run_multi_seed_evaluation
from simulation.environment import AntibioticEnvironment


def test_known_student_t_interval():
    interval = t_confidence_interval([1.0, 2.0, 3.0])
    assert interval.mean == 2.0
    assert interval.sample_count == 3
    assert interval.sample_standard_deviation == 1.0
    assert interval.lower_bound == pytest.approx(-0.4841377117)
    assert interval.upper_bound == pytest.approx(4.4841377117)
    assert interval.confidence_level == 0.95
    assert interval.method == "student_t"
    assert "small_sample_fewer_than_10_runs" in interval.limitations


def test_larger_confidence_produces_wider_interval_and_is_reproducible():
    values = [0.1, 0.2, 0.3, 0.4]
    narrow = t_confidence_interval(values, 0.90)
    wide = t_confidence_interval(values, 0.99)
    assert narrow.mean == wide.mean
    assert wide.lower_bound < narrow.lower_bound
    assert wide.upper_bound > narrow.upper_bound
    assert wide == t_confidence_interval(values, 0.99)


@pytest.mark.parametrize("values", [[], [None], [None, None]])
def test_no_valid_runs_has_no_mean_or_interval(values):
    interval = t_confidence_interval(values)
    assert interval.mean is None
    assert interval.lower_bound is None and interval.upper_bound is None
    assert interval.sample_count == 0
    assert interval.excluded_count == len(values)


def test_single_run_has_mean_but_no_bounds():
    interval = t_confidence_interval([None, 0.9])
    assert interval.mean == 0.9
    assert interval.sample_count == interval.excluded_count == 1
    assert interval.lower_bound is None and interval.upper_bound is None
    assert interval.sample_standard_deviation is None


def test_undefined_runs_excluded_without_zero_imputation():
    expected = t_confidence_interval([1.0, 2.0, 3.0])
    actual = t_confidence_interval([1.0, None, 2.0, None, 3.0])
    assert actual.mean == expected.mean
    assert actual.lower_bound == expected.lower_bound
    assert actual.upper_bound == expected.upper_bound
    assert actual.sample_count == 3 and actual.excluded_count == 2


def test_constant_values_have_zero_width_with_caveat():
    interval = t_confidence_interval([0.5] * 12)
    assert interval.mean == interval.lower_bound == interval.upper_bound == 0.5
    assert interval.sample_standard_deviation == 0.0
    assert "constant_observed_values_not_proof_of_no_uncertainty" in interval.limitations
    assert "small_sample_fewer_than_10_runs" not in interval.limitations


def test_strongly_skewed_values_flag_limitation():
    interval = t_confidence_interval([0.0] * 9 + [100.0])
    assert "strong_sample_skew_t_approximation_may_be_unreliable" in interval.limitations


def test_rate_interval_is_not_clipped_to_zero_one():
    interval = t_confidence_interval([0.0, 1.0])
    assert interval.lower_bound < 0.0
    assert interval.upper_bound > 1.0


@pytest.mark.parametrize("confidence", [0, 1, -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_confidence_values(confidence):
    with pytest.raises(ValueError):
        t_confidence_interval([1.0, 2.0], confidence)


@pytest.mark.parametrize("confidence", [True, None, "0.95"])
def test_invalid_confidence_types(confidence):
    with pytest.raises(TypeError):
        t_confidence_interval([1.0, 2.0], confidence)


@pytest.mark.parametrize("values", [[float("nan")], [float("inf")], [-float("inf")]])
def test_nonfinite_data_rejected_not_excluded(values):
    with pytest.raises(ValueError):
        t_confidence_interval(values)


@pytest.mark.parametrize("values", [[True], ["1"], "123", None])
def test_malformed_data_rejected(values):
    with pytest.raises(TypeError):
        t_confidence_interval(values)


@pytest.fixture
def multi_seed_result():
    return run_multi_seed_evaluation(
        lambda: AntibioticEnvironment(max_steps=2), GreedyPolicy,
        [(10, 100), (20, 200), (30, 300)],
        initial_states=[(0,) * 7, (1,) * 7],
    )


def test_report_has_one_observation_per_run_and_preserves_grouping(multi_seed_result):
    before = deepcopy(multi_seed_result)
    report = calculate_confidence_intervals(multi_seed_result)
    assert report.evaluation is multi_seed_result
    assert set(report.intervals) == set(METRIC_FIELDS)
    assert report.policy_name.endswith("GreedyPolicy")
    assert report.scenario_id == "REF_UNIFORM_SUPPORTED"
    for name, record in report.intervals.items():
        assert record.run_ids == (0, 1, 2)
        assert record.run_values == tuple(getattr(run.metrics.summary, name) for run in multi_seed_result.runs)
        assert record.interval.sample_count == 3
        assert record.interval.mean == pytest.approx(sum(record.run_values) / 3)
    assert report == calculate_confidence_intervals(multi_seed_result)
    assert multi_seed_result == before
    exported = report.to_dict()
    json.dumps(exported, allow_nan=False)
    assert exported["evaluation"]["runs"][0]["episode_identities"] == ((0, 0), (0, 1))
    exported["evaluation"]["environment_configuration"]["horizon"] = 99
    assert multi_seed_result.environment_configuration["horizon"] == 2


def test_zero_step_runs_have_undefined_rate_intervals_but_defined_endpoint_intervals():
    result = run_multi_seed_evaluation(
        AntibioticEnvironment, GreedyPolicy, [(1, 1), (2, 2)],
        initial_states=[(1,) * 7],
    )
    report = calculate_confidence_intervals(result)
    rate = report.intervals["pooled_treatment_effectiveness_rate"]
    assert rate.interval.sample_count == 0
    assert rate.excluded_run_ids == (0, 1)
    assert rate.interval.mean is None
    endpoint = report.intervals["mean_future_effective_antibiotics"].interval
    assert endpoint.sample_count == 2
    assert endpoint.mean == endpoint.lower_bound == endpoint.upper_bound == 0.0


def test_undefined_rates_preserve_contributor_ids(multi_seed_result):
    runs = list(multi_seed_result.runs)
    metrics = runs[1].metrics
    summary = replace(metrics.summary, pooled_treatment_effectiveness_rate=None)
    runs[1] = replace(runs[1], metrics=replace(metrics, summary=summary))
    report = calculate_confidence_intervals(replace(multi_seed_result, runs=tuple(runs)))
    record = report.intervals["pooled_treatment_effectiveness_rate"]
    assert record.contributing_run_ids == (0, 2)
    assert record.excluded_run_ids == (1,)
    assert record.interval.sample_count == 2


@pytest.mark.parametrize("field", ["policy_name", "scenario_id", "horizon", "reward_weights"])
def test_inconsistent_run_configuration_rejected(multi_seed_result, field):
    run = multi_seed_result.runs[1]
    new_value = {"policy_name": "OTHER", "scenario_id": "OTHER", "horizon": 99, "reward_weights": {}}[field]
    run = replace(run, metrics=replace(run.metrics, **{field: new_value}))
    altered = replace(multi_seed_result, runs=(multi_seed_result.runs[0], run, multi_seed_result.runs[2]))
    with pytest.raises(ValueError, match="inconsistent"):
        calculate_confidence_intervals(altered)


def test_malformed_run_collection_rejected(multi_seed_result):
    with pytest.raises(ValueError):
        calculate_confidence_intervals(replace(multi_seed_result, runs=()))
    with pytest.raises(ValueError, match="unique"):
        calculate_confidence_intervals(replace(multi_seed_result, runs=(multi_seed_result.runs[0],) * 3))
    with pytest.raises(ValueError, match="seed plan"):
        calculate_confidence_intervals(replace(multi_seed_result, seed_pairs=((99, 99),) * 3))