# Scientific model

The environment represents antibiotic susceptibility as a binary research abstraction. It does not model a patient, bacterial population size, infection anatomy, dose, pharmacokinetics, recovery or clinical treatment success. Public UI wording uses *analysis* and *strategy evaluation*; source modules and API routes retain their simulation names for compatibility.

## States, observations and actions

| Index | Antibiotic | Code |
| --- | --- | --- |
| 0 | Ciprofloxacin | CIP |
| 1 | Nitrofurantoin | NIT |
| 2 | Fosfomycin | FOS |
| 3 | Trimethoprim | TMP |
| 4 | Gentamicin | GEN |
| 5 | Mecillinam | MEC |
| 6 | Ceftazidime | CAZ |

This order is fixed across CSVs, observations, checkpoints and the API. A seven-bit profile uses `0` for susceptible and `1` for resistant: 128 mathematically possible profiles, not 128 measured isolates. Model Explorer groups these by resistant count; its colors do not encode biological distance, prevalence or transition probability.

The policy observation has 15 values: seven resistance bits, seven one-hot values for the previous action (all zero initially), and the current step. Previous action and step matter when evaluating a policy; the resistance profile alone is not its complete input.

Actions select one of the seven antibiotics. A hard mask permits only currently susceptible drugs during PPO prediction, DQN exploration, greedy prediction and Bellman-target computation, and baseline sampling. An all-resistant profile is terminal with no invented action. The random susceptible-action baseline samples uniformly from eligible actions; internal legacy names such as `greedy` refer to this baseline, not a second trained model.

## Transition evidence

`data/processed/empirical_interactions.csv` contains 30 directed records across 18 antibiotic pairs. The evidence registry also retains 15 records whose direction is unknown; those are excluded from the training interaction table. Public MIC and outcome extracts, URLs and hashes are retained under `data/research/transition-data-2026-10-23/`. They support modeled relationships, not empirically calibrated clinical probabilities.

For an action A, the generator considers directed A-to-B relationships applicable to the current binary state:

| Relationship | Applicable target | Result |
| --- | --- | --- |
| Cross-resistance (XR) | B currently susceptible | B becomes resistant |
| Collateral sensitivity (CS) | B currently resistant | B becomes susceptible |
| Neutral | Represented target | Profile stays unchanged |

Only one candidate outcome is sampled per step. Duplicate target/outcome candidates are merged with their source IDs, so duplicate citations do not increase sampling weight. A transition's evidence explains the simulator relationship; it does not explain the internal reasoning of PPO or DQN.

`REF_UNIFORM_SUPPORTED` assigns equal probability to unique applicable candidates, including neutral ones. This is a scenario assumption. In sensitivity scenarios `SENSITIVITY_Q_000`, `_025`, `_050`, `_075`, `_100`, resistance-changing candidates share occurrence probability q; the remaining probability leaves the profile unchanged. If only neutral candidates exist they are sampled uniformly. None of these scenarios adds missing relationships.

When there is no applicable candidate, the state remains unchanged and the trace records `unsupported_no_candidate`. This can reflect absent directed data or a relationship that cannot change the selected state. It is a coverage gap, not evidence that the drug is safe or effective. The Model Explorer derives coverage from the actual generator for each selected state rather than hard-coding gaps by drug.

## Reward and horizon

The reference horizon H is eight actions with discount factor 1. After each action, the reward is `-(number of resistant antibiotics after the step) / 7`. Cumulative resistance burden is the negative episode return. If all drugs become resistant, the terminal cost continues through the remaining horizon; an initially all-resistant state has zero actions, return `-H` and burden H.

The environment does not introduce selected-drug self-resistance. The selected drug therefore remains susceptible, and current nonterminal episodes reach the full horizon. Exposure is contextual rather than an independently optimized clinical endpoint.

## Reported metrics

The service returns definitions with every result and the API stores them with the run. Their implementation is in `ml/src/metrics.py`, `service/rollout.py` and `simulation/reward.py`; the API validates names against `MetricCatalogue`.

| Metric | Meaning |
| --- | --- |
| Cumulative resistance burden | Sum of normalized resistant counts plus any terminal-tail cost; lower is less modeled burden |
| Initial resistant count | Resistant antibiotics before any action |
| Final resistant / susceptible count | Counts in the final profile, summing to seven |
| Susceptible-count change | Final susceptible count minus initial susceptible count |
| Resistance-emergence events / rate | Steps after which resistant count increased; rate divides by actions and is null for no actions |
| Treatment steps / cumulative antibiotic exposure | Number of actions executed; one administration per step |
| Unsupported-step count | Actions with no applicable candidate transition |
| Susceptible-action rate | Fraction of actions satisfying susceptibility; null for no actions |
| Cumulative reward | Sum of rewards including terminal adjustment; negative burden |

Susceptible-action rate is a mask-compliance check. A value of 100% does not establish efficacy. An unchanged profile likewise does not demonstrate bacterial clearance. The urinary-tract 3D illustration is aesthetic and is not a biological output of this model.

## Interpreting comparisons

PPO and DQN are frozen deterministic policies during app use. Training is an offline workflow; clicking Run Analysis executes inference and does not update model weights. The baseline has no checkpoint.

A paired comparison shares the initial profile, environment seed, scenario, horizon, data identity, reward, mask and per-step transition seeds. Actions can differ, so candidate sets and sampled outcomes can differ despite identical seeds. One comparison is one stochastic episode per strategy and cannot establish an overall algorithm winner. Saved Insights collections are descriptive selections of past evidence, not independent training replicates.

Important limitations include sparse and study-dependent evidence, assumed transition probabilities, unknown-direction records excluded from training, binary resistance without MIC dynamics, and absent self-resistance and recovery. From `0000000`, both frozen policies repeat fosfomycin with zero modeled burden and unsupported transitions throughout: this is a model limitation, not established biological safety. See [research methods](research.md) for the exact model review and sensitivity checks.
