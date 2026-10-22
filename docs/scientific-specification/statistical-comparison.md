# Statistical comparison

## Pairing

`ml/src/statistical_comparison.py` provides the pairing and bootstrap helpers used
by matched-policy evaluation, the frozen service comparison and the multi-seed study.

`match_run_pairs()` validates stored metrics against the raw episodes, unique run
identities, expanded seed schedules, actual episode seeds, ordered initial profiles
and identical environment/data configurations. Pairing uses environment and policy
base seeds rather than positional IDs. Different scenarios, horizons, reward
configurations, action mappings or interaction-data fingerprints are rejected.

Unmatched runs raise by default. Explicit intersection matching retains unmatched
seed designs on each side. The caller remains responsible for configuration that
is not exposed in the environment fingerprint.

## Bootstrap intervals

`paired_bootstrap_interval()` resamples complete paired run differences. It does
not resample individual time steps or separate the two strategies in a pair.
Defaults are 10,000 resamples and pointwise 95% percentile intervals for the mean
and median, with linear empirical quantiles and an explicit local NumPy RNG seed.
Zero differences remain in the sample.

Inputs must be finite real differences, with a nonnegative integer seed, at least
two resamples and confidence strictly between zero and one. The caller must
explicitly declare independent runs. With fewer than two observations or without
that declaration, interval bounds are undefined. Distinct seeds alone do not
establish independence.

The paired difference is strategy A minus strategy B. Metric direction and the
analysis unit are defined by the calling evaluation. Episodes within a run are
not automatically independent statistical observations. See the
[multi-seed study runbook](ppo-seed-study-runbook.md) for the implemented study design.

These helpers do not produce a policy ranking, clinical interpretation, Wilcoxon
report or multiple-testing correction. Simulation uncertainty does not establish
biological validity or clinical effectiveness.
