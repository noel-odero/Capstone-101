# Observable State Representation

## 1. Purpose

The observable state defines the information available to the reinforcement-learning agent when selecting an antibiotic.


The simulation maintains the true bacterial state internally, while the agent receives only the information that the proposed decision-support system is intended to observe.

## 2. Observation Components

The MVP observation consists of three components:

1. Current susceptibility information
2. Treatment history
3. Treatment-step context

The observation is represented as a fixed-length vector.

## 3. Susceptibility Information

The most recent susceptibility result is represented for each antibiotic in the seven-drug action space.

Each antibiotic has one of three values:

- `0` = susceptible
- `1` = resistant
- `-1` = unknown or unavailable

The seven values follow the canonical antibiotic ordering:

| Index | Antibiotic |
|---|---|
| 0 | Ciprofloxacin |
| 1 | Nitrofurantoin |
| 2 | Fosfomycin |
| 3 | Trimethoprim |
| 4 | Gentamicin |
| 5 | Mecillinam |
| 6 | Ceftazidime |

For example:

```text
[0, -1, 0, 1, -1, 0, 1]