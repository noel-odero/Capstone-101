# Internal simulation service

FastAPI service over the existing frozen PPO inference layer (`ml/src/ppo_inference.py`) and the stochastic
resistance simulator. It is internal: the ASP.NET Core API is the intended caller, not the browser. It
stores nothing, and all output is simulation output, not clinical advice.

## Install

From the repository root, using the existing virtual environment (`python` on PATH may be a broken Store alias):

```powershell
.\.venv\Scripts\python.exe -m pip install -r service/requirements.txt
```

`service/requirements.txt` includes `ml/requirements.txt` and adds FastAPI, Uvicorn, Pydantic and httpx
(needed by the test client). The root requirements and lock file are unchanged.

## Run

From the repository root. Use one worker: the model is verified and loaded once per process and predictions
are serialized inside the engine.

```powershell
.\.venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Startup verifies the checkpoint SHA-256, the transition-data hash and the manifest contract (about 2 to 7 s).
If verification fails the service still starts, `GET /internal/health` returns 503 with `model_ready: false`,
and every model-dependent endpoint returns the same 503 error. Interactive docs: `/docs`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # whole repository
.\.venv\Scripts\python.exe -m pytest service -q  # service only
```

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /internal/health` | 200 when the frozen model is verified and loaded, otherwise 503. |
| `GET /internal/model` | Model id, checkpoint and interaction-data hashes, scenario, horizon, observation layout, mask rule. |
| `GET /internal/antibiotics` | Canonical action ids, names and drug classes (from `data/processed/action_space.csv`). |
| `POST /internal/profiles/validate` | Validate a 7-value 0/1 profile; returns feasible actions and terminal status. |
| `POST /internal/recommend` | One frozen-PPO action for a full context (`resistance_profile`, `last_action`, `treatment_step`). |
| `POST /internal/simulate` | One full episode for `strategy` `ppo` or `greedy` (Random Susceptible Baseline). |
| `POST /internal/compare` | PPO and the baseline from one profile and one environment seed. |

Horizon (8) and scenario (`REF_UNIFORM_SUPPORTED`) come from the verified manifest and are not request fields.
Unknown request fields are rejected.

## Semantics

- Resistance profile: canonical order `CIPROFLOXACIN, NITROFURANTOIN, FOSFOMYCIN, TRIMETHOPRIM, GENTAMICIN,
  MECILLINAM, CEFTAZIDIME`; `0` susceptible, `1` resistant. Unknown values are rejected.
- A feasible action is a currently susceptible antibiotic. A policy-selected action, a feasible action, an
  action with supported transition data and a clinically effective treatment are different things.
- `transition_status` `unsupported_no_candidate` means the simulator has no candidate transition for that action
  in that state and leaves the profile unchanged. It is a data gap, not evidence of effectiveness. FOSFOMYCIN,
  GENTAMICIN and CEFTAZIDIME never have candidates; support for the other drugs depends on the state.
- `selected_drug_susceptible` and `susceptible_action_rate` are simulator susceptibility flags, not efficacy.
- A valid all-resistant profile is a terminal result (HTTP 200): no feasible actions, `terminal_reason`
  `no_effective_antibiotic`, and a simulation with zero steps. A context at step 8 is terminal with
  `maximum_horizon`.
- Traces: `states` has `steps + 1` entries (state 0 is the initial state); each `steps[i]` goes from
  `states[i]` to `states[i + 1]`. Profile differences are derived from before/after profiles.
- Seeds: `environment_seed` and `policy_seed` are optional (0 to 4294967295); omitted seeds are generated and
  reported. PPO is deterministic and ignores `policy_seed`; the baseline uses it for tie-breaking.
- Comparison pairing: both strategies share the environment seed, so per-step transition seeds come from the
  same stream by step index. Trajectories can still diverge because candidate transition sets depend on the
  selected action. One paired run is a single sample and does not show either strategy is better.

## Errors

All errors use `{"error": {"code", "message", "request_id", "details"?}}` and the `X-Request-ID` header carries the
same id. Stack traces and file paths are logged server-side only.

| Status | Codes |
|---|---|
| 422 | `request_validation_error`, `invalid_context` |
| 503 | `model_not_loaded`, `checkpoint_integrity_failure`, `model_contract_mismatch`, `model_or_data_unavailable` |
| 500 | `empty_action_mask`, `infeasible_policy_action`, `inference_failure`, `internal_error` |
| other | `http_error` (unknown route or method) |
