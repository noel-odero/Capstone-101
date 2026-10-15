# Public API contract notes

Decisions that are easy to get wrong. Code comments on the DTOs and interfaces carry the same statements.

## Strategy identifiers

| Public (`/api/v1`) | Python wire | Display label |
|---|---|---|
| `ppo` | `ppo` | Frozen PPO Policy |
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

PPO-specific for the MVP. It returns the PPO-selected steps of a stored simulation. When the id is unknown, or the run has
no PPO steps (a baseline simulation, a comparison id, a failed run), the response is the same explicit
`404 recommendation_not_found`; the two cases are deliberately indistinguishable. A recommendation is a policy choice
among simulator-feasible (susceptible) drugs; it is not clinical advice.

## What the public contract takes from Python

Evidence is in `service/schemas.py`, `simulation/reward.py`, `ml/src/ppo_training.py` and the fixtures under
`backend/tests/Amr.UnitTests/Fixtures/python`.

| Field | Python source | Decision |
|---|---|---|
| `rewardSpecification` | `RewardSpecification.to_dict()`; schema declares `dict[str, Any]`; today `objective`, `normalization`, `terminal_convention` (pinned by `simulation/tests/test_reward.py`) | Passed through verbatim as a map. No key is dropped or interpreted, and a future key appears without a code change. Keys keep their Python spelling. |
| `actionMaskConfiguration` (comparisons) | `PPOConfig.__post_init__` rejects anything but `{"enabled": true, "rule": "susceptible_actions_only"}` | Typed (`enabled`, `rule`), because the shape is enforced. |
| model `observation`, `actionSpace`, `actionMasking`, `inference` | Validated by `load_manifest` against the frozen manifest | Typed. Manifest file paths, the inference device, the Python `implementation` class name and `evaluation_utility` are not exposed. |
| Metric definitions | Returned only inside each Python run response | Not in the DTOs yet (open question). |

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
| Internal | 500 | `internal_error`, `comparison_contract_violation` |

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
`.\.venv\Scripts\python.exe -B backend/tests/Amr.UnitTests/Fixtures/generate_python_fixtures.py` from the repository root.

Readiness (`IDependencyHealthProbe`) reports `pythonService` and `model` separately: a reachable service with a model
that failed verification is `pythonService` healthy, `model` unhealthy (`model_unavailable`).

## Build reproducibility

- `global.json` pins SDK 10.0.401 with `rollForward: latestPatch` (patch updates within the 10.0.4xx band only).
- `nuget.config` clears machine-level sources and uses nuget.org only.
- `Directory.Packages.props` holds every package version; `MicrosoftPackagesVersion` keeps the Microsoft packages aligned.
- Each project has a committed `packages.lock.json`; set `CI=true` (or pass `--locked-mode`) to fail on drift.
- Nullable reference types and warnings-as-errors apply to every project; analyzers run at `latest-recommended`.
  Test projects additionally disable CA1707 (underscored test names) and CA1861 (inline expected arrays).
