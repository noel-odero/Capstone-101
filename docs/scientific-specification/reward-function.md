# Reward Function Specification

## 1. Purpose

The reward function defines how the reinforcement learning agent evaluates
treatment decisions within the simulated E. coli resistance environment.

The objective is to encourage treatment with an antibiotic to which the
current bacterial population is susceptible, discourage increases in
resistance, and discourage unnecessary antibiotic exposure.

The reward function is a computational representation of the project's
stewardship objectives. The reward weights are model design parameters and
are not interpreted as biological probabilities or clinical recommendations.

---

## 2. Reward Definition

For each environment transition, the reward is defined as:

$$
R_t = w_E R_E + w_R R_R + w_X R_X
$$

where:

- $R_E$ = treatment-effectiveness component
- $R_R$ = resistance-change component
- $R_X$ = antibiotic-exposure component
- $w_E$ = effectiveness weight
- $w_R$ = resistance weight
- $w_X$ = exposure weight

The weights are configurable.

The initial MVP values are:

| Component | Weight |
|---|---:|
| Treatment effectiveness | 1.0 |
| Resistance change | 0.5 |
| Antibiotic exposure | 0.1 |

These values are initial model-design choices and will be subject to
evaluation and sensitivity analysis.

---

## 3. Treatment Effectiveness

Treatment effectiveness represents whether the selected antibiotic is
currently effective against the simulated bacterial resistance state.

For action $A_t$ and state $S_t$:

$$
R_E =
\begin{cases}
+1 & \text{if the selected antibiotic is susceptible} \\
-1 & \text{if the selected antibiotic is resistant}
\end{cases}
$$

The effectiveness component therefore provides an immediate signal about
whether the selected treatment can act against the current resistance state.

This component does not represent clinical cure.

The MVP does not model minimum inhibitory concentrations, pharmacokinetics,
pharmacodynamics, patient-specific drug concentrations, or clinical
clearance probabilities. Therefore, susceptibility in the simulation is
treated as treatment effectiveness within the computational model rather
than a guarantee of clinical cure.

---

## 4. Resistance Change

The resistance component penalizes increases in the number of antibiotics
to which the simulated bacterial population is resistant.

Let $N_R(S_t)$ and $N_R(S_{t+1})$ represent the numbers of resistant
antibiotics in the current and next states, respectively.

The change in resistance is:

$$
\Delta R = N_R(S_{t+1}) - N_R(S_t)
$$

The resistance reward is:

$$
R_R = -\Delta R
$$

Therefore:

| Resistance change | R_R |
|---|---:|
| Resistance increases by 1 | -1 |
| No change | 0 |
| Resistance decreases by 1 | +1 |
| Resistance increases by 2 | -2 |
| Resistance decreases by 2 | +2 |

This allows collateral sensitivity to produce a positive resistance-related
reward when a transition reduces the number of resistant antibiotics.

The component does not assume that every resistance change is caused by a
specific biological mechanism. The transition model determines the next
state, while the reward function evaluates the resulting change.

---

## 5. Antibiotic Exposure

Each treatment action incurs an exposure cost:

$$
R_X = -1
$$

The exposure component discourages unnecessarily long treatment sequences.

The exposure penalty is deliberately smaller than the initial treatment
effectiveness reward. This prevents the model from strongly preferring
shorter treatment simply because shorter treatment produces less exposure.

The exposure component represents treatment burden within the simulation.
It does not represent a clinical toxicity estimate or a patient-specific
dose-related risk.

---

## 6. Combined Reward

The complete reward is:

$$
R_t = w_E R_E + w_R R_R + w_X R_X
$$

Using the initial MVP weights:

$$
R_t = 1.0R_E + 0.5R_R + 0.1R_X
$$

For example, suppose:

- the selected antibiotic is susceptible;
- resistance increases by one antibiotic after the transition;
- one treatment step has been used.

Then:

$$
\begin{aligned}
R_E &= +1 \\
R_R &= -1 \\
R_X &= -1
\end{aligned}
$$

Therefore:

$$
\begin{aligned}
R_t &= (1.0)(+1) + (0.5)(-1) + (0.1)(-1) \\
    &= 0.4
\end{aligned}
$$

The agent therefore receives a positive reward, but less than it would
receive for an effective treatment that did not increase resistance.

---

## 7. Future Treatment Options

The number of future treatment options is not currently included as a
separate reward component.

In the binary seven-antibiotic resistance representation, the number of
susceptible antibiotics is directly related to the number of resistant
antibiotics:

$$
N_S = 7 - N_R
$$

Therefore, independently rewarding both resistance reduction and an
increase in susceptible future options would count the same state change
twice.

Future treatment options will instead be evaluated as an outcome metric
during policy evaluation.

This allows the project to measure whether a policy preserves future
treatment options without artificially increasing the reward for the same
resistance change.

---

## 8. Treatment Success and Clinical Clearance

Clinical treatment success is not directly represented as a reward component
in the MVP.

The current simulation determines whether an antibiotic is effective against
the simulated resistance state but does not model infection clearance.

Therefore, the effectiveness reward must not be interpreted as a clinical
success or cure probability.

If a future version of the environment introduces an explicit infection
clearance state, episode-level treatment success can be incorporated into
the reward function and evaluated separately.

---

## 9. Reward Weight Configuration

Reward weights are configurable through the `RewardWeights` object.

The implementation does not hard-code the weights inside the reward
calculation.

This allows experiments with different stewardship priorities without
changing the reward-function implementation.

The initial values are:

```text
effectiveness = 1.0
resistance = 0.5
exposure = 0.1