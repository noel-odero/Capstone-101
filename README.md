# StewardLab / AMR Decision Support

A research workbench for exploring antibiotic resistance in a simulated E. coli environment. Save labeled starting profiles, compare frozen PPO and DQN policies with a random susceptible-action baseline, inspect collateral sensitivity and cross-resistance transitions, and revisit saved results.

Research and simulation only. This platform is not validated for clinical prescribing or patient-specific treatment decisions. The 3D bacteria clearance animation is illustrative; the model tracks resistance, not bacterial load.

## Structure

| Folder | Purpose |
| --- | --- |
| `frontend/` | React workbench, authentication, samples, simulation and results |
| `backend/` | ASP.NET Core API, account ownership and PostgreSQL persistence |
| `service/` | Internal Python inference service and frozen-model validation |
| `simulation/` | Resistance state, actions, transitions and reward |
| `ml/` | PPO/DQN training, evaluation and inference contracts |
| `data/processed/` | Scientific inputs and evidence registry |
| `artifacts/` | Frozen policies, data snapshots and checksums |
| `experiments/` | Study configuration, data integration and model selection |
| `docs/` | Scientific specifications, study figures and sample workflow |

The browser calls the .NET API through Vite. The API calls the Python service for scientific computation and stores account-owned samples and completed runs in PostgreSQL.

## Local setup

Requirements: Docker Desktop, .NET 10 SDK (see `backend/global.json`), Node 22.12 or later, and Python with the dependencies in `ml/requirements.txt`. Use the repository `.venv` on Windows; plain `python` may resolve to the Microsoft Store alias.

Run the four components in this order, in separate PowerShell terminals from the repository root. The existing local PostgreSQL container is `amr-test-pg`, exposed on port 55432. The user environment variable `AMR_TEST_POSTGRES` must contain its admin connection string; do not commit credentials.

1. Start PostgreSQL:

   ```powershell
   docker start amr-test-pg
   ```

2. After new migrations, apply them explicitly:

   ```powershell
   cd backend
   $admin = [Environment]::GetEnvironmentVariable('AMR_TEST_POSTGRES', 'User')
   $env:ConnectionStrings__Amr = [regex]::Replace($admin, 'Database=[^;]*', 'Database=amr_frontend_dev')
   dotnet tool restore
   dotnet tool run dotnet-ef database update --project src/Amr.Infrastructure --startup-project src/Amr.Api
   ```

3. Start Python:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```

4. Start the API:

   ```powershell
   $admin = [Environment]::GetEnvironmentVariable('AMR_TEST_POSTGRES', 'User')
   $env:ConnectionStrings__Amr = [regex]::Replace($admin, 'Database=[^;]*', 'Database=amr_frontend_dev')
   $env:ASPNETCORE_ENVIRONMENT = 'Development'
   $env:ASPNETCORE_URLS = 'http://127.0.0.1:5080'
   dotnet run --project backend\src\Amr.Api --no-launch-profile
   ```

5. Start the frontend:

   ```powershell
   cd frontend
   npm ci # first setup or after dependency changes
   npm run dev
   ```

Open http://localhost:5173. Use `npm run dev` to retain the larger HTTP header limit needed when localhost cookies accumulate. Stop each service with Ctrl+C; PostgreSQL can remain running.

Check readiness and the frontend proxy:

```powershell
Invoke-RestMethod http://127.0.0.1:5080/api/v1/health
Invoke-RestMethod http://127.0.0.1:5173/api/v1/auth/session
```

The API requires its connection string and reports `database_migrations_pending` when migrations are missing.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm run build
npm run lint
npm test
```

