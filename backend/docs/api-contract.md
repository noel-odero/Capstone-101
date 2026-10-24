# Public API contract notes

Decisions that are easy to get wrong. Code comments on the DTOs and interfaces carry the same statements.

The product calls these operations **analyses** and **strategy evaluations**. Existing route names
(`/simulations`, `/comparisons`, `/recommendations`), resource kinds and DTO fields remain stable for
compatibility. Analyses still use a computational simulation; the terminology does not imply clinical validation.

## Endpoints

| Route | Success | Behavior |
|---|---|---|
| `GET /api/v1/health` | 200 / 503 | 200 only when `pythonService`, `model` and `database` are all healthy; otherwise 503 with the same report body |
| `GET /api/v1/health/live` | 200 | The process answers; touches no dependency |
| `GET /api/v1/model` | 200 | Frozen-model metadata from Python |
| `GET /api/v1/antibiotics` | 200 | Seven-drug catalogue in action order |
| `POST /api/v1/profiles/validate` | 200 | Any valid profile, including terminal all-resistant |
| `POST /api/v1/simulations` | 201 | Runs `ppo`, `dqn` or `random_susceptible_baseline` in Python, stores the result, returns it with `Location` |
| `POST /api/v1/comparisons` | 201 | Runs the paired comparison in Python, verifies the contract, stores all strategy results, returns it with `Location` |
| `GET /api/v1/simulations/{id}` | 200 / 404 | The stored simulation, in the same representation as the POST response |
| `GET /api/v1/comparisons/{id}` | 200 / 404 | The stored comparison, in the same representation as the POST response |
| `GET /api/v1/recommendations/{simulationId}` | 200 / 404 | Learned-policy steps of a stored simulation |
| `GET /api/v1/simulations/recent` | 200 | Stored simulations and comparisons, newest first |
| `GET /api/v1/analyses` | 200 | Owner-scoped, paginated saved history with profile, resistance-count, strategy, UTC date and sort filters |
| `POST /api/v1/analyses/compare` | 200 / 404 / 422 | Reads 2–50 distinct, non-empty saved analysis UUIDs; returns recorded strategy results, compatibility issues and nullable within-analysis burden differences |
| `GET /api/v1/analysis-collections` | 200 | Lists the signed-in account's saved research collections |
| `POST /api/v1/analysis-collections` | 201 / 404 / 422 | Saves a name, optional research question and 2–50 distinct owned analysis UUIDs |

**Analysis Insights.** `GET /analyses` accepts `page`, `pageSize`, `profile` (seven binary digits),
`initialResistantCount` (0–7), `strategy` (`ppo`, `dqn`, `baseline`, `missing_dqn`), inclusive
`from`/`to` timestamps, and `sort` (`newest`, `oldest`, `ppo`, `dqn`, `baseline`, `disagreement`).
Burden sorts are ascending, missing policies last; disagreement sorts absolute PPO–DQN burden
differences descending, paired records first. Ties use date then id.

`POST /analyses/compare` takes `{ "analysisIds": ["<uuid>", "<uuid>"] }` and preserves selection order.
It uses stored data only and requires the same authentication and antiforgery protection as other POSTs.
Missing and foreign-owned IDs produce the same `404 analysis_not_found` for the entire request;
neither is silently excluded. Missing strategies and their differences remain absent/null, never zero.
Compatibility checks cover checkpoint and transition-data identities, scenario, horizon, action order/mask,
reward and metric definitions, shared-condition verification, service versions, profiles and seeds.
Repeated recorded random draws are flagged. Unknown identities are not guessed.
The response is descriptive: no pooled mean, significance test or automatic algorithm winner is computed.
The comparison read layer does not require new scientific records. Research collections use the
`AddAnalysisCollections` migration: owner, name (80 characters), optional question (500 characters),
creation time and ordered analysis UUIDs. Foreign and missing IDs return the same 404; collections
never expose another account's evidence. Saving a collection does not run a policy.
The archive continues to use `/simulations/recent`. Existing `/app/history/analyze` links redirect
to the standalone `/app/insights` page. Exports are generated in the browser from validated saved results.

