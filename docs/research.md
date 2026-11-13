# Research and retraining

Run commands from the repository root using the module form (`-m`); direct script execution can fail to resolve `ml` and `simulation` imports. Generated study outputs in `experiments/runs`, `experiments/results` and `experiments/logs` are ignored by Git.

## Data provenance

The authoritative training inputs are in `data/processed/`. The four CSVs in `data/versions/interactions-v1/` are derivation inputs: `experiments/integrate_public_evidence.py` combines them with the retained public extracts under `data/research/transition-data-2026-10-23/`. `sources.json` records source locations and hashes. Keep these inputs to reproduce the processed tables.

```powershell
# Validate the processed tables without changing them.
.\.venv\Scripts\python.exe -B -m experiments.integrate_public_evidence --check

# Rebuild the processed tables if their source extracts change.
.\.venv\Scripts\python.exe -B -m experiments.integrate_public_evidence
```

Directional MIC/outcome evidence informs the candidate relationships. Transition occurrence probabilities remain scenario assumptions. Unknown-direction relationships remain in the registry for transparency, not in the training interaction table. [Scientific model](scientific-model.md) defines these distinctions.

## Three-strategy benchmark

`experiments/dqn_public_data_v2_config.json` pins the processed-data hash, seed schedule and 100,096 environment-interaction budget per trained model. It uses `experiments/ppo_baseline_config.json` for shared environment/PPO settings. Twenty training seeds (1000 through 20000 in steps of 1000) train both PPO and DQN. Update schedules and compute cost differ; only interaction budgets are matched.

```powershell
.\.venv\Scripts\python.exe -B -m ml.src.dqn_benchmark `
  --config experiments\dqn_public_data_v2_config.json `
  --output-dir experiments\runs\public-data-v2

.\.venv\Scripts\python.exe -B -m experiments.analyze_dqn_study `
  --study-dir experiments\runs\public-data-v2 `
  --output-dir experiments\results\public-data-v2-review
```

New output directories must be empty. Add `--resume` to the benchmark command to continue the same study; resume verifies the configuration, data and completed checkpoints instead of silently retraining them. The analyzer audits feasible actions, saved traces, paired comparisons and uncertainty.

Both policies train on all 127 nonterminal resistance profiles and evaluate all 128 profiles over five RNG seed blocks. Evaluation holds out stochastic draws, not resistance profiles. Episode/profile/seed-block results are averaged within each training replicate before summarizing across replicates. Reused baseline draws are not extra independent baseline samples. Matching environment seeds does not guarantee matching transitions after different actions.

Confidence intervals and paired tests are implemented in `ml/src/confidence_intervals.py` and `ml/src/statistical_comparison.py`. Respect their assumption warnings, especially skew and small sample counts. A single run, selected failure case, validation checkpoint or conditional planner review is not an independent training replicate. The completed twenty-seed comparison did not establish a clear PPO/DQN winner.

## Archived release and selection

The previous release remains archived at `artifacts/frozen/public-data-v2/`: PPO seed 19000 and DQN seed 15000, their configurations, training summaries, shared interaction snapshot, manifests, selection records and checksums. Its selection ranked final checkpoints by validation burden, then fewer emergence events, more remaining options and lower seed. The active evidence-aware release is described below. The baseline is code plus recorded RNG seeds, not a third trained checkpoint.

```powershell
# Reproduce selection into a new directory after completing the benchmark.
.\.venv\Scripts\python.exe -B -m experiments.freeze_models `
  --study-dir experiments\runs\public-data-v2 `
  --output-dir artifacts\frozen\public-data-v2-reselection

# Verify the archived release; text checksums normalize CRLF to LF.
.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums `
  --sums artifacts\frozen\public-data-v2\SHA256SUMS.txt
```

Selection does not automatically change the app. `ml/frozen_ppo_manifest.json` is the active PPO manifest; DQN's active manifest is configured in `service/runtime.py`. After a deliberate promotion, update both references, retain matching snapshots/checksums and rerun the checks before restarting Python. The service validates checkpoint hashes, data hashes and the inference contract before becoming ready. Do not alter a checkpoint or its pinned data in place.

The full study's generated checkpoints and reports are not distributed with a fresh checkout. They can be recreated with the commands above; the selected checkpoints and their provenance are distributed so the app runs without retraining.

## Exact conditional model review

`experiments/review_frozen_policies.py` explicitly loads the archived public-data-v2 release, enumerates its transition distributions and uses finite-horizon backward induction to calculate the exact optimum. It evaluates each policy with its full observation, including previous action and step. Its results concern the original rules, not the active evidence restriction.

```powershell
.\.venv\Scripts\python.exe -B -m experiments.review_frozen_policies `
  --output-dir experiments\results\model-review
```

