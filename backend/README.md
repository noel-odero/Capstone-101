# Backend (ASP.NET Core)

Public API for the capstone. It validates requests, calls the internal Python scientific service for every simulation,
comparison, model lookup and profile check, stores completed runs in PostgreSQL, and returns versioned JSON. It contains no
scientific logic.

Contract decisions (ids, `201 Created`, `isPersisted`, metric definitions, unsupported transitions, migrations, health,
live tests): [docs/api-contract.md](docs/api-contract.md). Limits to plan around before building a frontend (CORS,
authentication, retries, OpenAPI, errors): [Known limitations for frontend integration](docs/api-contract.md#known-limitations-for-frontend-integration).

## Layout

| Project | Role |
|---|---|
| `src/Amr.Domain` | Enums and value types; no references |
| `src/Amr.Application` | DTOs, service and repository interfaces, services, mappings, metric catalogue, error model; references Domain only, no packages |
| `src/Amr.Infrastructure` | Python HTTP client, EF Core / PostgreSQL persistence and migrations, health probes; the only project that talks HTTP or to the database |
| `src/Amr.Api` | Controllers, problem details, versioning, registration; controllers only call application services |
| `tests/Amr.UnitTests` | Services, mappings, persistence mapping, failure classification, architecture rules |
| `tests/Amr.IntegrationTests` | Controllers with fake services, full stack with a stubbed Python network and real PostgreSQL, schema and migration tests, live tests |
| `tests/Shared` | Python fixtures (real captures) and stub HTTP support |
| `scripts/run-live-tests.ps1` | Starts the real Python service and runs the live tests with skipping disabled |

## Prerequisites

- .NET SDK 10.0.401 or a later 10.0.4xx patch (`global.json`).
- The Python service, run from the repository `.venv`.
- A PostgreSQL server for the API and for the database tests (a disposable container is enough for development).

## Run

1. Start a PostgreSQL server and set the connection string in the environment. It is never stored in a file:

   ```powershell
   $env:ConnectionStrings__Amr = 'Host=localhost;Port=5432;Database=amr;Username=amr;Password=<local-dev-password>'
   ```

2. Apply the migrations explicitly. The API never changes the schema on startup:

   ```powershell
   cd backend
   dotnet tool restore
   dotnet tool run dotnet-ef database update --project src/Amr.Infrastructure --startup-project src/Amr.Api
   ```

3. Start the Python service from the repository root, then the API from `backend/`:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
   dotnet run --project src/Amr.Api
   ```

`PythonService:BaseUrl` (default `http://127.0.0.1:8000`) and the timeouts are in `src/Amr.Api/appsettings.json`. The API
does not start without `ConnectionStrings__Amr`. `GET /api/v1/health` reports `database_migrations_pending` if step 2 was
skipped.

To review the schema change as SQL instead of applying it directly, generate an idempotent script:

```powershell
dotnet tool run dotnet-ef migrations script --idempotent --project src/Amr.Infrastructure --startup-project src/Amr.Api -o amr-migrations.sql
```

## Test

Start a disposable PostgreSQL server (never a shared database) and point the tests at it with an admin connection string:

```powershell
docker run -d --name amr-test-pg -e POSTGRES_PASSWORD=<throwaway> -p 127.0.0.1:55432:5432 postgres:17-alpine
$env:AMR_TEST_POSTGRES = 'Host=127.0.0.1;Port=55432;Username=postgres;Password=<throwaway>;Database=postgres'
$env:AMR_REQUIRE_POSTGRES = 'true'   # fail, rather than skip, if the server is missing
dotnet build Amr.sln --no-incremental --nologo
dotnet test Amr.sln --nologo
```

Every database test class creates and drops its own `amr_it_<guid>` database. Without `AMR_TEST_POSTGRES` the PostgreSQL
tests are skipped and reported as skipped; without `AMR_PYTHON_URL` the live tests are skipped. Set `CI=true` for
locked-mode package restore.

### Live tests (real Python service, real PostgreSQL, no skipping)

```powershell
.\scripts\run-live-tests.ps1
```

The script starts the Python service, waits for a ready model, sets `AMR_PYTHON_URL`, runs the live tests with
`AMR_REQUIRE_LIVE=true` and `AMR_REQUIRE_POSTGRES=true`, and always stops the service. It needs `AMR_TEST_POSTGRES` in the
environment and the repository `.venv` (or `-Python <path>`). It selects exactly the live test classes, so it does not repeat
the rest of the suite. It also fails when the filter selects no tests in either live class, because `dotnet test` itself
exits 0 for an empty selection.

### CI

`.github/workflows/ci.yml` runs on pull requests and on pushes to `main` and `backend`: the `dotnet` job (locked restore, build
with warnings as errors, all non-live tests against a PostgreSQL service, `AMR_REQUIRE_POSTGRES=true`), the `python` job (full
`pytest`) and the `live` job (this script, no skipping). The three jobs completed successfully on GitHub for the push to
`backend` at `e11e0e5` (run #2) and for pull request #1 (run #3), according to the Actions run pages. The job logs were not
inspected, so the remote test counts and skip counts are not independently confirmed.

## Endpoint status

| Route | Behavior |
|---|---|
| `GET /api/v1/health`, `GET /api/v1/health/live` | Readiness covers Python, the model and the migrated database; liveness does not |
| `GET /api/v1/model`, `GET /api/v1/antibiotics` | Served by Python |
| `POST /api/v1/profiles/validate` | 200, including terminal all-resistant profiles |
| `POST /api/v1/simulations`, `POST /api/v1/comparisons` | 201 Created with `Location`; the run is stored and `isPersisted` is true only after the commit |
| `GET /api/v1/simulations/{id}`, `GET /api/v1/comparisons/{id}` | The stored run; 404 for an unknown id or the other kind |
| `GET /api/v1/recommendations/{simulationId}` | PPO steps of a stored simulation; 404 `recommendation_not_found` otherwise |
| `GET /api/v1/simulations/recent` | Simulations and comparisons, newest first, paged |
| `GET /api/v1/samples`, `GET /api/v1/samples/{id}` | The authenticated account's saved profiles, labels, dates and linked comparisons |
| `POST /api/v1/samples` | Save a labeled starting profile without running a simulation; 201 Created |

`POST /api/v1/comparisons` also accepts an optional `sampleId`. The sample service checks ownership and the original profile before execution; the run and sample link are then committed together. See [the sample workflow](../docs/ui/samples-workflow.md).

If Python succeeds but the save fails, the response is 503 `database_unavailable` or 500 `persistence_failed`, no id is
issued, and the failure is logged with the run id and correlation id. Python is never called twice for one request.
