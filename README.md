#  Anti Microbial Resistance Decision Support

This work is a research workbench for evaluating antibiotic-selection strategies in a binary E. coli resistance model. Record labeled samples, compare frozen PPO and DQN policies with a random susceptible-action baseline, inspect transitions and revisit saved evidence through Analysis History and Analysis Insights. Model Explorer exposes the 128 possible resistance states and their transition-data coverage.

Results are model-derived research outputs, not clinical treatment recommendations. The original interactive urinary-tract 3D view is an aesthetic illustration; it does not represent measured bacterial clearance or evolution. A scientifically grounded evolution visualization is future work.

## Repository

| Folder | Responsibility |
| --- | --- |
| `frontend/` | React workspace, charts and illustrative 3D view |
| `backend/` | ASP.NET Core API, authentication and PostgreSQL persistence |
| `service/` | Internal FastAPI service loading the frozen policies locally |
| `simulation/` | Resistance states, action masks, transitions and reward |
| `ml/` | PPO/DQN training, inference and evaluation |
| `experiments/` | Data integration, benchmark configuration, audits and model selection |
| `data/` | Processed scientific inputs, source extracts and derivation inputs |
| `artifacts/frozen/` | Active policy checkpoints, manifests and checksums |

The browser calls the .NET API; the API calls Python for scientific computation and saves completed evaluations in PostgreSQL. Models run locally inside Python and do not require external model hosting.

## First setup

Use Python 3.11, Node 22.12 or later, the .NET 10 SDK specified in `backend/global.json`, and Docker Desktop. Commands below are PowerShell, starting from the repository root.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-lock.txt -r service/requirements-dev.txt
dotnet restore backend\Amr.sln --locked-mode
npm --prefix frontend ci
```

For an inference-only Python environment, install `service/requirements.txt` instead. Use `.venv` Python on Windows; plain `python` may resolve to the Microsoft Store alias.

The development PostgreSQL container is `amr-test-pg` (`postgres:17-alpine`, host port 55432). If it does not exist, create it once with a local password:

```powershell
$pgPassword = Read-Host 'Local PostgreSQL password'
docker run -d --name amr-test-pg -e "POSTGRES_PASSWORD=$pgPassword" -p 127.0.0.1:55432:5432 postgres:17-alpine
$admin = "Host=127.0.0.1;Port=55432;Username=postgres;Password=$pgPassword;Database=postgres"
[Environment]::SetEnvironmentVariable('AMR_TEST_POSTGRES', $admin, 'User')
Remove-Variable pgPassword
```

If the container already exists, retain its existing `AMR_TEST_POSTGRES` admin connection string. Credentials and local environments are excluded from Git.

## Run locally

Start the four components in order, each service in its own terminal.

1. Start PostgreSQL with Docker Desktop running:

   ```powershell
   docker start amr-test-pg
   ```

2. On first setup and after pulling migrations, apply the schema explicitly:

   ```powershell
   cd backend
   $admin = [Environment]::GetEnvironmentVariable('AMR_TEST_POSTGRES', 'User')
   $env:ConnectionStrings__Amr = [regex]::Replace($admin, 'Database=[^;]*', 'Database=amr_frontend_dev')
   dotnet tool restore
   dotnet tool run dotnet-ef database update --project src/Amr.Infrastructure --startup-project src/Amr.Api
   ```

3. From the repository root, start Python:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```

4. From the repository root, start the API:

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
   npm run dev
   ```

Open http://localhost:5173 and create an account. `npm run dev` retains the larger HTTP header limit needed when localhost cookies accumulate. Stop each service with Ctrl+C; PostgreSQL can remain running.

```powershell
Invoke-RestMethod http://127.0.0.1:5080/api/v1/health
Invoke-RestMethod http://127.0.0.1:5173/api/v1/auth/session
```

Readiness requires Python, verified models and a migrated database. `database_migrations_pending` means step 2 is needed. The API refuses to start without `ConnectionStrings__Amr`.

## Checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums
npm --prefix frontend run build
npm --prefix frontend run lint
npm --prefix frontend test
```

[API and architecture](docs/api.md) covers .NET, PostgreSQL and live-service tests. [Scientific model](docs/scientific-model.md) defines the computational assumptions and metrics. [Research and retraining](docs/research.md) describes data provenance, the three-strategy benchmark and frozen-model selection.