The output directory must be empty. Outputs include `review.json`, all-profile `profiles.csv`, resistance-stratified `strata.csv` and `review.png`. All 128 profiles remain in the CSV, including the terminal profile. The review also evaluates q=0.25, 0.50 and 0.75 occurrence scenarios with fixed policies.

| Reference scenario, 127 nonterminal profiles | Expected burden | Gap above exact optimum |
| --- | ---: | ---: |
| Exact planner | 2.8124 | 0 |
| PPO | 2.8512 | 0.0388 |
| DQN | 2.8392 | 0.0268 |
| Random susceptible baseline | 3.7506 | 0.9382 |

These are expectations conditional on the simulator and two selected checkpoints, not a new across-training comparison or clinical validation. Of 448 feasible state/action pairs, 64 have no applicable candidate; 114 force an unchanged state, including modeled neutral outcomes. Agreement between policies can reflect optimization of the same restricted objective. Sensitivity scenarios do not resolve unknown relationships or introduce self-resistance.

## Evidence-aware study and active release

`experiments/evidence_aware_study.py` tests the unchanged-state shortcut with the shared environment in `experiments/evidence_environment.py`. The app now points to `artifacts/frozen/evidence-aware-v3/`. Updating a local checkout does not change a running remote deployment until it is rebuilt, migrated and restarted.

The `supported` variant permits an action only when it is susceptible and has an applicable candidate. Explicit neutral candidates remain permitted. Starting states without a permitted action are excluded from training resets (126 training profiles); all 128 profiles remain in evaluation, including the all-resistant state and the evidence-boundary state `1111110`.

The ordinary step cost remains resistant count divided by seven. If a trajectory reaches an evidence boundary with `k` stages remaining, training adds a pessimistic continuation cost `k * (1 + repetition_penalty)` and terminates with no Bellman bootstrap. This bounds the remaining per-stage objective rather than granting free early termination. It is **not** a prediction that all antibiotics become resistant. Evaluation reports the uncertainty cost separately through the pessimistic score; unfinished trajectories have `null` full-horizon burden and final options. The all-resistant state retains the original absorbing-to-horizon convention.

The comparisons include PPO, DQN, uniform random choice within the same allowed set, a genuine immediate-expected-cost policy, and an exact finite-horizon planner. DQN uses the evidence mask during warm-up, epsilon exploration, inference, current replay-action validation and next-state Bellman targets. Its checkpoint archives the mask table. Repetition penalties are separate ablations, not empirical facts.

Run these PowerShell commands from the repository root. These runs use the local Python environment; Docker and the database are not required.

### Stage 1: audit and pipeline check

```powershell
.\.venv\Scripts\python.exe -B -m experiments.evidence_aware_study audit `
  --output-dir experiments\results\evidence-aware-audit

.\.venv\Scripts\python.exe -B -m experiments.evidence_aware_study train `
  --stage smoke --variant supported `
  --output-dir experiments\runs\evidence-aware-smoke
```

The audit reviews the original frozen policies and enumerates evidence coverage and the restricted exact optimum. The smoke run trains each algorithm for only 512 interactions and checks serialization, evaluation and reporting; it establishes pipeline behavior, not performance. Use a new output directory if one already exists, or add `--resume` to a training command with exactly matching code, packages, data and settings.

### Stage 2: three-seed pilot

```powershell
.\.venv\Scripts\python.exe -B -m experiments.evidence_aware_study train `
  --stage pilot --variant supported --workers 2 `
  --output-dir experiments\runs\evidence-aware-pilot
```

Each algorithm receives 16,384 interactions at each of seeds 30000, 31000 and 32000. Evaluation uses all 128 profiles over two random-seed blocks. Start with this variant. Optional pilots use `q000`, `q025`, `q050`, `q075` or `q100` for assumed transition occurrence, and `repeat005` or `repeat010` for repetition penalties 0.05 or 0.10. Each variant needs its own output directory. `legacy` reproduces the original action restriction and fallback for an explicit control. Occurrence-variant pilots retrain in their respective environments; they are not fixed-policy cross-scenario robustness tests.

Inspect `report.md`, `report.json`, `replicate_metrics.csv`, and each seed's `exact_audit.json` and `evaluation.json`. The pessimistic score includes uncertainty cost and any repetition cost; do not label it raw resistance burden. Complete-only burden can involve different subsets between policies, so each replicate also reports burden on the common completed subset. Conditioning on completion can still introduce selection bias. Check completion, unobserved steps, repetitions and unsupported actions alongside score. Exact optimality gaps assess optimization of the specified model, not biological validity. Do not select a variant solely because its differently defined objective gives a smaller number.

### Stage 3: fixed-protocol confirmation

After reviewing the pilot, lock the variant and run:

```powershell
.\.venv\Scripts\python.exe -B -m experiments.evidence_aware_study train `
  --stage full --variant supported --workers 2 `
  --pilot-dir experiments\runs\evidence-aware-pilot `
  --output-dir experiments\runs\evidence-aware-full
```

