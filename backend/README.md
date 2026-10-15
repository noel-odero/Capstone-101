# Backend (ASP.NET Core)

Public API for the capstone. It validates requests, calls the internal Python scientific service for every simulation,
comparison, model lookup and profile check, and returns versioned JSON. It contains no scientific logic.

Contract decisions: [docs/api-contract.md](docs/api-contract.md).

## Layout

| Project | Role |
|---|---|
| `src/Amr.Domain` | Enums and value types; no references |
| `src/Amr.Application` | DTOs, service interfaces, services, mappings, error model; references Domain only, no packages |
| `src/Amr.Infrastructure` | Python HTTP client and health probe; the only project that talks HTTP |
| `src/Amr.Api` | Controllers, problem details, versioning, registration; controllers only call application services |
| `tests/Amr.UnitTests` | Services, mappings, client, architecture rules |
| `tests/Amr.IntegrationTests` | Controllers with fake services, full stack with a stubbed Python network, optional live tests |
| `tests/Shared` | Python fixtures (real captures) and stub HTTP support |

## Prerequisites

.NET SDK 10.0.401 or a later 10.0.4xx patch (`global.json`). The Python service runs from the repository `.venv`.

## Run

Start the Python service from the repository root, then the API from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
dotnet run --project src/Amr.Api
```

`PythonService:BaseUrl` (default `http://127.0.0.1:8000`) and the timeouts are in `src/Amr.Api/appsettings.json`.

## Test

```powershell
dotnet build Amr.sln --no-incremental --nologo
dotnet test Amr.sln --nologo
```

Live tests call a real Python service and are skipped unless `AMR_PYTHON_URL` is set:

```powershell
$env:AMR_PYTHON_URL = 'http://127.0.0.1:8000'
dotnet test tests/Amr.IntegrationTests --nologo
```

Set `CI=true` for locked-mode package restore.

## Endpoint status

| Route | Status |
|---|---|
| `GET /api/v1/health`, `GET /api/v1/health/live` | Working |
| `GET /api/v1/model`, `GET /api/v1/antibiotics` | Working |
| `POST /api/v1/profiles/validate` | Working |
| `POST /api/v1/simulations`, `POST /api/v1/comparisons` | Working; results are returned with `isPersisted: false` |
| `GET /api/v1/simulations/{id}`, `GET /api/v1/comparisons/{id}`, `GET /api/v1/recommendations/{simulationId}`, `GET /api/v1/simulations/recent` | 501 `persistence_not_available` until durable storage exists |

Results are not stored and not cached in memory, so a returned run cannot be fetched again yet.
