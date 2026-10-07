# Deterministic Computational Reference

## Purpose and Scope

Sprint 4 Card 4.3 provides a finite, deterministic reference problem for later
exact policy computation. It is not a claim that bacterial evolution is
deterministic. The stochastic environment and completed policies are unchanged.
Card 4.4 adds an exact finite-horizon value-iteration solver. No policy evaluator
or policy-comparison pipeline is implemented here.

## Transition Rule

`REF_DETERMINISTIC_FIRST_SUPPORTED` uses the existing evidence-supported
candidate generator and its applicability/directionality rules. For each state
and action, candidates are grouped by `(target_drug, outcome)`. The
lexicographically smallest key is selected, with all its supporting source IDs
retained in sorted order. Neutral candidates participate in the same ordering.
If the candidate set is empty, resistance remains unchanged and the status is
`unsupported_no_candidate`.

Lexicographic selection is an arbitrary, reproducible computational fixture,
not an evidence ranking or clinical priority. For a fixed processed dataset,
state, and action, the selected next state has probability 1 and every other
next state has probability 0. These probabilities have provenance
`reference_scenario`, not `empirical`. Seeds do not affect transitions.
Changing the evidence dataset can change the reference problem.

## Finite Planning State

All seven canonical antibiotics and binary resistance components are retained.
There are 128 resistance profiles. The planning state is `EpisodeState`, which
also includes elapsed treatment steps from 0 through the configured horizon.
At the default horizon of eight, there are 128 * 9 = 1,152 state/time pairs and
seven actions. These include terminal states; not all pairs need be reachable
from one initial state. The default initial profile is fully susceptible;
`reset(options={"initial_resistance_state": ...})` also accepts a validated
`ResistanceState`, tuple, or list.

Episodes terminate at the horizon or when all seven antibiotics are resistant.
For planning, terminal states are absorbing with zero further reward. The
interactive environment rejects further steps until reset. The horizon is an
intrinsic finite-horizon boundary, so the terminal flag is `terminated=True`,
not an external time-limit truncation.

The canonical 15-dimensional observation uses 0 for susceptible and 1 for
resistant, includes one-hot last action and elapsed steps, and exposes the
current reference state fully. Last action does not affect future dynamics or
reward, so it is excluded from the minimal planning state without losing the
Markov property. The constrained resistance-burden reward is used. If a
transition reaches the all-resistant state before the horizon, its burden is
charged through the remaining fixed-horizon steps.

## Exact Planning Interface

`DeterministicReferenceEnvironment.states()` enumerates the finite state space.
`is_terminal(state)` identifies terminal states, and
`transition(state, action)` returns the unique next planning state, reward,
terminal flag, and scenario metadata without mutating the running episode.
This supplies a complete known transition/reward table for Card 4.4.

## Solver Contract (Card 4.4)

`ml/src/value_iteration.py` exposes `value_iteration(environment, gamma=1.0)`.
It accepts the deterministic reference environment and requires `gamma = 1`
for the specified undiscounted fixed-horizon burden objective. Booleans and
nonnumeric values raise `TypeError`; nonfinite or out-of-range values raise
`ValueError`, and other in-range discount values are rejected.

The solver enumerates planning states and processes them in descending treatment
step order. Every nonterminal transition advances time, so a single reverse-time
pass suffices; no convergence tolerance or iterative stopping criterion is needed.
For each nonterminal state and feasible action, the Bellman backup is:

$$
Q(s,a) = R(s,a) + \mathbf{1}_{\text{not terminal}} V(T(s,a)),
\qquad V(s) = \max_{a\in A_{\mathrm{feasible}}(s)} Q(s,a).
$$

The reward for entering an all-resistant terminal state includes burden through
the remaining horizon; its continuation value is zero. Other terminal states
have zero state and action values and no policy action. Infeasible actions have
action value negative infinity and are excluded from maximization. Exact
maximizing ties select the lowest feasible action ID. Near-equal floating-point
values are not converted into ties by a numerical tolerance.

`ValueIterationResult` contains `state_values[state]`,
`action_values[state][action]`, `policy[state]`, and the validated `gamma`.
All enumerated states and seven actions are present in the value tables;
infeasible action values are negative infinity. `policy[state]` is `None` for
terminal states and a feasible integer action otherwise. Keys are immutable
`EpisodeState` objects. Solving does not reset, step, or mutate the interactive
environment and does not consume any random generator.

This is exact planning under the known reference dynamics, up to floating-point
arithmetic. It is not an optimal policy for the stochastic environment or a
clinical recommendation. Values depend on the reference selection rule, processed
evidence snapshot, reward specification, and horizon. The solver relies
on this model's complete finite enumeration and strictly advancing nonterminal
time; it is not a general cyclic or infinite-horizon solver.

## Validation

Tests cover cross-resistance, collateral sensitivity, neutral outcomes,
unsupported actions, seed independence, reward and observation conventions,
termination, and Gymnasium compatibility. The full state/action table is checked
for deterministic repeatability, probability 1, closure within the enumerated
space, absorbing terminal states, and absence of mutation during planning.

Solver tests additionally verify all-state Bellman consistency, terminal values,
immediate rewards and continuation, lowest-ID ties, discount validation,
reproducibility, no episode/RNG mutation, and agreement with exhaustive action
sequences for a two-step horizon.