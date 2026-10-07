from collections.abc import Sequence
from dataclasses import asdict, dataclass
import math
from numbers import Real
from statistics import mean, stdev

from scipy.stats import skew, t

from ml.src.multi_seed_evaluation import MultiSeedResult


METRIC_FIELDS = (
    "pooled_treatment_effectiveness_rate",
    "pooled_resistance_emergence_rate",
    "mean_episode_treatment_effectiveness_rate",
    "mean_episode_resistance_emergence_rate",
    "mean_future_effective_antibiotics",
    "mean_change_in_future_effective_antibiotics",
    "mean_cumulative_antibiotic_exposure",
    "mean_cumulative_reward",
)
ASSUMPTIONS = (
    "Run-level values, not time steps or episodes, are statistical observations.",
    "Student-t coverage assumes independent, identically distributed run-level values "
    "with an approximately normal sampling distribution for the mean.",
    "Matched initial states and seed schedules are retained; independence is not "
    "established by distinct seeds and dependence is not corrected by this method.",
    "Intervals concern simulation assumptions, not clinical or biological uncertainty.",
)


@dataclass(frozen=True)
class ConfidenceInterval:
    mean: float | None
    lower_bound: float | None
    upper_bound: float | None
    sample_count: int
    excluded_count: int
    confidence_level: float
    sample_standard_deviation: float | None
    method: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class RunMetricInterval:
    metric: str
    run_ids: tuple[int, ...]
    run_values: tuple[float | None, ...]
    contributing_run_ids: tuple[int, ...]
    excluded_run_ids: tuple[int, ...]
    interval: ConfidenceInterval


@dataclass(frozen=True)
class ConfidenceIntervalReport:
    evaluation: MultiSeedResult
    policy_name: str
    scenario_id: str
    intervals: dict[str, RunMetricInterval]
    assumptions: tuple[str, ...] = ASSUMPTIONS

    def to_dict(self) -> dict:
        """Export evaluation/grouping data and intervals without changing the source."""
        return {
            "evaluation": self.evaluation.to_dict(),
            "policy_name": self.policy_name,
            "scenario_id": self.scenario_id,
            "confidence_intervals": {
                name: asdict(record) for name, record in self.intervals.items()
            },
            "assumptions": list(self.assumptions),
        }


def _confidence_level(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("Confidence level must be a real number.")
    value = float(value)
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError("Confidence level must be finite and strictly between 0 and 1.")
    return value


def _values(values: Sequence[float | None]) -> tuple[float | None, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("Metric values must be an ordered sequence.")
    validated = []
    for value in values:
        if value is None:
            validated.append(None)
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("Metric values must be real numbers or None.")
        if not math.isfinite(value):
            raise ValueError("Metric values must be finite; only None denotes undefined.")
        validated.append(float(value))
    return tuple(validated)


def t_confidence_interval(
    values: Sequence[float | None], confidence_level: float = 0.95
) -> ConfidenceInterval:
    """Two-sided Student-t interval for the mean of equally weighted run values.

    None is excluded, never imputed. With n<2, bounds are undefined. Bounds are
    not clipped to the metric range. No RNG or resampling is used.
    """
    confidence = _confidence_level(confidence_level)
    validated = _values(values)
    observed = [value for value in validated if value is not None]
    count = len(observed)
    excluded = len(validated) - count
    limitations = []
    if excluded:
        limitations.append("undefined_runs_excluded")
    if count < 2:
        limitations.append("insufficient_runs_for_interval")
        return ConfidenceInterval(
            mean(observed) if observed else None,
            None, None, count, excluded, confidence, None, "student_t",
            tuple(limitations),
        )

    average = mean(observed)
    deviation = stdev(observed)
    critical = float(t.ppf(0.5 + confidence / 2.0, df=count - 1))
    half_width = critical * deviation / math.sqrt(count)
    lower = average - half_width
    upper = average + half_width
    if not all(math.isfinite(value) for value in (average, deviation, lower, upper)):
        raise ValueError("Interval calculation produced nonfinite values.")
    if count < 10:
        limitations.append("small_sample_fewer_than_10_runs")
    if deviation == 0.0:
        limitations.append("constant_observed_values_not_proof_of_no_uncertainty")
    elif count >= 3:
        sample_skew = float(skew(observed, bias=False))
        if math.isfinite(sample_skew) and abs(sample_skew) > 1.0:
            limitations.append("strong_sample_skew_t_approximation_may_be_unreliable")
    return ConfidenceInterval(
        average, lower, upper, count, excluded, confidence, deviation,
        "student_t", tuple(limitations),
    )


def calculate_confidence_intervals(
    evaluation: MultiSeedResult, confidence_level: float = 0.95
) -> ConfidenceIntervalReport:
    """Attach separate run-level intervals to one existing multi-seed evaluation.

    No policy comparisons, pooled trajectory resampling, or independence claims.
    The original evaluation remains accessible with its seed/grouping metadata.
    """
    confidence = _confidence_level(confidence_level)
    if not isinstance(evaluation, MultiSeedResult):
        raise TypeError("Expected a MultiSeedResult.")
    if not evaluation.runs:
        raise ValueError("A multi-seed evaluation must contain at least one run.")
    if len(evaluation.runs) != len(evaluation.seed_pairs):
        raise ValueError("Seed plan does not match the run collection.")
    first = evaluation.runs[0].metrics
    if not first.policy_name or not first.scenario_id:
        raise ValueError("Policy and scenario identity are required.")
    run_ids = tuple(run.run_id for run in evaluation.runs)
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("Run IDs must be unique.")
    for run, pair in zip(evaluation.runs, evaluation.seed_pairs):
        metrics = run.metrics
        if (run.environment_base_seed, run.policy_base_seed) != tuple(pair):
            raise ValueError("Run base seeds do not match the seed plan.")
        if (
            metrics.policy_name != first.policy_name
            or metrics.scenario_id != first.scenario_id
            or metrics.horizon != first.horizon
            or metrics.reward_specification != first.reward_specification
        ):
            raise ValueError("Run metrics have inconsistent policy, scenario, horizon, or reward weights.")
        if (
            run.evaluation.scenario_id != metrics.scenario_id
            or run.evaluation.horizon != metrics.horizon
            or run.evaluation.reward_specification != metrics.reward_specification
        ):
            raise ValueError("Run metrics do not match the evaluation configuration.")
        if tuple(episode.initial_resistance_profile for episode in run.evaluation.episodes) != evaluation.initial_resistance_profiles:
            raise ValueError("Runs must preserve the initial-profile grouping.")

    intervals = {}
    for field in METRIC_FIELDS:
        values = _values(tuple(getattr(run.metrics.summary, field) for run in evaluation.runs))
        intervals[field] = RunMetricInterval(
            metric=field,
            run_ids=run_ids,
            run_values=values,
            contributing_run_ids=tuple(run_id for run_id, value in zip(run_ids, values) if value is not None),
            excluded_run_ids=tuple(run_id for run_id, value in zip(run_ids, values) if value is None),
            interval=t_confidence_interval(values, confidence),
        )
    return ConfidenceIntervalReport(evaluation, first.policy_name, first.scenario_id, intervals)