# Multi-Seed Evaluation (Sprint 4 Card 4.7)

`ml/src/multi_seed_evaluation.py` exposes
`run_multi_seed_evaluation(environment_factory, policy_factory, seed_pairs,
initial_states=...)`. Both factories follow the existing stochastic runner
contracts. The environment factory takes no arguments. The policy factory takes
the action space and a keyword seed and must return a fresh observation policy.
The initial-state sequence is nonempty and is reused in exactly the same order
for every run. It determines the number of episodes per run.

## Seed Plan

`seed_pairs` is a nonempty ordered sequence of nonnegative integer pairs
`(environment_base_seed, policy_base_seed)`. Run IDs follow this order; episode
IDs remain zero-based within each run. Episode i uses each base seed plus i,
as assigned by the existing runner. Composite identity is `(run_id, episode_id)`;
actual episode seeds, policy identity, and scenario identity are retained.

Before execution, expanded schedules are checked for overlap across runs within
each stream. With two initial profiles, environment bases 10 and 11 overlap on
seed 11 and are rejected. Cross-stream equality (an environment seed numerically
equal to a policy seed) is permitted. No additional random seed derivation or
sampling is introduced by the orchestration layer.

## Consistent Configuration and Fresh Instances

Each run creates a new stochastic environment. The existing runner creates a
new seeded policy per episode. Reused environment or policy objects are rejected.
The orchestration layer owns its factory-created environments and closes them
after each run, including execution or configuration failures. Existing runner,
metrics, policies, and environments are not modified.

Configuration snapshots must match before each run and remain unchanged afterward.
Snapshots include component types, action mappings throughout the simulation,
action-space dimensions, scenario ID and occurrence assumption, active horizon,
episode-step reward weights, and observation bounds/dtype. A SHA-256 fingerprint
of loaded interaction records includes all fields and preserves row ordering;
dictionary-key ordering is normalized. Data row order matters for seeded candidate
selection. A different dataset or configuration is rejected, not silently mixed.

The snapshot covers the exposed configuration of the current simulation stack,
not arbitrary hidden parameters in custom component subclasses. Factories remain
responsible for keeping any extra settings identical. Use the same factory,
initial-profile ordering, and seed plan in separate random/greedy invocations.
Their manifests can be checked for equality, without implementing policy rankings.

## Results and Interpretation

`MultiSeedResult` contains the ordered seed plan, initial profiles, common
configuration snapshot, and ordered `SeedRunResult` records. Each record retains
run ID, base seeds, raw `EvaluationResult`, and the existing metrics engine's
`EvaluationMetrics`, plus composite episode identities. `to_dict()` exports
detached JSON-compatible data. No metrics formulas are duplicated and no cross-run
summary, confidence interval, hypothesis test, or policy ranking is calculated.
Initially terminal episodes remain zero-step records with undefined rates.

Repeating the same configuration, data snapshot, seed plan, and fresh deterministic
factories reproduces results. Shared environment seeds across policies mean
matched initialization and seed schedules, not perfectly paired stochastic draws:
different actions, candidate sets, and episode lengths can produce divergent
random consumption and transitions. Distinct seeds do not establish statistical
independence of real biological trajectories or biological/clinical validation.

This card supports stochastic random/greedy evaluation only. It adds no
deterministic-reference runner, VI adapter, confidence intervals, statistical
analysis, baseline report, or PPO training. Failures propagate without fallback
actions, substituted runs, or successful partial result collections.