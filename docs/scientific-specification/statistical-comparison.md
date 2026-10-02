# Statistical Comparison (Sprint 4 Card 4.9)

## Unit, Estimand, and Pairing

`ml/src/statistical_comparison.py` compares existing `MultiSeedResult` records.
Independent evaluation runs are the primary analysis units. Each run contributes
mean episode TER, mean episode RER, mean FEA, and mean episode cumulative exposure,
using the existing metrics engine. Rates average defined episode rates, not
steps; zero-step episodes retain endpoint/exposure values but have undefined rates.
This estimand is intentionally different from pooled step-weighted TER/RER.
All defined run pairs have equal weight. Episode-level data remain in the report
for diagnostics, but are not additional statistical samples.

`match_run_pairs()` validates metrics against raw episodes, unique run IDs,
expanded seed schedules, actual episode seeds, ordered initial-profile sets,
and identical environment/data manifests. Pairing uses environment and policy
base seeds under that shared design, not positional run/episode IDs. Each pair
retains both strategies' run and episode identifiers. Changed scenarios, horizon,
weights, action mappings, observation contract, or transition-data fingerprint
are rejected. Custom hidden component settings remain the factory's responsibility.

Missing run matches raise by default. Explicit intersection matching reports
unmatched designs from each strategy. Metric values undefined on either side
exclude that complete pair for that metric only, with both missingness flags
retained. The resulting estimand is conditional on defined paired values; no
zero imputation, fallback pairing, or substituted strategy is used.

## Descriptive Differences and Bootstrap

Differences are always strategy A minus strategy B. Positive TER/FEA differences
favor A for that metric; negative RER differences favor A. Negative exposure
differences mean fewer actions but must be considered alongside effectiveness
and resistance. Report mean and median paired differences in original units.
No clinical practical-importance threshold is inferred.

`paired_bootstrap_interval()` resamples complete run pairs via their difference
vector, preserving the two sides together. It returns pointwise 95% percentile
intervals for mean and median, using a local NumPy RNG, explicit seed, 10,000
resamples by default, and linear empirical quantiles. Zero differences remain
in bootstrap/descriptive samples. With fewer than two defined pairs, bounds are
undefined. Bounds are also withheld unless run independence is explicitly assumed.
Constant differences can produce zero-width bounds, not proof of equivalence or
absence of uncertainty. Small/discrete samples can give poor percentile coverage.

## Conditional Wilcoxon Inference

`ComparisonConfig` defaults to alpha 0.05 and confidence 0.95. Independence and
symmetry assumptions default to false: callers must explicitly declare them after
design review. Distinct computational seeds do not prove independence or represent
independent biological populations. Matched seeds mean matched initialization and
schedules, not perfectly paired stochastic transitions. Run clustering/dependence
is not corrected by this implementation; if independence is not defensible,
descriptive results are retained and inference is withheld.

`compare_paired_metric()` uses two-sided Wilcoxon signed ranks with `zero_method="pratt"`
and no continuity correction. Zero differences participate in rank assignment but
their ranks do not contribute signs. Absolute-rank ties use average ranks. Ranking
differences are rounded to a predeclared default 12 decimal places to prevent
floating-point artifacts; effect estimates and bootstrap use original values.
Zero/nonzero counts and tie counts describe this explicitly rounded rank input.

P-values are withheld for no defined pairs, all-zero differences, fewer than the
configured minimum six nonzero pairs, undeclared symmetry/independence, or strong
observed skewness. Six is a conservative default eligibility rule: with fewer
nonzero signs even the minimum two-sided sign-permutation resolution cannot fall
below 0.05. It is not a power guarantee, especially after Holm correction.
Absolute bias-corrected sample skew above one is a conservative descriptive gate,
not a formal symmetry test; passing it does not establish symmetry. The signed-rank
location interpretation requires independent comparable differences with a
distribution symmetric about its location, not normal individual policy outcomes.
Wilcoxon is not specifically a test of the mean difference.

When eligible, SciPy's `PermutationMethod` computes the signed-rank p-value:
exhaustive sign permutations for at most 16 defined pairs, or seeded 9,999
permutations otherwise. Ties/zeros are accommodated by the permutation distribution;
the standard no-ties Wilcoxon exact table and automatic method selection are not
used. Monte Carlo p-values have finite resampling resolution and simulation error.
No unsupported case silently switches to a different hypothesis test.

## Predeclared Testing Family

`compare_strategies(evaluations, contrasts, family_id=..., config=...)` accepts
explicit ordered strategy contrasts and creates exactly four tests per contrast.
Duplicate/reversed contrasts are rejected. Every contrast belongs to one scenario
and matching configuration. No sensitivity/reference pooling or joint claims
across scenarios are made. Such claims require an explicitly expanded future family.

`adjust_holm()` applies Holm step-down across the entire planned contrast-by-four-
metric family. Untestable hypotheses retain their family slots conservatively as
p=1 internally; their reported raw/adjusted p-values and rejection decision remain
undefined. Both raw and adjusted p-values are reported, with rejection based on
adjusted p <= 0.05 by default. Bootstrap bounds are pointwise, not simultaneous
family-adjusted confidence intervals. No arbitrary overall score or policy ranking
is generated. Statistical significance is not clinical importance, clinical
effectiveness, or biological validation.

## Reproducibility and Output

Reports preserve original evaluations, paired values, missingness, scenario,
configuration/input SHA-256 hashes, policy labels and class identities, ordered
contrasts, family size, all settings, and Python/NumPy/SciPy plus comparison-contract
versions. Pair order is canonical by seed design. Separate RNG streams for bootstrap
and permutation use reported seeds derived from the base seeds and a SHA-256 digest
of family ID, contrast, and metric. Unrelated contrast ordering does not change
these streams. Repeating inputs/settings with the same numerical environment
reproduces results. Preserve the source revision externally along with the report;
the contract version is not a git commit identifier. `to_dict()` exports detached
JSON-compatible results. Inputs and previous cards are not modified.

This card adds no VI adapter, baseline report, PPO training, or later-card work.
Available inputs may have too few runs for inference; they produce explicitly
withheld tests, never inflated sample sizes from dependent episodes.