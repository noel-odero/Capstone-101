from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from numbers import Real
import platform

import numpy as np
import scipy
from scipy.stats import PermutationMethod, skew, wilcoxon

from ml.src.metrics import calculate_metrics
from ml.src.multi_seed_evaluation import MultiSeedResult, SeedRunResult


PRIMARY_METRICS = {
    "treatment_effectiveness_rate": ("mean_episode_treatment_effectiveness_rate", "higher", "proportion"),
    "resistance_emergence_rate": ("mean_episode_resistance_emergence_rate", "lower", "proportion"),
    "future_effective_antibiotics": ("mean_future_effective_antibiotics", "higher", "antibiotics"),
    "cumulative_antibiotic_exposure": ("mean_cumulative_antibiotic_exposure", "context_dependent", "actions"),
}


@dataclass(frozen=True)
class ComparisonConfig:
    independent_runs_assumed: bool = False
    symmetric_differences_assumed: bool = False
    confidence_level: float = 0.95
    alpha: float = 0.05
    bootstrap_resamples: int = 10000
    permutation_resamples: int = 9999
    bootstrap_seed: int = 0
    permutation_seed: int = 1
    rank_decimal_places: int = 12
    minimum_nonzero_pairs: int = 6
    allow_missing_pairs: bool = False

    def __post_init__(self):
        for name in ("independent_runs_assumed", "symmetric_differences_assumed", "allow_missing_pairs"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean.")
        for name in ("confidence_level", "alpha"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(f"{name} must be a real number.")
            if not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"{name} must be finite and strictly between 0 and 1.")
        for name, minimum in (
            ("bootstrap_resamples", 2), ("permutation_resamples", 2),
            ("bootstrap_seed", 0), ("permutation_seed", 0),
            ("rank_decimal_places", 0), ("minimum_nonzero_pairs", 2),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")
            if value < minimum:
                raise ValueError(f"{name} must be at least {minimum}.")
        if self.rank_decimal_places > 15:
            raise ValueError("rank_decimal_places must not exceed 15.")


@dataclass(frozen=True)
class RunPair:
    environment_base_seed: int
    policy_base_seed: int
    run_a: SeedRunResult
    run_b: SeedRunResult


@dataclass(frozen=True)
class MatchedRuns:
    pairs: tuple[RunPair, ...]
    unmatched_a: tuple[tuple[int, int], ...]
    unmatched_b: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class BootstrapIntervals:
    mean_lower: float | None
    mean_upper: float | None
    median_lower: float | None
    median_upper: float | None
    sample_count: int
    resamples: int
    seed: int
    confidence_level: float
    method: str = "paired_run_percentile"


@dataclass(frozen=True)
class PairedMetricComparison:
    strategy_a: str
    strategy_b: str
    metric: str
    units: str
    interpretation: str
    matched_pairs: int
    sample_count: int
    zero_count: int
    nonzero_count: int
    tied_absolute_difference_count: int
    mean_difference: float | None
    median_difference: float | None
    bootstrap: BootstrapIntervals
    statistic: float | None
    raw_p_value: float | None
    adjusted_p_value: float | None
    reject_null: bool | None
    test_method: str | None
    test_status: str
    limitations: tuple[str, ...]
    pair_records: tuple[dict, ...]
    bootstrap_seed: int
    permutation_seed: int


@dataclass(frozen=True)
class StatisticalComparisonReport:
    scenario_id: str
    family_id: str
    contrasts: tuple[tuple[str, str], ...]
    family_size: int
    config: ComparisonConfig
    configuration_sha256: str
    input_sha256: dict[str, str]
    software_versions: dict[str, str]
    comparisons: tuple[PairedMetricComparison, ...]
    matching: dict[str, dict]
    evaluations: dict[str, MultiSeedResult]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["evaluations"] = {name: value.to_dict() for name, value in self.evaluations.items()}
        return result


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _index_runs(result: MultiSeedResult) -> dict[tuple[int, int], SeedRunResult]:
    if not isinstance(result, MultiSeedResult) or not result.runs:
        raise ValueError("Comparisons require nonempty MultiSeedResult inputs.")
    if len(result.runs) != len(result.seed_pairs) or not result.initial_resistance_profiles:
        raise ValueError("Run collection, profile set, and seed plan must be complete.")
    indexed = {}
    ids = set()
    environment_seeds = set()
    policy_seeds = set()
    first = result.runs[0].metrics
    for run, planned in zip(result.runs, result.seed_pairs):
        key = (run.environment_base_seed, run.policy_base_seed)
        if key != tuple(planned) or key in indexed or run.run_id in ids:
            raise ValueError("Duplicate run identity or inconsistent seed plan.")
        if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in key):
            raise ValueError("Run seeds must be nonnegative integers.")
        if run.metrics != calculate_metrics(run.evaluation):
            raise ValueError("Stored metrics do not match the episode records.")
        if (
            run.metrics.policy_name != first.policy_name
            or run.metrics.scenario_id != first.scenario_id
            or run.metrics.horizon != first.horizon
            or run.metrics.reward_weights != first.reward_weights
        ):
            raise ValueError("Run-level policy or evaluation configuration differs.")
        episodes = run.evaluation.episodes
        if tuple(episode.initial_resistance_profile for episode in episodes) != result.initial_resistance_profiles:
            raise ValueError("Initial profile ordering differs from the evaluation design.")
        for index, episode in enumerate(episodes):
            if (
                episode.episode_id != index
                or episode.environment_seed != key[0] + index
                or episode.policy_seed != key[1] + index
            ):
                raise ValueError("Episode IDs or actual seeds do not match the run design.")
            if episode.environment_seed in environment_seeds or episode.policy_seed in policy_seeds:
                raise ValueError("Overlapping expanded seed schedules do not provide distinct runs.")
            environment_seeds.add(episode.environment_seed)
            policy_seeds.add(episode.policy_seed)
        indexed[key] = run
        ids.add(run.run_id)
    manifest = result.environment_configuration
    if (
        manifest.get("scenario_id") != first.scenario_id
        or manifest.get("horizon") != first.horizon
        or manifest.get("reward_weights") != first.reward_weights
        or not manifest.get("interaction_data_sha256")
    ):
        raise ValueError("Configuration fingerprint metadata is incomplete or inconsistent.")
    return indexed


def match_run_pairs(
    strategy_a: MultiSeedResult, strategy_b: MultiSeedResult, *, allow_missing: bool = False
) -> MatchedRuns:
    """Match complete runs by seed design, never by positional IDs alone."""
    indexed_a = _index_runs(strategy_a)
    indexed_b = _index_runs(strategy_b)
    if strategy_a.environment_configuration != strategy_b.environment_configuration:
        raise ValueError("Compare one scenario and identical environment/data configuration at a time.")
    if strategy_a.initial_resistance_profiles != strategy_b.initial_resistance_profiles:
        raise ValueError("Paired runs require identical ordered initial profile sets.")
    missing_a = tuple(sorted(indexed_a.keys() - indexed_b.keys()))
    missing_b = tuple(sorted(indexed_b.keys() - indexed_a.keys()))
    if (missing_a or missing_b) and not allow_missing:
        raise ValueError("Unmatched seed designs; explicitly enable intersection matching to proceed.")
    return MatchedRuns(
        tuple(RunPair(*key, indexed_a[key], indexed_b[key]) for key in sorted(indexed_a.keys() & indexed_b.keys())),
        missing_a, missing_b,
    )


def _numeric_differences(values: Sequence[float]) -> np.ndarray:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("Differences must be a sequence of real run-level values.")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise TypeError("Differences must be real numbers.")
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise ValueError("Differences must be finite and one-dimensional.")
    return array


def paired_bootstrap_interval(
    differences: Sequence[float], *, seed: int, resamples: int = 10000,
    confidence_level: float = 0.95, independent_runs_assumed: bool = False,
) -> BootstrapIntervals:
    """Resample complete paired run differences, not steps or strategy sides."""
    ComparisonConfig(
        bootstrap_seed=seed, bootstrap_resamples=resamples,
        confidence_level=confidence_level, independent_runs_assumed=independent_runs_assumed,
    )
    values = _numeric_differences(differences)
    count = len(values)
    if count < 2 or not independent_runs_assumed:
        return BootstrapIntervals(None, None, None, None, count, resamples, seed, confidence_level)
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    medians = np.empty(resamples)
    for start in range(0, resamples, 256):
        stop = min(start + 256, resamples)
        sampled = values[rng.integers(0, count, size=(stop - start, count))]
        means[start:stop] = np.mean(sampled, axis=1)
        medians[start:stop] = np.median(sampled, axis=1)
    quantiles = ((1 - confidence_level) / 2, (1 + confidence_level) / 2)
    mean_bounds = np.quantile(means, quantiles, method="linear")
    median_bounds = np.quantile(medians, quantiles, method="linear")
    if not np.all(np.isfinite(np.concatenate((mean_bounds, median_bounds)))):
        raise ValueError("Bootstrap produced nonfinite bounds.")
    return BootstrapIntervals(
        float(mean_bounds[0]), float(mean_bounds[1]), float(median_bounds[0]),
        float(median_bounds[1]), count, resamples, seed, confidence_level,
    )


def compare_paired_metric(
    matches: MatchedRuns, metric: str, *, strategy_a: str, strategy_b: str,
    config: ComparisonConfig = ComparisonConfig(),
) -> PairedMetricComparison:
    """Describe A-B and conditionally test symmetric paired run differences."""
    if metric not in PRIMARY_METRICS:
        raise ValueError("Only the four predeclared primary metrics are supported.")
    field, direction, units = PRIMARY_METRICS[metric]
    records = []
    differences = []
    for pair in matches.pairs:
        value_a = getattr(pair.run_a.metrics.summary, field)
        value_b = getattr(pair.run_b.metrics.summary, field)
        available = value_a is not None and value_b is not None
        if available:
            _numeric_differences([value_a, value_b])
            difference = float(value_a - value_b)
            differences.append(difference)
        else:
            difference = None
        records.append({
            "run_id_a": pair.run_a.run_id, "run_id_b": pair.run_b.run_id,
            "environment_base_seed": pair.environment_base_seed,
            "policy_base_seed": pair.policy_base_seed,
            "episode_ids_a": pair.run_a.episode_identities,
            "episode_ids_b": pair.run_b.episode_identities,
            "value_a": value_a, "value_b": value_b, "difference": difference,
            "missing_a": value_a is None, "missing_b": value_b is None,
        })
    values = _numeric_differences(differences)
    ranked_values = np.round(values, config.rank_decimal_places)
    nonzero = ranked_values[ranked_values != 0]
    zero_count = len(values) - len(nonzero)
    tied_count = len(nonzero) - len(np.unique(np.abs(nonzero)))
    limitations = []
    if len(values) < len(matches.pairs):
        limitations.append("undefined_run_metrics_excluded_complete_case_estimand")
    if matches.unmatched_a or matches.unmatched_b:
        limitations.append("unmatched_runs_excluded")
    if len(values) < 10:
        limitations.append("small_run_sample")
    if len(values) and np.all(values == values[0]):
        limitations.append("constant_differences_not_proof_of_equivalence_or_no_uncertainty")
    if np.any(values != ranked_values):
        limitations.append("ranking_uses_predeclared_decimal_precision")
    strong_skew = False
    if len(values) >= 3 and np.ptp(values) != 0:
        sample_skew = float(skew(values, bias=False))
        strong_skew = math.isfinite(sample_skew) and abs(sample_skew) > 1
        if strong_skew:
            limitations.append("strong_sample_skew_symmetry_not_supported_by_diagnostic")
    statistic = None
    p_value = None
    method = None
    if not config.independent_runs_assumed:
        status = "withheld_run_independence_not_declared"
    elif not len(values):
        status = "withheld_no_defined_pairs"
    elif not len(nonzero):
        status = "withheld_all_zero_differences"
    elif len(nonzero) < config.minimum_nonzero_pairs:
        status = "withheld_insufficient_nonzero_pairs"
    elif not config.symmetric_differences_assumed:
        status = "withheld_symmetry_not_declared"
    elif strong_skew:
        status = "withheld_strong_sample_skew"
    else:
        exact = len(values) <= 16
        resamples = 2 ** len(values) if exact else config.permutation_resamples
        permutation = PermutationMethod(
            n_resamples=resamples, rng=np.random.default_rng(config.permutation_seed),
        )
        tested = wilcoxon(
            ranked_values, zero_method="pratt", alternative="two-sided",
            correction=False, method=permutation, nan_policy="raise",
        )
        statistic = float(tested.statistic)
        p_value = float(tested.pvalue)
        method = "wilcoxon_pratt_exhaustive_sign_permutation" if exact else "wilcoxon_pratt_seeded_sign_permutation"
        status = "tested_conditional_on_declared_assumptions"
    bootstrap = paired_bootstrap_interval(
        differences, seed=config.bootstrap_seed, resamples=config.bootstrap_resamples,
        confidence_level=config.confidence_level,
        independent_runs_assumed=config.independent_runs_assumed,
    )
    interpretation = (
        "Positive A-B favors A for this metric; no clinical claim."
        if direction == "higher" else
        "Negative A-B favors A for this metric; no clinical claim."
        if direction == "lower" else
        "Negative A-B means fewer actions for A; interpret alongside effectiveness and resistance."
    )
    return PairedMetricComparison(
        strategy_a, strategy_b, metric, units, interpretation, len(matches.pairs),
        len(values), zero_count, len(nonzero), tied_count,
        float(np.mean(values)) if len(values) else None,
        float(np.median(values)) if len(values) else None,
        bootstrap, statistic, p_value, None, None, method, status,
        tuple(limitations), tuple(records), config.bootstrap_seed, config.permutation_seed,
    )


def adjust_holm(p_values: Sequence[float | None]) -> tuple[float | None, ...]:
    """Holm step-down across the full planned family; untested slots count as p=1."""
    for value in p_values:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or not 0 <= value <= 1
        ):
            raise ValueError("P-values must be finite within [0,1] or None.")
    ordered = sorted(enumerate(p_values), key=lambda item: 1.0 if item[1] is None else item[1])
    adjusted = [None] * len(p_values)
    previous = 0.0
    for rank, (index, value) in enumerate(ordered):
        previous = max(previous, min(1.0, (len(p_values) - rank) * (1.0 if value is None else value)))
        if value is not None:
            adjusted[index] = previous
    return tuple(adjusted)


