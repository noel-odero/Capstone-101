# Evaluation Metrics Specification

## 1. Purpose

The evaluation metrics define how treatment policies are compared within the
simulated MDR E. coli antibiotic stewardship environment.

The evaluation framework is separate from the RL reward function. The reward
function defines the objective optimized during training, while the evaluation
metrics measure the resulting policy across clinically and computationally
relevant outcomes.

No individual metric is treated as a complete measure of stewardship quality.

---

## 2. Primary Metrics

### 2.1 Treatment Effectiveness Rate

Treatment Effectiveness Rate (TER) is the proportion of treatment actions
for which the selected antibiotic is susceptible in the true simulated
resistance state.

TER = effective treatment steps / total treatment steps

Higher values indicate that a policy more frequently selects an antibiotic
that is effective against the current simulated resistance state.

---

### 2.2 Resistance Emergence Rate

Resistance Emergence Rate (RER) is the proportion of environment
transitions that increase the number of resistant antibiotics.

For each transition:

ΔR_t = N_R(S_{t+1}) - N_R(S_t)

A resistance-emergence event occurs when:

ΔR_t > 0

RER = resistance-increasing transitions / total transitions

Lower values indicate fewer resistance-increasing transitions.

---

### 2.3 Future Effective Antibiotics

Future Effective Antibiotics (FEA) is the number of antibiotics remaining
susceptible at the end of an episode.

FEA = N_S(S_T)

The MVP action space contains seven antibiotics, so FEA ranges from 0 to 7.

Higher values indicate greater preservation of future treatment options.

The change from the initial state is also recorded:

ΔFEA = N_S(S_T) - N_S(S_0)

---

### 2.4 Cumulative Antibiotic Exposure

Cumulative Antibiotic Exposure (CAE) is the number of antibiotic treatment
actions taken during an episode.

CAE = number of treatment actions

Lower exposure is desirable only when considered alongside treatment
effectiveness and resistance outcomes.

Low exposure alone does not indicate a better policy.

---

## 3. Deferred Metric

### 3.1 Episode Treatment Success

Episode-level treatment success will be defined once the environment includes
an explicit infection-clearance model.

Success = 1 if the episode reaches successful clearance
Success = 0 otherwise

This metric is not included in the current MVP because the simulation does
not yet model infection clearance.

---

## 4. Secondary Metrics

### 4.1 Cumulative Reward

Cumulative reward for an episode is:

G = Σ R_t

Cumulative reward is used to assess the objective optimized by the RL agent.

It is not treated as the primary outcome because the reward function itself
is a model-design choice.

---

### 4.2 Policy Stability

Each policy will be evaluated across multiple random seeds.

For each metric, the evaluation will report the mean and uncertainty across
evaluation episodes.

This reduces the influence of individual stochastic simulation outcomes.

---

### 4.3 Generalization

Policies will be evaluated on both scenarios used during training and
held-out scenarios.

Held-out evaluation may vary:

- initial resistance states;
- random seeds;
- resistance-transition configurations;
- treatment trajectories.

The purpose is to determine whether learned behaviour generalizes beyond
training scenarios.

---

## 5. Policy Comparison

The primary comparison will be between the PPO policy and the defined
baseline policies.

The same initial conditions and random seeds should be used when comparing
policies where practical.

This creates paired episode-level observations and reduces variation caused
by different simulation conditions.

No assumption is made that PPO must outperform the baseline.

Possible outcomes include:

- PPO performs better;
- PPO performs similarly;
- PPO performs worse.

All outcomes are retained and reported.

---

## 6. Statistical Reporting

For each primary metric, evaluation will report:

- mean;
- median where appropriate;
- standard deviation;
- 95% confidence interval;
- paired difference between policies.

Statistical tests will be selected according to the distribution and pairing
of the evaluated outcomes.

Where parametric assumptions are not appropriate, a non-parametric paired
test may be used.

Statistical significance will not be treated as the sole indicator of
practical importance.

---

## 7. Multi-Metric Interpretation

Policy evaluation will retain the individual metric values rather than
collapsing all outcomes into a single score.

The primary outcome vector is:

(E, R, F, X)

where:

- E = treatment effectiveness;
- R = resistance emergence;
- F = future effective antibiotics;
- X = cumulative antibiotic exposure.

This allows trade-offs between effectiveness, resistance, future treatment
options, and antibiotic exposure to remain visible.

A policy that improves one metric while substantially worsening another will
therefore not be described using a single aggregate metric.

---

## 8. Assumptions

The evaluation framework assumes:

1. The simulated resistance state is a useful computational abstraction of
   bacterial resistance.

2. Treatment effectiveness can be determined from the true simulated
   resistance state.

3. Resistance emergence can be identified by comparing consecutive
   resistance states.

4. Future treatment options can be approximated by the number of antibiotics
   remaining susceptible.

5. Antibiotic exposure can be approximated by the number of treatment
   actions.

6. Multiple random seeds are required because the simulation contains
   stochastic transitions.

---

## 9. Limitations

The metrics do not directly measure:

- patient mortality;
- clinical cure;
- adverse drug reactions;
- patient adherence;
- antibiotic toxicity;
- dosage;
- pharmacokinetics;
- pharmacodynamics;
- reinfection;
- healthcare costs;
- patient-specific clinical outcomes.

The metrics therefore evaluate policies within the simulated environment
rather than establishing clinical effectiveness.