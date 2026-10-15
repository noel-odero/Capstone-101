# Antibiotic Stewardship Simulation for Multidrug-Resistant *E. coli*

A research and software prototype. It simulates how binary antibiotic resistance in an MDR *E. coli* population changes after treatment actions, and compares a masked PPO policy with a Greedy baseline in that simulated environment.

This repository is a clinical decision-support system but it does not diagnose infections, recommend treatment for individual patients, or claim clinical superiority, effectiveness, or optimality of any policy.

## Scientific scope and caveats

The full scientific specification is in [docs/scientific-specification](docs/scientific-specification). The reward is defined in [reward-function.md](docs/scientific-specification/reward-function.md), and transition modeling is in [resistance-transition-model.md](docs/scientific-specification/resistance-transition-model.md).


## Repository layout

```text
artifacts/ppo/                        20 final PPO checkpoints with per-seed provenance
data/processed/                       Processed CSVs used by the simulator and its tests
docs/scientific-specification/        Scientific specification and study runbook
docs/figures/ppo/              Approved Step 9a study figures and provenance JSON
experiments/ppo_baseline_config.json  PPO configuration
ml/src/                               PPO training, evaluation, Greedy baseline, study tooling
ml/tests/                             ML pipeline tests
simulation/                           Resistance state, actions, transitions, environment, reward
tests/                                Simulation and data tests
```

## Setup

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r ml/requirements.txt
```

## Run the tests

```powershell
python -m pytest
```

The suite covers the simulation core (state, actions, transitions, environment, reward), the PPO pipeline, and the seed-study helpers.

## Final PPO checkpoints

`artifacts/ppo/ppo_seed_<S>/` contains one folder for each of the 20 training seeds, from 1000 to 20000 in steps of 1000:

* `final_model.zip`: the MaskablePPO checkpoint. Its SHA-256 was checked against the research archive manifest.
* `config.json`, `environment_manifest.json`, `training_summary.json`: per-seed training provenance.
* `training_ledger.json`: run ledger for seeds 6000 to 20000. Seeds 1000 to 5000 have no ledger in the canonical study folder.

Shared files:

* `protocol_lock.json`: study protocol lock.
* `checkpoint_manifest.json`: per-checkpoint source paths, SHA-256 hashes, sizes, and archive match status.
* `SHA256SUMS.txt`: hashes for every file under `artifacts/ppo/` except itself. Binary files (`final_model.zip`) are hashed as raw bytes. Text files (`.json`, `.txt`, `.csv`, `.md`) are hashed after CRLF to LF normalization, so the same hash holds for Windows (CRLF) and Linux (LF) checkouts.

Per-episode training logs (`training_episodes.json`) are not included in this repository.
To verify a checkpoint, compute its hash and compare it with `checkpoint_manifest.json`:

```powershell
Get-FileHash -Algorithm SHA256 artifacts\ppo\ppo_seed_1000\final_model.zip
```

Load a checkpoint in Python with `load_ppo_model` from [ml/src/ppo_training.py](ml/src/ppo_training.py).

To verify every file against `SHA256SUMS.txt` under that policy, from the repository root (exit code 0 means all verified):

```powershell
.\.venv\Scripts\python.exe -m ml.src.artifact_checksums
```

On a Linux checkout, `cd artifacts/ppo && sha256sum -c SHA256SUMS.txt` gives the same result because the files are already LF. The hashes embedded in `checkpoint_manifest.json` for `protocol_lock.json` and the per-seed provenance files are not covered by this policy and were left unchanged.

## Study figures

`docs/figures/ppo-step9a/` contains four figures and their provenance file:

* `primary_burden_interval.png`
* `per_seed_paired_difference.png`
* `secondary_outcomes_interval.png`
* `seed_profile_difference_heatmap.png`
* `study_figures_provenance.json`

[ml/src/study_figures.py](ml/src/study_figures.py) regenerates these figures from the canonical study outputs in `experiments/results/ppo_step9a_multiseed`. Those outputs are not part of this repository, so the script cannot run here as-is. The provenance file records the input and output hashes.

## Study commands

The study tooling in [ml/src/ppo_seed_study.py](ml/src/ppo_seed_study.py) operates on the canonical study root by default. Its subcommands are `train`, `quarantine`, `verify`, `evaluate`, `report`, and `quarantine-evaluation`. Exit codes are 0 for success, 1 for an incomplete verification, 2 for a refused action, and 3 for a failed run.

`verify` writes `manifest.json` into the study root, so run it only against a complete canonical study. The runbook is in [docs/scientific-specification/ppo-seed-study-runbook.md](docs/scientific-specification/ppo-seed-study-runbook.md).

