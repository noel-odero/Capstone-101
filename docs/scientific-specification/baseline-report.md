# Baseline Evaluation Report (Sprint 4 Card 4.10)

The predeclared plan is `experiments/baseline_config.json`: 20 seed runs per
random/greedy policy and stochastic scenario, all 128 equally weighted binary
initial profiles, eight-step horizon, gamma=1 for the exact reference, and the
primary `REF_UNIFORM_SUPPORTED` plus sensitivity q=0.25/0.50/0.75 scenarios.
This is exhaustive profile coverage, not a clinical prevalence distribution.

`ml/src/baseline_report.py` delegates trajectories, metrics, t intervals, and
paired-run descriptive contrasts/bootstrap intervals to the existing pipeline.
It uses the approved run-independence assumption conditionally; symmetry remains
undeclared, so Wilcoxon p-values are withheld. Test eligibility may independently
withhold tests for zeros, small samples, or strong skew. Each scenario has its
own four-primary-metric Holm family and is never pooled with another scenario.

For run i with N profiles, base seeds are `1000 + i*N` for the environment and
`100000 + i*N` for the policy; the runner adds the episode index. This avoids
expanded-schedule overlap. The same design is used separately for both policies.
Matched initialization and schedules do not imply matched transition draws.

The exact section solves the deterministic reference and rolls out its policy
through the pure transition interface for every initial profile. It verifies
each cumulative reward against the exact state value and reuses episode metrics.
It is not a VI adapter for stochastic evaluation, and exact seed placeholders
do not represent replicated random samples. No seed interval is invented for
fixed exact values. Optimality applies only to this deterministic reward problem.

## Regeneration

From the repository root with the project's Python environment:

```powershell
python -m ml.src.baseline_report --config experiments/baseline_config.json --output-dir experiments/results/baseline
```

This generates `baseline_report.md` and `baseline_report.json`. The JSON retains
full trajectories, seed/group identities, all metrics/uncertainty, comparison
settings, configuration/data hashes, plan hash, and numerical software versions.
The Markdown keeps random, greedy, exact, metrics, uncertainty, scenario sensitivity,
termination summaries, and interpretation limits visible. Pooled and episode-mean
rates are separately named. Reports contain no arbitrary combined score, clinical
recommendation, claim that RL wins, or PPO results.

No timestamps are introduced: identical plan, data, code, and numerical versions
should reproduce identical output. Preserve the source revision externally with
the artifacts. Generated files live in the repository's existing ignored results
directory; retain/archive them deliberately as research outputs. Tests use smaller
explicit fixtures without changing the committed full evaluation plan.