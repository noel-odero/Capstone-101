# Run-Level Confidence Intervals (Sprint 4 Card 4.8)

## Interface and Evaluation Output

`ml/src/confidence_intervals.py` provides
`calculate_confidence_intervals(multi_seed_result, confidence_level=0.95)`.
It returns a `ConfidenceIntervalReport` containing the original evaluation,
policy/scenario identity, assumptions, and separate metric intervals. This wrapper
adds confidence intervals to exported evaluation output without modifying the
Card 4.7 result or changing the runner/metrics engine. `to_dict()` creates detached
JSON-compatible records, including all original grouping/seed information.

Each metric record contains the ordered run IDs and values, contributing and
excluded run IDs, mean, lower/upper bounds, valid sample count, excluded count,
sample standard deviation, confidence level, method, and limitation flags.
`t_confidence_interval(values, confidence_level=0.95)` is also available for an
explicit sequence of run-level values; it does not know grouping metadata.

## Statistical Observation and Estimands

One evaluation run contributes one value per metric, regardless of its episode
lengths. No individual time step or episode is treated as an independent sample.
All defined runs have equal weight in the across-run mean and interval.

The reported fields are pooled TER/RER, mean episode TER/RER (kept separately),
mean FEA, mean change in FEA, mean episode cumulative exposure, and mean episode
cumulative reward. Run-level pooled rates weight steps within their own run;
episode-rate means use only defined episodes within the run, following Card 4.6.
Endpoints/exposure/reward means retain zero-step episodes. Runs can therefore
have differing step counts and terminal conditions without changing definitions.

Undefined run-level values (`None`) are excluded only for that metric. They are
never replaced by zero. The mean/interval targets the distribution of defined
run-level values; excluded runs and differing rate-contributor sets must be
visible when interpreting results. An all-zero-step run has undefined rates but
defined endpoint, exposure, and reward means.

## Method

The two-sided Student-t interval for the run-level mean is:

$$
\bar{x} \pm t_{1-\alpha/2,n-1}\frac{s}{\sqrt{n}},
\qquad \alpha = 1-\text{confidence level},
$$

where `s` is the sample standard deviation with `n - 1` degrees of freedom.
SciPy supplies the t quantile. No RNG, bootstrap, or resampling is used; identical
inputs yield identical results within the same numerical environment.

For no valid values, mean and bounds are `None`. With one valid run, the mean is
defined but standard deviation and bounds are `None`. Constant samples with at
least two runs return a zero-width interval with a caveat: identical observed
values do not prove there is no uncertainty. Bounds are not clipped to natural
metric ranges; rate intervals extending outside `[0,1]` reveal a limitation of
the conventional approximation, not a valid probability outside that range.

Confidence levels must be finite real numbers strictly between 0 and 1;
booleans are rejected. Nonfinite or nonnumeric data are rejected, not counted as
undefined observations. Nonfinite numerical results are also rejected.
Mixed policy/scenario/configuration records, duplicate run IDs, inconsistent
seed plans, and changed initial-profile groupings are rejected.

## Assumptions and Limitations

Nominal t coverage assumes independent, identically distributed run-level values
and an approximately normal sampling distribution of their mean. Distinct seeds
alone do not establish those assumptions. Matching initial states and schedules
means matched initialization, not perfectly paired stochastic transitions.
All run IDs, base/episode seeds, and initial-profile grouping are retained;
dependence or additional clustering is not corrected by this method.

Fewer than ten valid runs triggers an explicitly heuristic small-sample flag.
For at least three nonconstant values, absolute bias-corrected sample skewness
above one triggers a skewness limitation flag. These flags are descriptive
warnings, not normality tests, automatic validity certificates, or policy tests.
Intervals describe variation under simulator assumptions, not clinical uncertainty
or independent biological populations. There are no policy comparisons,
hypothesis tests, multiple-comparison corrections, rankings, VI adapters, or
baseline reports in this card.