Any database-backed route answers 503 `database_unavailable` while the database cannot be reached. A missing run is never
reported as an empty result or a 404 in that case.

## Run creation: ids, status code and `isPersisted`

**The id.** `id` is the Python run id (a UUID the scientific service issues per execution). It is also the stored
resource id: `GET /api/v1/simulations/{id}` or `GET /api/v1/comparisons/{id}` returns exactly the run that was created.
A simulation id is not a comparison id; asking for the wrong kind is `404 not_found`.

**Why 201 Created.** Creation now produces a durable, individually addressable resource, so the response is
`201 Created` with `Location: /api/v1/simulations/{id}` (or `/comparisons/{id}`) and the run as the body. A `200 OK` would
not say that a new resource now exists, and would leave the client without its address.

**When `isPersisted` is true.** Only after the database transaction committed. The service builds the result with
`isPersisted: false`, saves it, and sets `true` on the returned copy after the save succeeded. A response is never sent
with `isPersisted: true` before the commit, and a failed save never produces a success body at all. A retrieved run always
has `isPersisted: true`.

**When the save fails.** Python may have executed a run that has no public record:

| Cause | Status | Code |
|---|---|---|
| Database unreachable, authentication or resource failure, timeout | 503 | `database_unavailable` |
| The write was rejected (constraint, missing schema, duplicate run id) | 500 | `persistence_failed` |

The message says the analysis ran but no record exists, and no id is issued to the client. The failure is logged at
error level with the Python run id and the request's `X-Correlation-ID`, so the orphaned upstream execution can be found.
Python is called once per request: there are no automatic retries of simulation or comparison POSTs, and a failed save does
not re-run Python. If the client cancels during the save, the transaction is abandoned and normally rolls back, but a
cancellation that races the commit can leave the run stored without the client receiving its id.

**Failed and partial runs.** Only completed runs are stored. Python either returns a full result or an error, so there is no
partial result. A failed or contract-violating run (`comparison_contract_violation`, an invalid or mismatched Python
response) is reported as an error and never persisted. The database enforces this: `experiment_runs.status` has a check
constraint allowing only `completed`, and a comparison row must carry its contract, pairing semantics and caveat.

## Persistence model

| Table | Purpose |
|---|---|
| `model_versions` | The exact model and simulator configuration: model id, algorithm, checkpoint SHA-256, interaction-data SHA-256, scenario, horizon, action-mask rule, reward specification, antibiotic order. Unique on a SHA-256 fingerprint of those fields (the service version is excluded). |
| `experiment_runs` | One simulation or comparison. Primary key is the public id. References one model version, and records inputs (initial profile, seeds and their sources), service version, Python's creation time, the commit time, metric definitions, and for comparisons the pairing semantics, caveat and verified contract. |
| `strategy_runs` | One strategy's trajectory and its 12 metrics. Unique on (experiment run, strategy): a simulation has one, a comparison has `ppo`, `dqn` and `random_susceptible_baseline` (older runs have two). Also holds the state snapshots and each learned policy?s model id, algorithm and checkpoint hash. |
| `step_traces` | One step. Primary key (strategy run, step index), so order is stable and duplicates are impossible. |

`ModelVersion` relates one-to-many to experiment runs, which relate one-to-many to strategy runs, which relate
one-to-many to step traces. Foreign keys cascade from run to strategy runs to steps; a model version cannot be deleted
while a run references it. A save is one transaction: the model-version upsert (`ON CONFLICT DO NOTHING`, race-free), the
run, its strategy runs and every step commit together or not at all.

Values are copied, never recomputed, so a retrieved run equals the run Python produced. Structured sub-documents
(state snapshots, feasible actions, candidate transitions, metric definitions, the reward specification and the comparison
contract) are stored as `jsonb`, which does not preserve object key order; JSON consumers must not depend on it.
Paths, devices and Python class names are never stored or returned.

## Metrics: `metricDefinitions`