See [backend testing](backend/README.md#test) for PostgreSQL integration and live service tests. GitHub Actions runs backend, Python and live integration checks.

## Scientific contract and reproducibility

Profiles contain seven binary resistance states, giving 128 possible profiles. Each action selects a currently susceptible antibiotic. Candidate transitions model cross-resistance, collateral sensitivity or neutral changes under `REF_UNIFORM_SUPPORTED`. An empty candidate set leaves the profile unchanged: this can mean absent directed evidence or a relationship that cannot change the current binary state. It is not evidence of treatment success. A comparison is one stochastic episode, not evidence that either strategy is generally superior.

The service validates the checkpoint hash, transition-data hash and frozen manifest before serving runs. Every saved result records model identity, seeds and metric definitions. The active model is selected by [the frozen manifest](ml/frozen_ppo_manifest.json), which pins the selected PPO checkpoint and updated interaction CSV. DQN uses `artifacts/frozen/public-data-v2/dqn/manifest.json` with the same data. Default training environments use the CSV in `data/processed/`. The other checkpoints support the multi-seed study and are intentionally retained.

Verify archived artifacts:

```powershell
.\.venv\Scripts\python.exe -m ml.src.artifact_checksums
```

`artifacts/ppo/SHA256SUMS.txt` hashes binaries as raw bytes and text after CRLF-to-LF normalization. Research commands and provenance are documented in the [study runbook](docs/scientific-specification/ppo-seed-study-runbook.md). Figure regeneration requires the canonical study outputs, which are not distributed in this repo.

Further documentation: [scientific specification](docs/scientific-specification), [API contract](backend/docs/api-contract.md), [Python service](service/README.md), and [sample workflow](docs/ui/samples-workflow.md).

## Updated data and PPO/DQN comparison

The training CSV contains 30 directed records across 18 antibiotic pairs. The 15 records with unknown direction remain in the evidence registry and are excluded from training. Public measurements and their source URLs and hashes are retained in [data/research](data/research/transition-data-2026-10-23/sources.json). MIC changes inform modeled relationships; transition probabilities remain scenario assumptions, not measured clinical probabilities.

Run from the repository root. The full study trains 20 PPO and 20 DQN replicates with equal interaction budgets and evaluates both against the random susceptible baseline. Existing completed runs can be resumed with `--resume`; new output directories must be empty.

```powershell
# Check the processed tables against the public source extracts.
.\.venv\Scripts\python.exe -B -m experiments.integrate_public_evidence --check

# Train and evaluate; omit this command if the study is already completed.
.\.venv\Scripts\python.exe -B -m ml.src.dqn_benchmark `
  --config experiments\dqn_public_data_v2_config.json `
  --output-dir experiments\runs\public-data-v2

# Audit the completed study and generate the comparison analysis.
.\.venv\Scripts\python.exe -B -m experiments.analyze_dqn_study `
  --study-dir experiments\runs\public-data-v2 `
  --output-dir experiments\results\public-data-v2-review
```

Use module commands (`-m`) so imports resolve from the repository root. Generated run logs and analysis outputs are ignored by Git.

## Frozen updated policies

[artifacts/frozen/public-data-v2](artifacts/frozen/public-data-v2/selection.json) contains **PPO seed 19000** and **DQN seed 15000**, their shared training data, manifests and checksums. These are the lowest-burden final checkpoints for each algorithm on fresh validation draws: 128 profiles × 5 seed blocks per candidate. Exact ties use fewer emergence events, more remaining options, then lower training seed. Separate confirmation draws are recorded without reselecting models. The random baseline has no trained checkpoint; its code and RNG schedule define it.

The original 20-seed comparison did not establish a clear DQN/PPO winner. Selecting deployment checkpoints does not change that finding or establish performance on unseen profiles.

To reproduce selection after a completed study, use a new empty destination:

```powershell
.\.venv\Scripts\python.exe -B -m experiments.freeze_models `
  --study-dir experiments\runs\public-data-v2 `
  --output-dir artifacts\frozen\public-data-v2-reselection

.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums `
  --sums artifacts\frozen\public-data-v2\SHA256SUMS.txt
```

The workbench now serves the selected PPO and DQN alongside the random susceptible baseline. New comparisons run all three from the same starting profile, scenario and environment seed; saved historical two-strategy runs remain readable. Each strategy records its model identity and checkpoint hash. Apply the `AddDqnStrategy` database migration before starting the API.

## Scientific review of the frozen policies

The review enumerates the transition distributions and uses finite-horizon backward induction to compute the exact optimum. It evaluates the frozen policies with their full observations, including the previous action and step. This adds a model-based reference alongside the random baseline; neither the checkpoints nor the training objective change.

| Reference scenario, 127 nonterminal profiles | Expected burden | Gap above exact optimum |
| --- | ---: | ---: |
| Exact planner | 2.8124 | 0 |
| PPO | 2.8512 | 0.0388 |
| DQN | 2.8392 | 0.0268 |
| Random susceptible baseline | 3.7506 | 0.9382 |

These are exact expectations conditional on the current simulator for two fixed checkpoints, not a new comparison across training replicates or clinical outcomes. Agreement can reflect successful optimization of the same objective. It does not validate that objective or its biological assumptions. An optimal-policy reference and sensitivity analysis also appear in [Weaver et al. (2024)](https://doi.org/10.1073/pnas.2303165121); [Patterson et al. (2024)](https://jmlr.org/papers/v25/23-0183.html) discuss fair comparisons and experimental bias in reinforcement learning.

The audit identifies substantive limitations:

- Of 448 feasible state/action pairs, 64 have no applicable transition and use the unchanged-state fallback; 114 force an unchanged state, including modeled neutral outcomes.
- Selected-drug self-resistance is absent. The selected drug remains susceptible, so a nonterminal episode always reaches the full horizon. Mask compliance (100%) and exposure (eight actions) are constraint checks, not evidence of superior treatment performance.
- From `0000000`, both frozen policies repeat fosfomycin: burden is zero, but all eight steps lack an applicable transition. This is an artifact of the modeled relationships, not established biological safety.
- No recovery, bacterial-load, dose or stopping state exists. A constant exposure penalty would add the same cost to every equal-length run and would not correct this limitation. Repetition penalties or new evolution probabilities would define additional assumptions and require a separately specified, evaluated training protocol.

Reproduce the review using an empty output directory:

```powershell
.\.venv\Scripts\python.exe -B -m experiments.review_frozen_policies `
  --output-dir experiments\results\model-review
```

Outputs are `review.json`, all-profile `profiles.csv`, resistance-stratified `strata.csv` and `review.png`. The review includes the existing q=0.25, 0.50 and 0.75 occurrence scenarios with the policies fixed. These scenarios vary supported transitions; they do not resolve unknown evolution or add self-resistance. All 128 profiles remain in the CSV, including the terminal profile. No cases are removed to create a separation between algorithms.
