# Simulation Horizon Specification

## 1. Purpose

The simulation horizon defines the maximum number of sequential treatment
decisions within one simulated treatment episode.

The horizon determines how many opportunities the reinforcement learning agent
has to respond to changes in the simulated E. coli resistance state.

The horizon is a computational parameter and does not represent a clinical
treatment duration or recommended number of antibiotic doses.

---

## 2. Maximum Horizon

The MVP uses a maximum horizon of:

$$
H = 8
$$

An episode can therefore contain at most eight treatment actions.

The horizon is configurable so that alternative horizons can be evaluated
during later experiments.

---

## 3. Rationale

A sequential treatment problem requires enough decision steps for an earlier
treatment choice to influence subsequent resistance states and therefore
future treatment decisions.

A horizon that is too short would reduce the problem toward a single-step
treatment-selection task.

A horizon that is unnecessarily long would increase computational cost and
could introduce additional assumptions about long treatment sequences that
are not supported by the MVP biological model.

Eight steps provides a bounded environment in which:

- multiple treatment decisions can occur;
- resistance transitions can accumulate;
- collateral sensitivity can influence later decisions;
- future treatment options can change during an episode;
- PPO training remains computationally manageable.

The value of eight is a modelling choice rather than an empirical clinical
parameter.

---

## 4. Episode Termination

An episode terminates when any defined termination condition is reached.

### 4.1 Maximum Horizon

The episode terminates after eight treatment actions:

$$
t \geq H
$$

where:

$$
H = 8
$$

---

### 4.2 No Effective Antibiotic Remains

The episode terminates when the true resistance state contains resistance
to all antibiotics in the MVP action space.

The MVP contains seven antibiotics.

Therefore:

$$
N_S(S_t) = 0
$$

terminates the episode.

This represents a state in which the simulated population has no remaining
effective treatment option within the defined action space.

It does not represent clinical pan-drug resistance outside the simulated
seven-antibiotic environment.

---

## 5. Termination and Clinical Clearance

The MVP does not currently include an explicit infection-clearance model.

Therefore, the environment does not terminate because of simulated clinical
cure.

This distinction is intentional.

The current simulation models antibiotic treatment decisions and resistance
dynamics rather than a complete patient-level infection model.

An explicit clearance state may be considered in a future extension if it can
be supported by an appropriate biological and clinical model.

---

## 6. Repeated Antibiotic Use

The same antibiotic may be selected more than once during an episode.

The action space therefore remains:

$$
A = \{
\text{ciprofloxacin},
\text{nitrofurantoin},
\text{fosfomycin},
\text{trimethoprim},
\text{gentamicin},
\text{mecillinam},
\text{ceftazidime}
\}
$$

No rule prevents an agent from selecting the same action at consecutive
steps.

The resulting resistance state determines whether that antibiotic remains
effective.

This avoids introducing an unsupported assumption that an antibiotic cannot
be reused.

---

## 7. Horizon and Observation

The treatment step is included in the observable state.

The treatment-step value starts at:

$$
t = 0
$$

and increases after each treatment action.

The observation therefore provides the agent with information about its
position within the finite-horizon episode.

---

## 8. Horizon and Reward

The reward is calculated for each treatment transition.

For an episode containing $T$ treatment actions:

$$
G = \sum_{t=0}^{T-1} R_t
$$

The maximum possible number of reward-producing treatment transitions in the
MVP is eight.

The finite horizon therefore bounds the total number of treatment actions
and associated exposure costs.

---

## 9. Horizon and Evaluation

The same maximum horizon should be applied consistently when comparing
policies unless an experiment explicitly evaluates the effect of changing
the horizon.

Evaluation should record:

- number of treatment steps;
- whether the episode reached the maximum horizon;
- whether the episode terminated because no effective antibiotic remained;
- cumulative reward;
- treatment effectiveness;
- resistance emergence;
- future effective antibiotics;
- cumulative antibiotic exposure.

---

## 10. Configurability

The horizon should be configurable in the simulation environment rather than
hard-coded into the transition logic.

The initial configuration is:

```text
max_steps = 8