Every simulation and comparison response (POST and GET) carries `metricDefinitions`, keyed by the metric's property name
in `result.metrics` (`ppo.metrics` / `dqn.metrics` / `baseline.metrics` for comparisons). Each entry has:

- `definition`: the Python service's text, verbatim as returned with that run and stored with it;
- `kind`: `cumulative` (a running total of per-step quantities), `count` (a tally, or the count in one state),
  `difference` (a signed difference of two counts) or `rate` (a ratio of two counts within one episode);
- `unit` and `aggregation`: the scale and how the value is computed over one episode.

All values describe one simulated episode. No exposed metric is an average across episodes or a percentage; rates are
proportions in [0, 1] and are `null` when the episode has no steps. None is a clinical outcome. The kind, unit and
aggregation were verified against `service/rollout.py`, `ml/src/metrics.py` and `simulation/reward.py`
(`Amr.Application/Metrics/MetricCatalogue.cs` is the single catalogue). A Python response whose metric names differ from
the catalogue is rejected as `python_service_invalid_response` instead of being guessed at.

| Metric | Kind | Unit | Aggregation | Python definition (verbatim) |
|---|---|---|---|---|
| `cumulativeResistanceBurden` | cumulative | resistant-antibiotic burden normalized by 7 antibiotics; simulated, lower is less burden | Negated cumulative reward: the negated sum of step rewards plus the negated terminal adjustment, which is -horizon when the episode starts in the all-resistant terminal state and 0 otherwise (so a zero-step episode that starts all-resistant has burden equal to the horizon) | Negative of the simulator's cumulative reward (ml.src.matched_policy_evaluation._episode_burden): sum over steps of resistant_count_after / 7, with an all-resistant state charged for the remaining horizon. Lower means less simulated resistance burden; it is not a clinical outcome. |
| `cumulativeReward` | cumulative | simulator reward units | Sum of step rewards plus the terminal adjustment, which is -horizon when the episode starts in the all-resistant terminal state and 0 otherwise | Sum of simulator step rewards plus any terminal adjustment (ml.src.metrics). |
| `treatmentSteps` | count | steps | Number of actions taken before the episode ended | Number of actions taken before the episode ended. |
| `initialResistantCount` | count | antibiotics, from 0 to 7 | Value at the start of the episode; not accumulated | Resistant antibiotics in the initial profile. |
| `finalResistantCount` | count | antibiotics, from 0 to 7 | Value at the end of the episode; not accumulated | Resistant antibiotics in the final profile. |
| `finalSusceptibleCount` | count | antibiotics, from 0 to 7 | Value at the end of the episode; not accumulated | Susceptible antibiotics in the final profile (ml.src.metrics future_effective_antibiotics). |
| `changeInSusceptibleCount` | difference | antibiotics, signed | Final susceptible count minus initial susceptible count | final_susceptible_count minus the initial susceptible count. |
| `resistanceEmergenceEvents` | count | steps | Number of steps after which the resistant count increased | Steps after which the resistant count increased (ml.src.metrics). |
| `resistanceEmergenceRate` | rate | proportion of steps in [0, 1]; not a percentage | resistance_emergence_events divided by treatment_steps; null when there are no steps | resistance_emergence_events / treatment_steps; null when there are no steps. |
| `susceptibleActionRate` | rate | proportion of steps in [0, 1]; not a percentage | Steps whose selected drug was susceptible in the simulator divided by treatment_steps; null when there are no steps | Fraction of steps whose selected drug was susceptible in the simulator (ml.src.metrics treatment_effectiveness_rate). The susceptible-only mask makes this 1.0 for all strategies, and it is not clinical efficacy; null when there are no steps. |
| `unsupportedStepCount` | count | steps | Number of steps with transition_status unsupported_no_candidate | Steps with transition_status unsupported_no_candidate: the simulator had no candidate transition and left the profile unchanged. |
| `cumulativeAntibioticExposure` | cumulative | antibiotic administrations | One per step, so it equals treatment_steps | Number of antibiotic administrations (one per step). |

