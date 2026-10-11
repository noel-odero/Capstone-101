# PPO Seed Study Runbook (Step 9A)

Module: `ml/src/ppo_seed_study.py`. Run from the workspace root with `.\.venv\Scripts\python.exe`.

## Fixed protocol

- Training budget: `TOTAL_TIMESTEPS = 100000`. Realized budget is the rollout-aligned count `ceil(100000 / n_steps) * n_steps` (100096 for `n_steps` 256).
- Training seeds: retained 1000 to 5000, new 6000 to 20000 in steps of 1000 (15 new seeds).
- Evaluation: 128 canonical profiles, matched-policy base seed 900001.
- Burden ties: differences within `BURDEN_TIE_TOLERANCE = 1e-12` count as ties. Nonzero per-seed burden differences are multiples of about 2.2e-4, so the tolerance only absorbs float64 error (about 2e-14).

## Failure recovery

1. Failed or interrupted seeds are never deleted. `quarantine --seed S --reason TEXT` moves the seed's ledger and run directory to `root/quarantine/`.
2. Only seeds with ledger status `failed` or `started` can be quarantined by default. A completed seed is quarantined only with `quarantine --seed S --reason TEXT --invalid-completed`, and only when `verify` reports its training as invalid. A completed seed that verifies complete is never quarantined.
3. Before quarantining an interrupted seed, confirm that no training process is still writing to its run directory.
4. After quarantine, `train --seed S` reruns the same seed under the unchanged protocol. The seed set and protocol do not change.
5. If the seed set or any protocol field changes, the protocol lock mismatches. `train` refuses unless `--confirm-protocol-change` is given. That option moves the old lock and all batch state (`run_ledger/`, `training/`, `evaluation/`, `manifest.json`) to one `root/quarantine/<stamp>_protocol_change/` directory and writes a new lock. Nothing is deleted, and no old artifact can enter the new batch.
6. A missing lock with batch state present is refused. Restoring the lock by hand does not bypass this; use `--confirm-protocol-change` only if the protocol change is intended.
7. `verify` must report `protocol_lock: match` and `training_complete` before `evaluate` or `report` will run.
8. Evaluation recovery: if `evaluate` refuses with an `interrupted` or `failed` evaluation state (ledger `started` or `failed`, or an output directory with no ledger), run `quarantine-evaluation --reason TEXT`. It moves `run_ledger/evaluation.json` and `evaluation/` to `root/quarantine/<stamp>_evaluation/` and writes `quarantine_reason.json` there (reason, verification status and problems, previous ledger, and moved paths). Training runs, training ledgers, the protocol lock, and the seed set are not touched.
9. A completed, valid evaluation is never quarantined or overwritten. `quarantine-evaluation` refuses in that case, and `evaluate` refuses while any evaluation ledger or output directory exists.
10. Artifact integrity: when a new seed completes, its `final_model.zip` hash is stored in its ledger as `checkpoint_sha256`, and its `config.json` and `training_summary.json` hashes are stored as `metadata_sha256`. `verify` requires these recorded values and flags any live file that differs. A completed ledger without a checkpoint hash is incompatible; such ledgers from earlier runs cannot be verified and must be quarantined under item 11 or retrained after quarantine. The five retained seeds (1000 to 5000) are also pinned to canonical hashes. Evaluation receives the verified checkpoint and metadata hashes, reads each checkpoint once, refuses before writing any output if a hash differs, and re-verifies the batch before the evaluation ledger is marked `completed`; a failed re-verification records the evaluation as `failed`. The evaluation `config.json` records the metadata hashes it consumed.
11. Invalid completed seed: if `verify` reports a completed new seed as incompatible (for example, its checkpoint or metadata changed after completion), run `quarantine --seed S --reason TEXT --invalid-completed`. This moves the ledger and run directory to `root/quarantine/` with the verification status and problems in `quarantine_reason.json`, and the checkpoint and metadata stay there as evidence. Then run `train --seed S`. Quarantining any training seed leaves an existing evaluation incompatible, so run `quarantine-evaluation --reason TEXT` before `evaluate` is rerun.
12. Undefined rates: a rate with no transitions is undefined and is written as an empty cell in `raw_results.csv`. `verify` treats an empty cell as undefined (not zero), and two strategies are compared as undefined only when both are undefined. `report` excludes undefined values for that metric only: each per-seed mean uses defined cases, a seed with no defined difference is listed under `excluded_training_seeds` for that metric, and `defined_case_count` is recorded per training seed. A metric with fewer than two defined seeds refuses the report. The primary metric is always defined and is unaffected.

## Commands

Timing pilot (not part of the study; writes to a temp directory):

```powershell
Measure-Command { .\.venv\Scripts\python.exe -m ml.src.ppo_training --config experiments/ppo_baseline_config.json --output-dir $env:TEMP\step9a_timing_pilot --seed 6000 --total-timesteps 4096 } | Select-Object TotalSeconds
```

Study (run only after approval):

```powershell
foreach ($s in 6000,7000,8000,9000,10000,11000,12000,13000,14000,15000,16000,17000,18000,19000,20000) { .\.venv\Scripts\python.exe -m ml.src.ppo_seed_study train --seed $s; if ($LASTEXITCODE -ne 0) { break } }
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study verify
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study evaluate
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study verify
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study report
```

Invalid completed seed recovery (only after `verify` reports the seed incompatible; `S` is the seed):

```powershell
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study quarantine --seed S --reason "<reason>" --invalid-completed
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study train --seed S
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study quarantine-evaluation --reason "<reason>"
```

The `quarantine-evaluation` line is needed only if an evaluation directory or ledger already exists.

Evaluation recovery (only after `evaluate` refuses with an interrupted or failed evaluation, and only once no evaluate process is running):

```powershell
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study quarantine-evaluation --reason "<reason>"
.\.venv\Scripts\python.exe -m ml.src.ppo_seed_study evaluate
```

## Exit codes

- `0`: success
- `1`: batch incomplete. `verify` returns this until both training and evaluation are complete, so it is expected after training and before evaluation.
- `2`: refused before training, evaluation, or report; study state unchanged
- `3`: a training run or the evaluation run raised an error. A failed training run leaves a `failed` ledger; the failure is printed to stderr.
