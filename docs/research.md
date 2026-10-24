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

## Frozen policies and selection

The active release is `artifacts/frozen/public-data-v2/`: PPO seed 19000 and DQN seed 15000, their configurations, training summaries, shared interaction snapshot, manifests, selection records and checksums. Selection ranks final checkpoints by lowest burden on fresh validation draws (128 profiles times five seed blocks), then fewer emergence events, more remaining options, and lower training seed. Separate confirmation draws are recorded without reselection. The baseline is code plus recorded RNG seeds, not a third trained checkpoint.

```powershell
# Reproduce selection into a new directory after completing the benchmark.
.\.venv\Scripts\python.exe -B -m experiments.freeze_models `
  --study-dir experiments\runs\public-data-v2 `
  --output-dir artifacts\frozen\public-data-v2-reselection

# Verify the current release; text checksums normalize CRLF to LF.
.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums
```

Selection does not automatically change the app. `ml/frozen_ppo_manifest.json` is the active PPO manifest and the template for future selection; DQN's active manifest is configured in `service/runtime.py`. After a deliberate promotion, update both references, retain matching snapshots/checksums and rerun the checks before restarting Python. The service validates checkpoint hashes, data hashes and the inference contract before becoming ready. Do not alter a checkpoint or its pinned data in place.

The full study's generated checkpoints and reports are not distributed with a fresh checkout. They can be recreated with the commands above; the selected checkpoints and their provenance are distributed so the app runs without retraining.

## Exact conditional model review

`experiments/review_frozen_policies.py` enumerates modeled transition distributions and uses finite-horizon backward induction to calculate the exact optimum, then evaluates each frozen policy with its full observation, including previous action and step.

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

## Dependencies and attribution

`ml/requirements-lock.txt` retains the pinned scientific, plotting and test dependency closure used by the research environment. `service/requirements.txt` defines inference-service dependencies. Notebook tooling is not required. Preserve `ml/third-party-notices.txt`: the masked DQN implementation adapts Stable-Baselines3 code and retains its attribution. Dataset source IDs and `sources.json` are part of the scientific provenance.