**Terminal adjustment.** The Python definition strings for `cumulativeReward` and `cumulativeResistanceBurden` do not say
what the "terminal adjustment" is, and the burden string describes only the per-step sum. The code defines it:
`ml/src/evaluation_runner.py` sets `terminal_reward_adjustment` to `-float(horizon)` when the episode starts in the
all-resistant terminal state and to `0.0` otherwise, `EpisodeResult.cumulative_reward` is the sum of step rewards plus that
adjustment, and the burden is its negative (`ml/src/matched_policy_evaluation.py`, `_episode_burden`). An episode that starts
all-resistant executes zero steps yet reports burden `8.0` and reward `-8.0` for an eight-step horizon (see the
`simulate_200_terminal` fixture). The aggregation column states this; the Python text is still passed through verbatim.
The API assigns no further scientific meaning to the adjustment, and the rationale for choosing `-horizon` is not stated in
the code, so it is left to the scientific owners. The `susceptibleActionRate` source field is internally named
`treatment_effectiveness_rate`; the public name deliberately avoids implying efficacy.

## Susceptibility versus supported transition data

Two different facts are kept apart on every step and are stored in separate columns:

- `selectedDrugSusceptible`: in the resistance profile the selected antibiotic was susceptible (the simulator's internal
  `effective` flag). It is not clinical efficacy.
- `transitionStatus` / `hasCandidateTransition`: whether the simulator has transition data for that action in that state.
  `transitionStatus` is the sampled outcome, or `unsupported_no_candidate` when there is no candidate transition.

A susceptible drug can have no transition data. Such a step has `selectedDrugSusceptible: true`,
`transitionStatus: "unsupported_no_candidate"`, `hasCandidateTransition: false`, empty `candidateTransitions`, a null
`selectedOutcome`, and the profile after equals the profile before. Nothing is invented for it, and it is counted in
`unsupportedStepCount`. Python provides no separate reason code beyond `transitionStatus`, so none is stored. The same
values come back from POST, GET and the recommendation endpoint.

## Validation boundary

DTO validation attributes at the API boundary are the contract (shape, lengths, ranges, strategy enum, unknown members).
Application services trust a bound DTO and do not re-validate it. Python remains the backstop: its own rejection is
mapped to 422 and its message is not echoed. Services additionally check that a Python response answers the request (same
profile, seeds and strategy) and reject mismatches as `python_service_invalid_response`, or as
`comparison_contract_violation` for comparisons. Nothing is saved before those checks pass.

## Strategy identifiers

| Public (`/api/v1`) | Python wire | Display label |
|---|---|---|
| `ppo` | `ppo` | PPO |
| `dqn` | `dqn` | DQN |
| `random_susceptible_baseline` | `greedy` | Random Susceptible Baseline |

`Amr.Application/Mappings/StrategyMapping.cs` is the only translation point. The baseline is Python's existing
`GreedyPolicy`, which samples uniformly among susceptible actions; its behavior is unchanged. An unknown Python id is an
upstream error (`python_service_invalid_response`).

## Recent runs: `GET /api/v1/simulations/recent`

Returns simulations and comparisons together. Each row has `kind` (`simulation` or `comparison`) and one
(`simulation`) or two (`comparison`) strategy summaries. Order is `createdAtUtc` descending, then `id` descending, so
pages are stable. `page` starts at 1; `pageSize` defaults to 20 and is capped at 50 (`PaginationLimits`). Out-of-range
values are rejected with 422, not clamped.

## Recommendations: `GET /api/v1/recommendations/{simulationId}`

Returns the PPO- or DQN-selected steps of a stored simulation. When the id is unknown, or the run has
no learned-policy steps (a baseline simulation, a comparison id, a failed run), the response is the same explicit
`404 recommendation_not_found`; the two cases are deliberately indistinguishable. A recommendation is a policy choice
among simulator-feasible (susceptible) drugs; it is not clinical advice.

## What the public contract takes from Python

Evidence is in `service/schemas.py`, `simulation/reward.py`, `ml/src/ppo_training.py` and the fixtures under
`backend/tests/Shared/Fixtures/python`.

