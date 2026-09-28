# Treatment Action Space

## 1. Purpose

The treatment action space defines the treatment decisions available to the reinforcement-learning agent during a simulation episode.

The MVP uses seven antibiotic actions corresponding to the seven antibiotics defined in:

`data/processed/action_space.csv`

## 2. Action Encoding

The action space contains seven discrete actions:

| Action | Antibiotic |
|---:|---|
| 0 | Ciprofloxacin |
| 1 | Nitrofurantoin |
| 2 | Fosfomycin |
| 3 | Trimethoprim |
| 4 | Gentamicin |
| 5 | Mecillinam |
| 6 | Ceftazidime |

The mapping is fixed and must remain consistent across the simulation environment, training pipeline, evaluation pipeline, and API.

## 3. Computational Representation

The domain-level action space is represented by `ActionSpace` in:

`simulation/action_space.py`

The environment will expose these seven actions to the reinforcement-learning agent as a discrete action space.

Conceptually:

```text
action ∈ {0, 1, 2, 3, 4, 5, 6}