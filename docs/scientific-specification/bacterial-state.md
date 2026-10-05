# Bacterial State Representation

## 1. Purpose

The bacterial state represents the current resistance phenotype of the simulated *Escherichia coli* population. It is the underlying condition used to determine treatment effectiveness, resistance evolution, and future treatment options.

The state is intentionally distinct from the observation available to the reinforcement-learning agent. This lets the simulation represent the underlying resistance condition separately from the information provided to a decision-making policy.

## 2. Population-Level Representation

The MVP models resistance at the population level; it does not represent individual bacterial cells or genomic mutations. The state is a seven-element binary vector, with one element per antibiotic in the MVP action space:

- `0` means susceptible.
- `1` means resistant.

Formally, $S_t = [r_0, r_1, ..., r_6]$, where each $r_i \in \{0,1\}$ and corresponds to the antibiotic at canonical position $i$.

For example, `0000000` represents susceptibility to all seven antibiotics. `1000000` represents ciprofloxacin resistance, because ciprofloxacin occupies position 0.

## 3. Canonical Antibiotic Ordering

The state vector uses the canonical ordering in `data/processed/action_space.csv`:

| Position | Action ID | Antibiotic |
|---:|---:|---|
| 0 | 0 | Ciprofloxacin |
| 1 | 1 | Nitrofurantoin |
| 2 | 2 | Fosfomycin |
| 3 | 3 | Trimethoprim |
| 4 | 4 | Gentamicin |
| 5 | 5 | Mecillinam |
| 6 | 6 | Ceftazidime |

This ordering is a computational convention, not a ranking of clinical preference, treatment quality, or first-line versus last-line drugs. The selected antibiotics provide an MVP experimental space spanning multiple antibiotic classes, UTI-relevant drugs, and available resistance-interaction evidence. Their fixed sequence assigns each drug a stable coordinate and action ID: action `2` always means fosfomycin, and state position `2` always represents fosfomycin susceptibility or resistance.

## 4. Why the Ordering Must Stay Fixed

A seven-element vector is meaningful only when every position has a stable interpretation. Without a fixed ordering, a profile such as `1000000` is ambiguous.

The same antibiotic mapping must be used by:

- the bacterial resistance state;
- susceptibility values in the observation given to the agent;
- action IDs;
- empirical interaction tables and the transition model;
- evaluation results and downstream consumers such as the reference environment, value iteration, and PPO.

The literature-derived interaction data is associated with antibiotic names and directions, while simulation components encode antibiotics using this shared mapping. Changing the ordering in only one component could make an action appear to select one antibiotic while the state or transition logic interprets it as another.

## 5. Source of Truth and Validation

`data/processed/action_space.csv` is the canonical source of truth for the action IDs and antibiotic order. The `ActionSpace` implementation in `simulation/action_space.py` checks the CSV order against the canonical resistance-state order when it loads the action space. This consistency was also explicitly validated during Sprint 4.

Any intentional change to the order must be treated as a coordinated model change: update the canonical action-space data and every dependent state, observation, transition, planning, training, evaluation, and API mapping together, then rerun the relevant tests. Do not reorder the list casually.