| Field | Python source | Decision |
|---|---|---|
| `rewardSpecification` | `RewardSpecification.to_dict()`; schema declares `dict[str, Any]`; today `objective`, `normalization`, `terminal_convention` (pinned by `simulation/tests/test_reward.py`) | Passed through verbatim as a map. No key is dropped or interpreted, and a future key appears without a code change. Keys keep their Python spelling. |
| `actionMaskConfiguration` (comparisons) | `PPOConfig.__post_init__` rejects anything but `{"enabled": true, "rule": "susceptible_actions_only"}` | Typed (`enabled`, `rule`), because the shape is enforced. |
| model `observation`, `actionSpace`, `actionMasking`, `inference` | Validated by `load_manifest` against the frozen manifest | Typed. Manifest file paths, the inference device, the Python `implementation` class name and `evaluation_utility` are not exposed. |
| Metric definitions | `metric_definitions` in every Python run response (`service/rollout.py`) | Exposed as `metricDefinitions` with kind, unit and aggregation; see Metrics above. |

## Validation and errors

All problem responses are RFC 9457 (`application/problem+json`) with `code` and `correlationId`
(`X-Correlation-ID` header, generated when absent or malformed).

- **422 `validation_failed`**: every unusable input: wrong profile length or values, numbers sent as strings, unknown JSON
  members (`horizon`, `scenarioId`), out-of-range seeds or paging, unparseable query values, empty or malformed bodies.
  The `errors` object is keyed by camelCase path. Parse errors get a generic message; framework text is never echoed.
  400 is not used.
- Other 4xx are framework conditions with their own code: 404 `not_found` (unknown route or API version), 405
  `method_not_allowed`, 415 `unsupported_media_type`.
- Valid terminal all-resistant profiles are normal results, never errors.

| Category | Status | Codes |
|---|---|---|
| Invalid request | 422 | `validation_failed` |
| Not found | 404 | `not_found`, `recommendation_not_found` |
| Dependency unavailable | 503 | `model_unavailable`, `python_service_unavailable`, `python_service_timeout`, `database_unavailable` |
| Upstream failure | 502 | `python_service_invalid_response` |
| Internal | 500 | `internal_error`, `comparison_contract_violation`, `persistence_failed` |

Python errors map in `Infrastructure/Python/PythonServiceErrorMapper.cs`: `invalid_context` and
`request_validation_error` to 422; `model_not_loaded`, `checkpoint_integrity_failure`, `model_contract_mismatch` and
`model_or_data_unavailable` to 503 `model_unavailable`; `comparison_contract_violation` is preserved (500); any other
Python 5xx is 500 `internal_error`; a gateway 502/503/504 without an envelope is 503 `python_service_unavailable`; any
other unrecognized response is 502. Python messages, request ids and details are logged, not returned.

## Python client behavior

One attempt per call; no retries anywhere, so a simulation or comparison is never run twice by the client. Caller
cancellation reaches the HTTP request and propagates as `OperationCanceledException`. `PythonService:RequestTimeoutSeconds`
bounds a call (`python_service_timeout`); `HealthTimeoutSeconds` bounds the health probe; `ConnectTimeoutSeconds`
bounds connecting. Response bodies are parsed strictly: a missing or null required member is an invalid response, unknown
members are ignored. The Python fixtures are regenerated with
`.\.venv\Scripts\python.exe -B backend/tests/Shared/Fixtures/generate_python_fixtures.py` from the repository root.
Fixtures are real captures and can go stale when the Python schema changes; regenerate them after any `service/` change.

Readiness (`IDependencyHealthProbe`) reports `pythonService` and `model` separately: a reachable service with a model
that failed verification is `pythonService` healthy, `model` unhealthy (`model_unavailable`). The `database` component is
described under Health below.

A Python connect timeout can surface as `python_service_timeout` rather than `python_service_unavailable`; both are 503 and
clients should treat them alike.

## Build reproducibility

