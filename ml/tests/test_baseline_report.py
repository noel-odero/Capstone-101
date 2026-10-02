from copy import deepcopy
import json
from pathlib import Path

import pytest

from ml.src.baseline_report import generate_baseline_report, render_baseline_report


@pytest.fixture
def plan():
    path = Path(__file__).resolve().parents[2] / "experiments" / "baseline_config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update({
        "run_count": 2, "horizon": 2, "bootstrap_resamples": 30,
        "initial_profile_design": "explicit", "initial_profiles": [[0] * 7, [1] * 7],
        "scenarios": ["REF_UNIFORM_SUPPORTED", "SENSITIVITY_Q_025"],
    })
    return config


def test_report_reproducible_complete_and_does_not_mutate_plan(plan):
    before = deepcopy(plan)
    first = generate_baseline_report(plan)
    second = generate_baseline_report(plan)
    assert first == second
    assert plan == before
    assert set(first["stochastic_scenarios"]) == set(plan["scenarios"])
    for scenario, section in first["stochastic_scenarios"].items():
        assert set(section["policies"]) == {"random", "greedy"}
        for policy in section["policies"].values():
            assert len(policy["evaluation"]["runs"]) == 2
            assert policy["uncertainty"]["scenario_id"] == scenario
            assert policy["uncertainty"]["confidence_intervals"]["mean_cumulative_reward"]["interval"]["sample_count"] == 2
        assert all(result["raw_p_value"] is None for result in section["comparison"]["comparisons"])
    exact = first["exact_reference"]
    assert exact["metrics"]["policy_name"] == "exact_reference_value_iteration"
    for item, episode in zip(exact["initial_state_values"], exact["metrics"]["episodes"]):
        assert item["optimal_value"] == pytest.approx(episode["cumulative_reward"])
    assert exact["metrics"]["episodes"][1]["cumulative_antibiotic_exposure"] == 0
    assert exact["planning_state_count"] == 128 * 3
    json.dumps(first, allow_nan=False)
    markdown = render_baseline_report(first)
    assert markdown == render_baseline_report(second)
    for text in ("Random", "Greedy", "Exact Deterministic", "bootstrap", "Pooled Rates", "not perfectly paired", "not a stochastic optimality benchmark"):
        assert text in markdown


def test_report_covers_all_binary_profiles(plan):
    plan.update({"initial_profile_design": "all_binary", "run_count": 1, "horizon": 1, "scenarios": ["REF_UNIFORM_SUPPORTED"]})
    report = generate_baseline_report(plan)
    assert len(set(report["initial_profiles"])) == 128
    assert report["initial_profiles"][0] == (0,) * 7
    assert report["initial_profiles"][-1] == (1,) * 7
    assert report["exact_reference"]["metrics"]["summary"]["episode_count"] == 128


@pytest.mark.parametrize(("field", "value"), [
    ("run_count", 0), ("run_count", True), ("horizon", 0),
    ("gamma", 0.9), ("environment_seed_start", -1),
    ("scenarios", ["UNKNOWN"]), ("scenarios", []),
    ("initial_profile_design", "clinical_distribution"),
])
def test_invalid_plan_rejected(plan, field, value):
    plan[field] = value
    with pytest.raises(ValueError):
        generate_baseline_report(plan)