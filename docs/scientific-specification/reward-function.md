# Reward and Feasibility Specification

## 1. Scope

The current objective is a constrained finite-horizon planning problem over a
fully observed binary resistance profile for seven antibiotics. It does not
model clinical cure, treatment need, dose, duration, or patient-specific
exposure. Susceptibility is an environment-defined feasibility signal, not a
guarantee of clinical success.

The policy must select an antibiotic that is susceptible in the current state
whenever any susceptible antibiotic is available. This is an action constraint,
not a reward term.

## 2. Feasible Actions

For resistance state $s$, define:

$$
A_{\mathrm{feasible}}(s)=\{a\in A : \text{antibiotic }a\text{ is susceptible in }s\}.
$$

The seven-action Gymnasium space remains fixed. Policies use the environment's
action mask; the exact planner maximizes only over $A_{\mathrm{feasible}}(s)$.
If all antibiotics are resistant, the episode is terminal and no action is
selected. Direct transition queries remain available for auditing model
transitions, including infeasible actions; they do not make those actions legal
policy choices.

## 3. Reward

Let $N_R(s)$ be the number of resistant antibiotics in state $s$. For a
transition to $s_{t+1}$, the reward is:

$$
r_t=-\frac{N_R(s_{t+1})}{7}.
$$

The denominator is the number of antibiotics in the defined action space. It
normalizes the per-step resistant fraction to $[0,1]$; it is not an empirically
calibrated biological parameter. No separate immediate-effectiveness bonus,
resistance-emergence penalty, or exposure penalty is included.

With horizon $H$ and $\gamma=1$, the objective is to minimize cumulative
post-transition resistance burden:

$$
\max_\pi\;\mathbb{E}_\pi\left[\sum_{t=0}^{H-1}r_t\right]
=-\min_\pi\;\mathbb{E}_\pi\left[\sum_{t=0}^{H-1}\frac{N_R(s_{t+1})}{7}\right],
$$

subject to $a_t\in A_{\mathrm{feasible}}(s_t)$ whenever the feasible set is
nonempty. This measures resistance burden over time, not merely emergence
events or the final resistant-drug count.

## 4. Terminal Convention and Discounting

The horizon is fixed at $H$ steps. If all seven antibiotics are already
resistant at reset, or become resistant after step $k<H$, that state is treated
as persisting for the remaining horizon. Initially all-resistant episodes
receive a terminal reward adjustment of $-H$ without inventing an action. If
all resistance is reached after a transition, that transition reward includes
the remaining unit-burden terms. This prevents early termination from avoiding
the cost of a persistently all-resistant state. Other terminal conditions do
not occur before the configured horizon in the current model.

The approved discount factor is $\gamma=1$. The exact planner rejects other
values because the terminal-tail accounting and the specified objective are
undiscounted. Changing the discount factor would define a different objective
and requires a separate specification.

## 5. Interpretation of Objectives and Metrics

| Concern | Current treatment |
|---|---|
| Treat effectively now | Hard feasibility constraint based on modeled susceptibility |
| Avoid resistance emergence | Measured separately as the count/rate of transitions that increase resistant-drug count |
| Preserve future treatment options | Represented by minimizing resistance burden throughout the horizon; drug identity still matters through downstream transitions |
| Avoid unnecessary exposure | Not modeled as an objective; action count is reported as a proxy only |

In the binary seven-drug state, final susceptible-drug count is $7-N_R(s_H)$.
That count complements final resistance count, but it does not encode the
identity-dependent value of future transitions. The planner's continuation
values capture identity only relative to the specified transition model and
this reward; they are not independent evidence that a particular drug is
clinically more valuable.

The current environment has no treatment-need state, recovery/clearance state,
or no-treatment/stop action. Therefore, it cannot identify unnecessary
antibiotic use. Cumulative antibiotic exposure is the number of treatment
actions, not dose, duration, drug-days, toxicity, or a clinical stewardship
measure. It remains an evaluation outcome and is excluded from the reward.

The model records seven binary resistance indicators; it does not apply a
formal clinical multidrug-resistance classification. Claims should refer to
simulated resistance burden unless such a classification is separately
defined.

## 6. Implementation Provenance

`RewardSpecification` records the objective name, normalization, and terminal
convention in evaluation output and configuration fingerprints. There are no
tunable reward weights in the current objective. Effectiveness remains present
in evaluation records as a model-defined susceptibility outcome, allowing
constraint compliance to be checked.

This is a computational objective for the stated state/action/transition
model, not a universally validated stewardship utility function or a clinical
recommendation. Results depend on the interaction data, candidate-generation
rules, transition scenario, horizon, and action-feasibility constraint.