- `global.json` pins SDK 10.0.401 with `rollForward: latestPatch` (patch updates within the 10.0.4xx band only).
- `nuget.config` clears machine-level sources and uses nuget.org only.
- `Directory.Packages.props` holds every package version; `MicrosoftPackagesVersion` keeps the Microsoft packages aligned.
- Each project has a committed `packages.lock.json`; set `CI=true` (or pass `--locked-mode`) to fail on drift.
- Nullable reference types and warnings-as-errors apply to every project; analyzers run at `latest-recommended`.
  Test projects additionally disable CA1707 (underscored test names) and CA1861 (inline expected arrays).

## Database configuration and migrations

PostgreSQL is configured only through the environment. The connection string is a secret and is never committed;
`appsettings*.json` contain no connection string, and a unit test enforces that.

```powershell
$env:ConnectionStrings__Amr = 'Host=localhost;Port=5432;Database=amr;Username=amr;Password=<local-dev-password>'
```

The API refuses to start without `ConnectionStrings__Amr`. `Database:CommandTimeoutSeconds` (30) and
`Database:HealthTimeoutSeconds` (3) are in `appsettings.json`.

**Migrations are explicit.** The API never creates or changes the schema on startup. An operator applies them with the
pinned local tool (`backend/dotnet-tools.json`, `dotnet-ef` 10.0.13):

```powershell
cd backend
dotnet tool restore
dotnet tool run dotnet-ef database update --project src/Amr.Infrastructure --startup-project src/Amr.Api
dotnet tool run dotnet-ef migrations list --project src/Amr.Infrastructure --startup-project src/Amr.Api
dotnet tool run dotnet-ef migrations script --idempotent --project src/Amr.Infrastructure --startup-project src/Amr.Api -o amr-migrations.sql
```

The same `ConnectionStrings__Amr` variable is used by `dotnet ef` (through a design-time factory), so no credential is
written to a file. The idempotent script can be reviewed and applied by a DBA instead; it is safe to apply repeatedly.
New migrations are created with `dotnet ef migrations add <Name> ... --output-dir Persistence/Migrations`; a test fails if
the model and the migrations disagree.

**Local development and tests.** Use a disposable server, never a shared one. For example:

```powershell
docker run -d --name amr-test-pg -e POSTGRES_PASSWORD=<throwaway> -p 127.0.0.1:55432:5432 postgres:17-alpine
$env:AMR_TEST_POSTGRES = 'Host=127.0.0.1;Port=55432;Username=postgres;Password=<throwaway>;Database=postgres'
```

`AMR_TEST_POSTGRES` is an admin connection string. Each database test class creates its own `amr_it_<guid>` database,
applies the migrations, and drops the database afterwards. Without the variable the PostgreSQL tests are reported as
skipped; with `AMR_REQUIRE_POSTGRES=true` a missing server fails them instead.

## Health

`GET /api/v1/health` reports `api`, `pythonService`, `model` and `database`. The `database` component is:

| Status | `detail` | Meaning |
|---|---|---|
| healthy | none | Reachable and every migration applied |
| unhealthy | `database_unavailable` | Cannot connect, authenticate or answer within the health timeout |
| unhealthy | `database_migrations_pending` | Reachable, but the schema is behind the migrations (the API does not migrate) |

Only these stable codes are reported; connection details never are. `GET /api/v1/health/live` does not depend on the
database.

## Live tests and CI

`backend/scripts/run-live-tests.ps1` starts the real Python service, waits for `/internal/health` to report a ready
model, sets `AMR_PYTHON_URL`, and runs the live tests with `AMR_REQUIRE_LIVE=true` and `AMR_REQUIRE_POSTGRES=true`, so a
missing service or database fails the run instead of skipping tests. Before running, it lists the tests its filter selects
and fails if either live class has none; afterwards it fails if the reported total differs from the listed count. It stops
the service in a `finally` block and exits with the test result. Prerequisites: the repository `.venv` (or
`-Python <path>`), a disposable PostgreSQL server in
`AMR_TEST_POSTGRES`, and the .NET SDK. It runs on Windows PowerShell 5.1 and on PowerShell 7 (Windows and Linux).

