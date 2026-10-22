from collections.abc import Sequence
from dataclasses import dataclass
import math
from numbers import Real

import numpy as np

from ml.src.metrics import calculate_metrics
from ml.src.multi_seed_evaluation import MultiSeedResult, SeedRunResult


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
            or run.metrics.reward_specification != first.reward_specification
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
        or manifest.get("reward_specification") != first.reward_specification
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
    if not isinstance(independent_runs_assumed, bool):
        raise TypeError("independent_runs_assumed must be boolean.")
    if isinstance(confidence_level, bool) or not isinstance(confidence_level, Real):
        raise TypeError("confidence_level must be a real number.")
    if not math.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be finite and strictly between 0 and 1.")
    for name, value, minimum in (("seed", seed, 0), ("resamples", resamples, 2)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer.")
        if value < minimum:
            raise ValueError(f"{name} must be at least {minimum}.")
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
