# Bacterial State Representation

## 1. Purpose

The bacterial state represents the current resistance phenotype of the simulated *Escherichia coli* population.

The state provides the underlying biological condition from which treatment effectiveness, resistance evolution, and future treatment options are determined.

The state representation is intentionally separated from the observable state available to the reinforcement-learning agent. This allows the simulation to distinguish the underlying resistance condition from the information available for decision-making.

## 2. Population-Level Representation

The MVP models resistance at the population level rather than representing individual bacterial cells or individual genomic mutations.

The bacterial state is represented as a seven-dimensional binary vector corresponding to the seven antibiotics in the MVP action space.

For each antibiotic:

- `0` represents susceptible
- `1` represents resistant

The state is therefore:

\[
S_t = [r_1, r_2, ..., r_7]
\]

where:

\[
r_i \in \{0,1\}
\]

and each \(r_i\) corresponds to one antibiotic in the action space.

## 3. Antibiotic Ordering

The state vector follows the canonical ordering defined in:

`data/processed/action_space.csv`

The current ordering is:

| Index | Antibiotic | State value |
|---|---|---|
| 0 | Ciprofloxacin | 0 = susceptible, 1 = resistant |
| 1 | Nitrofurantoin | 0 = susceptible, 1 = resistant |
| 2 | Fosfomycin | 0 = susceptible, 1 = resistant |
| 3 | Trimethoprim | 0 = susceptible, 1 = resistant |
| 4 | Gentamicin | 0 = susceptible, 1 = resistant |
| 5 | Mecillinam | 0 = susceptible, 1 = resistant |
| 6 | Ceftazidime | 0 = susceptible, 1 = resistant |

The ordering must remain consistent across the simulation environment, training data, model input, evaluation pipeline, and API.

## 4. Example State

The state:

```text
[0, 1, 0, 1, 0, 0, 1]