def compare_strategies(
    evaluations: Mapping[str, MultiSeedResult],
    contrasts: Sequence[tuple[str, str]],
    *, family_id: str, config: ComparisonConfig = ComparisonConfig(),
) -> StatisticalComparisonReport:
    """One explicit family of contrasts times four metrics within one scenario."""
    from dataclasses import replace

    if not family_id or not isinstance(family_id, str):
        raise ValueError("A nonempty predeclared family_id is required.")
    if not contrasts:
        raise ValueError("Predeclare at least one strategy contrast.")
    comparisons = []
    matching = {}
    planned = []
    used = {}
    for contrast in contrasts:
        if not isinstance(contrast, (tuple, list)) or len(contrast) != 2:
            raise ValueError("Contrasts must be strategy-name pairs.")
        name_a, name_b = contrast
        if name_a == name_b or name_a not in evaluations or name_b not in evaluations:
            raise ValueError("Contrasts must name two distinct supplied strategies.")
        if any(set(contrast) == set(previous) for previous in planned):
            raise ValueError("Duplicate or reversed contrasts are not separate hypotheses.")
        paired = match_run_pairs(evaluations[name_a], evaluations[name_b], allow_missing=config.allow_missing_pairs)
        if used and evaluations[name_a].environment_configuration != next(iter(used.values())).environment_configuration:
            raise ValueError("All family contrasts must use the same scenario and configuration.")
        used[name_a] = evaluations[name_a]
        used[name_b] = evaluations[name_b]
        planned.append((name_a, name_b))
        matching[str(len(planned) - 1)] = {
            "strategy_a": name_a, "strategy_b": name_b,
            "unmatched_a": paired.unmatched_a, "unmatched_b": paired.unmatched_b,
        }
        for metric in PRIMARY_METRICS:
            identity = json.dumps([family_id, name_a, name_b, metric], separators=(",", ":"))
            offset = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big")
            per_metric_config = replace(
                config, bootstrap_seed=config.bootstrap_seed + offset,
                permutation_seed=config.permutation_seed + offset,
            )
            comparisons.append(compare_paired_metric(
                paired, metric, strategy_a=name_a, strategy_b=name_b, config=per_metric_config,
            ))
    adjusted = adjust_holm(tuple(result.raw_p_value for result in comparisons))
    comparisons = tuple(
        replace(result, adjusted_p_value=p_value, reject_null=None if p_value is None else p_value <= config.alpha)
        for result, p_value in zip(comparisons, adjusted)
    )
    first = next(iter(used.values()))
    return StatisticalComparisonReport(
        first.runs[0].metrics.scenario_id, family_id, tuple(planned), len(comparisons), config,
        _fingerprint(first.environment_configuration),
        {name: _fingerprint(value.to_dict()) for name, value in used.items()},
        {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
         "comparison_contract": "card_4_9_v1"},
        comparisons, matching, dict(used),
    )