```powershell
.\backend\scripts\run-live-tests.ps1
```

**CI.** `.github/workflows/ci.yml` runs on pull requests and on pushes to `main` and `backend` with three independent jobs:

| Job | Runner | What it runs |
|---|---|---|
| `dotnet` | ubuntu-24.04 + PostgreSQL 17 service | `dotnet restore --locked-mode`, `dotnet build -warnaserror`, then every unit and integration test except the live classes, with `AMR_REQUIRE_POSTGRES=true` |
| `python` | windows-2025 | `ml/requirements-lock.txt` plus `service/requirements-dev.txt` (the lock is a Windows freeze), then the full `pytest` suite |
| `live` | ubuntu-24.04 + PostgreSQL 17 service | `service/requirements.txt`, then `run-live-tests.ps1`, which runs only `LivePythonServiceTests` and `LiveEndToEndTests` with skipping disabled |

The PostgreSQL service uses `POSTGRES_HOST_AUTH_METHOD=trust` on the job's private network, so no password or secret is
stored. All three jobs completed successfully on GitHub for the push to `backend` at `e11e0e5` (run #2) and for pull
request #1 (run #3), according to the Actions run pages. The job logs were not inspected, so the remote test counts and
skip counts are not independently confirmed. Branch protection and required status checks have not been verified.

## Known limitations for frontend integration

These are accepted prototype scope decisions or behaviors to design around. None is a known defect in the implemented
behavior; each would need its own approved change.

| Area | Kind | Behavior | What the frontend should do |
|---|---|---|---|
| Browser origin / CORS | Scope decision | No CORS policy, HTTPS redirection or host restriction is configured (`AllowedHosts` is `*`). A page on a different origin is blocked by the browser. | Use a same-origin or development proxy, or request a CORS policy with an explicit allowed origin before cross-origin use. |
| Authentication and rate limiting | Scope decision | None. Every route is anonymous and unthrottled. | Treat the API as a trusted local or private-network service; do not expose it publicly as is. |
| POST retry and idempotency | Scope decision | `POST /simulations` and `POST /comparisons` have no idempotency key and are never retried server-side. A client retry after a timeout runs Python again and creates a new run with a new id. | Do not retry automatically. Disable the submit control while a request is in flight and let the user resubmit deliberately. |
| Id only after 201 | Behavior | The run id is issued only with the 201 response. If the save fails (503 `database_unavailable` or 500 `persistence_failed`) the run has no record and no id. A client that cancels or disconnects can, rarely, leave a stored run it never learned the id of. | Show the failure and offer a new run; find stray runs through the recent list. |
| Recent runs | Behavior | `GET /simulations/recent` returns simulations and comparisons together (`kind`), newest first, `pageSize` at most 50. There is no comparison-only list. The count and the page are separate queries, so concurrent writes can shift page boundaries. | Filter by `kind` on the client; do not assume a page set is a stable snapshot. |
| OpenAPI | Scope decision | No OpenAPI or Swagger document is generated. Controllers declare response types, but the published contract is this document. | Code against this document and the problem-details shape below; generated clients are not available. |
| Error handling | Behavior | Every failure is `application/problem+json` with a stable `code` and `correlationId` (see Validation and errors). 422 is validation, 404 unknown run or route, 503 `database_unavailable`, `database_migrations_pending` (health only), `model_unavailable`, `python_service_unavailable` and `python_service_timeout`, 502 `python_service_invalid_response`, 500 `persistence_failed`, `comparison_contract_violation` and `internal_error`. A client abort is logged and answered with a non-standard 499 that the aborting client never sees. | Branch on `code`, not on `detail` text; show the correlation id for support; treat 503 as retryable by the user and 500 as not. |
| Scientific meaning | Contract | One run is one stochastic rollout, not a statistical result. A drug can be susceptible yet have no candidate transition (`unsupported_no_candidate`); this is not the same as ineffective. Metric definitions are returned with each run. | Keep unsupported-transition status and metric definitions visible next to results, and label recommendations as policy choices, not clinical advice. |

