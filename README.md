# StewardLab / AMR Decision Support

A research workbench for exploring antibiotic resistance in a simulated E. coli environment. Save labeled starting profiles, compare a frozen PPO policy with a random susceptible-action baseline, inspect collateral sensitivity and cross-resistance transitions, and revisit saved results.

Research and simulation only. This platform is not validated for clinical prescribing or patient-specific treatment decisions. The 3D bacteria clearance animation is illustrative; the model tracks resistance, not bacterial load.

## Structure

| Folder | Purpose |
| --- | --- |
| `frontend/` | React workbench, authentication, samples, simulation and results |
| `backend/` | ASP.NET Core API, account ownership and PostgreSQL persistence |
| `service/` | Internal Python inference service and frozen-model validation |
| `simulation/` | Resistance state, actions, transitions and reward |
| `ml/` | PPO training, evaluation, model manifest and reproducibility tools |
| `data/processed/` | Scientific inputs and evidence registry |
| `artifacts/ppo/` | Frozen checkpoints and their provenance |
| `experiments/` | Research configuration |
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

The service validates the checkpoint hash, transition-data hash and frozen manifest before serving runs. Every saved result records model identity, seeds and metric definitions. The active model is selected by [the frozen manifest](ml/frozen_ppo_manifest.json), which also pins the original interaction CSV for the existing checkpoint. Default training environments use the updated CSV in `data/processed/`. The other checkpoints support the multi-seed study and are intentionally retained.

Verify archived artifacts:

```powershell
.\.venv\Scripts\python.exe -m ml.src.artifact_checksums
```

`artifacts/ppo/SHA256SUMS.txt` hashes binaries as raw bytes and text after CRLF-to-LF normalization. Research commands and provenance are documented in the [study runbook](docs/scientific-specification/ppo-seed-study-runbook.md). Figure regeneration requires the canonical study outputs, which are not distributed in this repo.

Further documentation: [scientific specification](docs/scientific-specification), [API contract](backend/docs/api-contract.md), [Python service](service/README.md), and [sample workflow](docs/ui/samples-workflow.md).

An [offline DQN/PPO/baseline benchmark](docs/scientific-specification/dqn-benchmark.md) is available for research. Its pilot and full-study configurations are separate from the model served by the application.

The [transition-data research audit](docs/scientific-specification/transition-data-research-2026-10-23.md) identifies additional public measurements, extraction gaps and the limits of using those measurements as simulation probabilities.

The [public-data integration and retraining instructions](docs/scientific-specification/public-data-integration.md) describe the 45-record training CSV and the fresh 20-seed PPO/DQN/baseline command. Existing models remain paired with their original data until a retrained model is activated.
