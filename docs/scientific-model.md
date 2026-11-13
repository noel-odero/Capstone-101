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

Actions select one of the seven antibiotics. The active evidence-aware release permits an action only when the drug is currently susceptible **and** the transition generator has an applicable candidate for that state. PPO, DQN exploration and prediction, DQN Bellman targets, and the random baseline use the same restriction. Explicit neutral candidates remain allowed. An all-resistant profile is terminal; a nonterminal profile with no permitted action reaches an evidence boundary. Neither condition invents an action. Internal legacy names such as `greedy` refer to the random baseline, not a second trained model.

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

Candidate absence can reflect missing directed data or a relationship that is inapplicable to the selected state. Current policies exclude such actions. Earlier saved analyses used a susceptible-only mask and recorded an unchanged profile with `unsupported_no_candidate`; those records retain their original values and provenance. In either case, absence is not evidence of safety or effectiveness. Model Explorer derives coverage from the actual generator for each state rather than hard-coding gaps by drug. Of 448 susceptible state/action pairs, 64 have no applicable candidate; 50 additional pairs have explicit neutral-only candidates and remain permitted.

## Reward and horizon

The reference horizon H is eight stages with discount factor 1. After each action, the ordinary reward remains `-(number of resistant antibiotics after the step) / 7`. If all drugs become resistant, the absorbing cost continues through the remaining horizon; an initially all-resistant state has zero actions, return `-H` and burden H.

If an evidence boundary is reached with k stages remaining, evaluation stops. Training charges a conservative continuation cost of k and performs no future bootstrap. This prevents free early termination without pretending to observe future resistance. The negative return is therefore a **pessimistic objective score**, which includes this uncertainty cost. Full-horizon resistance burden is `null` for incomplete evaluations; observed-prefix burden and uncertainty continuation cost are reported separately. The current table produces one initial boundary state, `1111110`, whose only susceptible action has no applicable candidate.

The active release adds no repetition penalty or selected-drug self-resistance. Repetition can still occur through supported neutral outcomes or modeled cycles; evidence restrictions close the unsupported-action shortcut, not these broader biological limitations. Exposure remains contextual rather than an independently optimized clinical endpoint.

## Reported metrics

The service returns definitions with every result and the API stores them with the run. Their implementation is in `ml/src/metrics.py`, `service/rollout.py` and `simulation/reward.py`; the API validates names against `MetricCatalogue`.

| Metric | Meaning |
| --- | --- |
| Cumulative resistance burden | Full-horizon normalized resistant counts, including the all-resistant tail; null at an evidence boundary |
| Initial resistant count | Resistant antibiotics before any action |
| Final resistant / susceptible count | Last recorded profile counts; the UI withholds final outcomes for incomplete evaluations |
| Susceptible-count change | Final susceptible count minus initial susceptible count |
| Resistance-emergence events / rate | Steps after which resistant count increased; rate divides by actions and is null for no actions |
| Treatment steps / cumulative antibiotic exposure | Number of actions executed; one administration per step |
| Unsupported-step count | Actions with no applicable candidate transition; zero under the current evidence restriction |
| Susceptible-action rate | Fraction of actions satisfying susceptibility; null for no actions |
| Cumulative reward | Negative pessimistic score; includes conservative continuation cost when incomplete |
| Evaluation complete / uncertainty continuation cost | Whether an evidence boundary stopped evaluation, and the separately reported conservative cost |

Susceptible-action rate is a mask-compliance check. A value of 100% does not establish efficacy. An unchanged profile likewise does not demonstrate bacterial clearance. The urinary-tract 3D illustration is aesthetic and is not a biological output of this model.

## Interpreting comparisons

PPO and DQN are frozen deterministic policies during app use. Training is an offline workflow; clicking Run Analysis executes inference and does not update model weights. The baseline has no checkpoint.

A paired comparison shares the initial profile, environment seed, scenario, horizon, data identity, reward, mask and per-step transition seeds. Actions can differ, so candidate sets and sampled outcomes can differ despite identical seeds. One comparison is one stochastic episode per strategy and cannot establish an overall algorithm winner. Saved Insights collections are descriptive selections of past evidence, not independent training replicates.

Important limitations include sparse and study-dependent evidence, assumed transition probabilities, unknown-direction records excluded from training, binary resistance without MIC dynamics, and absent self-resistance and recovery. A complete supported trajectory can still exploit simplified neutral dynamics; it is not evidence of biological safety. The original release's repeated unsupported fosfomycin selections motivated the evidence-aware retraining. See [research methods](research.md) for the study, checkpoint selection and retained limitations.