The full study requires a completed matching pilot and verifies its manifest. It uses twenty training seeds (1000 through 20000), 100,096 interactions per algorithm per seed, and five evaluation-seed blocks distinct from the pilot. Only final checkpoints are candidates for later selection; intermediate validation does not select a checkpoint. The runner records training-seed confidence intervals, exact conditional optimality gaps, checksums, source hashes and dependency versions. Baseline draws are reused across training replicates and do not provide twenty independent baseline samples. Initial profiles are known during training; only random draws are held out. Resume deliberately rejects changed source, dependencies or data; after integration changes, keep completed studies intact and use a new directory for a new study.

```powershell
Get-Content experiments\runs\evidence-aware-pilot\status.json
Get-Content experiments\runs\evidence-aware-pilot\report.md
```

### Completed study and checkpoint selection

The completed twenty-seed reference study recorded zero unsupported learned actions. Mean pessimistic scores were 3.0103 (PPO), 3.0130 (DQN), 3.1040 (myopic) and 3.8230 (random allowed-action baseline); learned-policy completion was 127/128 profiles. The paired DQN-minus-PPO difference was 0.0027, with a 95% training-seed interval of [-0.0116, 0.0171]. These results do not establish an overall PPO/DQN winner and remain conditional on the fixed environment and evaluation design.

`experiments/freeze_evidence_models.py` ranks each algorithm's twenty final checkpoints on fresh validation draws: five seed blocks over all 128 profiles. It minimizes pessimistic score, breaking exact ties by higher completion, fewer repeated selections and lower training seed. Five separate confirmation blocks are evaluated without reselection. The package records every candidate and seed schedule in `selection.json` and `selection.csv`.

| Active checkpoint | Training seed | Validation score | Confirmation score |
| --- | ---: | ---: | ---: |
| PPO | 11000 | 2.9645 | 2.9507 |
| DQN | 15000 | 2.9830 | 2.9431 |

Both selected policies had 127/128 completion and zero unsupported actions on confirmation. These are selected-checkpoint measurements, not independent estimates of algorithm superiority. Models still permit supported neutral repetition and do not model selected-drug self-resistance.

```powershell
# Reproduce selection into a new directory; never overwrite a frozen release.
.\.venv\Scripts\python.exe -B -m experiments.freeze_evidence_models `
  --study-dir experiments\runs\evidence-aware-full `
  --output-dir artifacts\frozen\evidence-aware-reselection --workers 2

.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums
```

The active manifests are `ml/frozen_ppo_manifest.json` and the DQN reference in `service/runtime.py`. Inference validates the dataset identity, evidence mask, environment specification and checkpoint hashes before readiness. Training and inference share the environment code; DQN's archived mask is checked against the derived table. Existing analyses retain their original models, rules and metric definitions. New incomplete evaluations store null full-horizon burden; migration `AllowIncompleteEvaluationBurden` must be applied before using them.

Add `--resume` to the original pilot/full command after an interruption. Resume verifies completed checkpoints, traces and summaries. A partially finished seed is preserved under `interrupted/` and retrained from its beginning; it does not resume an optimizer mid-seed. Changing code, parameters, packages or data requires a new study directory and a new matching pilot. Avoid editing experiment source while a run is active. Use one worker if two workers consume too much memory.

These experiments do not modify CSV evidence, current manifests, frozen checkpoints or the UI. Do not pass the new study to the legacy `freeze_models` command: promotion requires a deliberate inference/API contract update for the evidence mask, incomplete evaluations and revised score. Candidate availability does not validate repeated exposure, and selected-drug self-resistance remains unmodeled. Never add invented transitions to the empirical CSV to make sequences appear varied.

## Dependencies and attribution

`ml/requirements-lock.txt` retains the pinned scientific, plotting and test dependency closure used by the research environment. `service/requirements.txt` defines inference-service dependencies. Notebook tooling is not required. Preserve `ml/third-party-notices.txt`: the masked DQN implementation adapts Stable-Baselines3 code and retains its attribution. Dataset source IDs and `sources.json` are part of the scientific provenance.
