# Workspace UI rework

The visual reference is `inspos/Capstone-uti.png`. The implementation retains the repository's real simulation contracts rather than hardcoding the example patient, drug sequence or chart values in that image.

## Architecture

- `frontend/`: React 19 + TypeScript, Vite, CSS Modules, React Router, TanStack Query, Recharts.
- `backend/`: .NET 10 public API, authentication, PostgreSQL persistence.
- `service/`: internal FastAPI scientific service; loads the frozen PPO checkpoint and simulator.
- `simulation/`, `ml/`, `data/`, `artifacts/`: scientific model, transitions and provenance.
- Workspace routes live under `/app`; the browser communicates only with `/api/v1` through the Vite proxy.

## Page plan and implementation

| Screen | Reference structure | Implementation |
| --- | --- | --- |
| Shared shell | Navy navigation, blue selection, account footer, pale surfaces | Shared layout tokens and sidebar; responsive mobile drawer; existing theme and authentication retained |
| Home | Greeting, location, four cards, blue anatomy hero and action | Latest real PPO metrics; decorative transparent anatomy asset; working new-simulation link; empty/loading/error states retained |
| Simulation | Profile and horizon controls, dark anatomy panel, playback, chart and metrics | All 128 profile choices (terminal profile disabled), real comparison submission, fixed model horizon, step controls and playback, returned trajectories, three primary metrics and expandable full trace |
| Recommendations | Numbered sequence beside explanation, blue information card, full-width action | Returned PPO sequence with selectable steps; scrolling retains all eight steps; baseline and full metrics remain expandable; new-run link carries the initial profile |
| Profile | Summary, tabs, seven resistance badges, trend and activity | Simulation profile identity, overview/history navigation, real initial resistance states, per-step resistant count chart and completed-run activity; detailed evolution and provenance retained |

The app has no patient demographics or clinical efficacy model. The corresponding reference positions therefore show simulation profile information and susceptible-action rate. Anatomy is explicitly illustrative and does not encode measured organ-level resistance.

## Local preview

Use the project's standard development database, `amr_frontend_dev`, on the `amr-test-pg` Docker container (PostgreSQL 17, port 55432). Read the admin connection string from the user environment variable `AMR_TEST_POSTGRES`; do not put passwords in commands or files. The initial UI verification used a separate disposable database, `amr_ui_preview_20261020`.

Current service addresses:

- Frontend: http://127.0.0.1:5173
- Public API: http://127.0.0.1:5080
- Internal Python service: http://127.0.0.1:8000

Sign in with your development account, or create one at `/auth/register`, then run a simulation. Captured API responses are used only in automated browser tests, never in the running application.

Start PostgreSQL, Python, the API and the frontend in that order, each in its own PowerShell terminal. Commands start at the repository root.

```powershell
docker start amr-test-pg

.\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1

$admin = [Environment]::GetEnvironmentVariable('AMR_TEST_POSTGRES','User')
$env:ConnectionStrings__Amr = [regex]::Replace($admin, 'Database=[^;]*', 'Database=amr_frontend_dev')
$env:ASPNETCORE_ENVIRONMENT = 'Development'
$env:ASPNETCORE_URLS = 'http://127.0.0.1:5080'
dotnet run --project backend\src\Amr.Api --no-launch-profile

cd frontend
npm run dev
```

Docker Desktop must be running. After pulling new migrations, run the database update from `backend/` with the same `ConnectionStrings__Amr` setting:

```powershell
dotnet tool run dotnet-ef database update --project src/Amr.Infrastructure --startup-project src/Amr.Api
```

Use the `.venv` interpreter; plain `python` resolves to a Microsoft Store alias on this machine. Use `npm run dev` to retain the larger HTTP header limit needed for local cookies. Install frontend dependencies only when dependency inputs change. Vite's default API proxy targets port 5080; no proxy override is needed.

Verify `http://127.0.0.1:5080/api/v1/health` returns healthy with `ready: true` and `http://127.0.0.1:5173/api/v1/auth/session` returns a session through the proxy. Open http://localhost:5173. Stop services with Ctrl+C; PostgreSQL can keep running. Reload the page after 3D camera changes.

On this machine, Python and .NET require access outside the restricted sandbox to the installed interpreter and Windows authentication encryption keys.

## Verification

- `npm run build`: TypeScript and production Vite build.
- `npm test -- --maxWorkers=2`: component/domain/authentication suite.
- `npm run test:e2e -- --workers=2`: four screens in light/dark, theme persistence, mobile navigation, mobile layout, settings submission and timeline playback.
- `node scripts/verify-live-ui.mjs`: opt-in check against the already running local preview stack. Creates a disposable account and real persisted comparison; checks timeline interactions, all four desktop/mobile pages and browser errors. Run only against a local preview database.

Live screenshots are saved in ignored `frontend/playwright-report/live-preview/`. Fixture-driven screenshots are in ignored `frontend/test-results/`. No login credentials or browser session state are saved by the live check.

## Generated visual asset

### Interactive simulation update

The Simulation page now uses actual Three.js geometry in `frontend/src/features/scene/BacteriaClearanceScene.tsx` instead of the anatomy PNG. Translucent kidneys, ureters and a bladder contain 48 instanced rod-shaped bacteria. Treatment-step progress drives an illustrative dissolve animation with clearing particles. Playback, direct step selection, camera rotation and zoom are supported; reduced-motion users get immediate step changes. A readable fallback handles missing WebGL and context loss.

The scene starts at step 0. Its caption identifies the PPO-selected antibiotic and returned resistance profile at each step. The clearance animation is explicitly educational: the scientific API has no bacterial-load, CFU or clearance endpoint, so visual particle counts are not reported as clinical or modeled outcomes. An early-ended PPO episode stops the scene at its last actual step.

The reference-matching anatomy is implemented in `UrinaryTractModel.tsx`: smooth blue-to-burgundy renal capsules, translucent internal medullary layers, branching vessels and renal pelvis, warm two-layer ureters, and a translucent green bladder. A local studio-light environment and rim shaders provide reflections without downloading external HDR files. Bacteria are deliberately small so the anatomy remains legible. The model consists of actual three-dimensional meshes and supports orbiting.

Browser checks record the real WebGL scene at steps 0, 4 and 8, verify timeline submission/playback, and exercise context-loss fallback. The Home page continues to use the generated PNG below.

Built-in image generation was used for `frontend/public/images/urinary-tract.png`, a transparent 1024 x 1536 PNG. It is bundled locally, without a runtime image service dependency.

Final generation prompt:

> Use case: scientific-educational. Create one premium 3D medical illustration asset for a research dashboard, isolated on genuinely transparent background. Front view of urinary tract only: two anatomically recognizable semi-transparent glossy kidneys, two slender ureters, bladder and short urethra. Kidneys violet lavender blue translucent glass with visible subtle internal vascular structures, orange yellow renal pelvis. Left kidney cool lavender, right kidney reddish purple lower half. Ureters thin luminous yellow green and orange. Bladder translucent green with orange red center. Delicate realistic volumetric lighting, sophisticated medical visualization, polished soft highlights. Symmetrical upright composition, organ system centered with modest empty margin, full system fits image. No text, no labels, no legend, no UI, no torso, no skeleton, no floor, no framing. This is decorative illustrative anatomy, not data visualization.
