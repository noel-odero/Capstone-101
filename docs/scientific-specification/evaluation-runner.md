# Evaluation Runner (Sprint 4 Card 4.5)

`ml/src/evaluation_runner.py` exposes
`run_evaluation(environment, policy_factory, episode_count, *, environment_seed=0,
policy_seed=0, initial_states=None)`. Supply a stochastic `AntibioticEnvironment`
and a factory such as `RandomPolicy` or `GreedyPolicy`. Existing policy instances
cannot be reseeded through their public interface, so the runner requires a
factory called as `factory(environment.action_space, seed=episode_policy_seed)`.
It never edits a policy RNG or changes the environment configuration.

Episode IDs are zero-based. Episode i uses `environment_seed + i` for reset and
`policy_seed + i` for a newly constructed policy. Base seeds must be nonnegative
integers, and episode count must be a positive integer. Repeating a configuration
with a fresh, equivalently configured environment and deterministic policy
factory reproduces the trajectories. Distinct seeds are bookkeeping for separate
streams, not a guarantee of statistically independent biological trajectories.
The runner does not draw from the environment RNG; reset and step own its use.

`initial_states` supplies exactly one validated binary resistance profile per
episode, as a `ResistanceState` or sequence. The default is fully susceptible in
every episode. Profiles are supplied using the existing reset option. The caller
owns the environment: the runner resets and advances it, leaves its last episode
in place, and does not close it. Factories must return a fresh policy without
reconfiguring the environment. Observation copies prevent policy-side mutation
from changing the recorded input. Initially terminal episodes are recorded with
zero actions and reward; no policy action is requested.

`EvaluationResult` records scenario ID, active horizon, actual episode-step reward
weights, and a tuple of `EpisodeResult` records. Each episode contains its ID,
seeds, policy class identity, initial/final true resistance profiles, reset
observation/info, and `StepResult` records with before/after observation snapshots,
action, reward, terminal/truncated flags, and deep-copied full transition info.
Properties expose observation, action, antibiotic, reward, and effectiveness
sequences, cumulative reward, and treatment-step count. Full info retains
transition status, scenario, candidate/source provenance, occurrence assumptions,
scenario probabilities, and transition seed. No probabilities are estimated.

Episodes stop on either Gymnasium flag. Termination reasons distinguish
`no_effective_antibiotic`, `maximum_horizon`, `terminated`, and `truncated`.
When exhaustion and horizon coincide, exhaustion takes precedence. An environment
that exceeds its declared horizon without signaling completion raises an error;
the runner does not invent truncation. Policy/environment failures propagate,
without fallback actions or successful partial-episode records.

This runner is policy-agnostic within the existing seeded-constructor and
`select_action(observation)` contracts. It does not support deterministic-reference
evaluation, a VI lookup adapter, unknown observation reconstruction, policy
rankings, aggregate metrics, statistical analysis, or PPO training. Raw results
are computational episode records, not evidence of clinical effectiveness.