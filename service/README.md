# Internal model-based evaluation service

FastAPI service over the shared frozen PPO/DQN inference layer (`ml/src/ppo_inference.py`) and the stochastic
resistance simulator. It is internal: the ASP.NET Core API is the intended caller, not the browser. It
stores nothing, and all output is model-derived research analysis, not clinical advice. The engine
uses a computational simulation; internal endpoint and schema names remain stable for compatibility.

## Install

Python 3.11, from the repository root (`python` on PATH may be a broken Store alias). Runtime only, in a new
virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r service/requirements.txt
```

For tests, add the development extras (`pytest`, `httpx`):

```powershell
.\venv\Scripts\python.exe -m pip install -r service/requirements-dev.txt
```

`service/requirements.txt` lists only what the service imports: the scientific stack pinned to the versions in
`ml/requirements-lock.txt`, plus FastAPI, Uvicorn and Pydantic. It does not install `jupyter`, `pandas` or
`pytest`. The research environment (`ml/requirements.txt`, the existing `.venv`) is unchanged and also runs the
service. Substitute `.\.venv\Scripts\python.exe` below if you use it. `venv/` is gitignored.

## Run

From the repository root. Use one worker: both models are verified and loaded once per process and predictions
are serialized inside the engine.

```powershell
.\venv\Scripts\python.exe -m uvicorn service.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Startup verifies the checkpoint SHA-256, the transition-data hash and the manifest contract (about 2 to 7 s).
If verification fails the service still starts, `GET /internal/health` returns 503 with `model_ready: false`,
and every model-dependent endpoint returns the same 503 error. Interactive docs: `/docs`.

## Test

```powershell
.\venv\Scripts\python.exe -m pytest -q          # whole repository
.\venv\Scripts\python.exe -m pytest service -q  # service only
```

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /internal/health` | 200 when both frozen models are verified and loaded, otherwise 503. |
| `GET /internal/model` | PPO/DQN identities and hashes, shared data hash, scenario, horizon, observation layout and mask rule. |
| `GET /internal/antibiotics` | Canonical action ids, names and drug classes (from `data/processed/action_space.csv`). |
| `POST /internal/profiles/validate` | Validate a 7-value 0/1 profile; returns feasible actions and terminal status. |
| `POST /internal/recommend` | One frozen-PPO action for a full context (`resistance_profile`, `last_action`, `treatment_step`). |
| `POST /internal/simulate` | One full episode for `strategy` `ppo`, `dqn` or `greedy` (Random Susceptible Baseline). |
| `POST /internal/compare` | PPO, DQN and the baseline from one profile and one environment seed. |

Horizon (8) and scenario (`REF_UNIFORM_SUPPORTED`) come from the verified manifest and are not request fields.
Unknown request fields are rejected.

## Semantics

- Resistance profile: canonical order `CIPROFLOXACIN, NITROFURANTOIN, FOSFOMYCIN, TRIMETHOPRIM, GENTAMICIN,
  MECILLINAM, CEFTAZIDIME`; `0` susceptible, `1` resistant. Unknown values are rejected.
- A feasible action is a currently susceptible antibiotic. A policy-selected action, a feasible action, an
  action with supported transition data and a clinically effective treatment are different things.
- `transition_status` `unsupported_no_candidate` means the simulator has no candidate transition for that action
  in that state and leaves the profile unchanged. A candidate set may be empty because directed evidence is absent or cannot apply to the current binary state; an unchanged profile does not demonstrate effectiveness.
- `selected_drug_susceptible` and `susceptible_action_rate` are simulator susceptibility flags, not efficacy.
- A valid all-resistant profile is a terminal result (HTTP 200): no feasible actions, `terminal_reason`
  `no_effective_antibiotic`, and a simulation with zero steps. A context at step 8 is terminal with
  `maximum_horizon`.
- Traces: `states` has `steps + 1` entries (state 0 is the initial state); each `steps[i]` goes from
  `states[i]` to `states[i + 1]`. Profile differences are derived from before/after profiles.
- Seeds: `environment_seed` and `policy_seed` are optional (0 to 4294967295); omitted seeds are generated and
  reported. PPO and DQN are deterministic and ignore `policy_seed`; the baseline uses it for tie-breaking.
- Comparison contract (`POST /internal/compare`): before returning, the service verifies that PPO, DQN and the
  baseline shared the initial profile, environment seed, scenario, horizon, transition-data hash, reward
  configuration and action-mask configuration (using the existing `match_run_pairs` plus explicit checks against
  the pinned model), and that their per-step transition seeds are equal by step index. The verified items are
  returned in `comparison_contract`. If any check fails the request returns 500
  `comparison_contract_violation` and no results.
- Matched seeds are not matched outcomes: a transition seed only seeds the random draw among the candidate
  transitions of the selected action in the current state, and those candidate sets differ by action and state.
  Equal transition seeds therefore do not guarantee identical transition outcomes
  (`transition_outcomes_guaranteed_identical` is always `false`), and trajectories can diverge once the actions
  differ. `comparison_contract.observed` reports the first divergent step. One paired run is a single sample and
  does not establish a superior strategy.

## Errors

All errors use `{"error": {"code", "message", "request_id", "details"?}}` and the `X-Request-ID` header carries the
same id. Stack traces and file paths are logged server-side only.

| Status | Codes |
|---|---|
| 422 | `request_validation_error`, `invalid_context` |
| 503 | `model_not_loaded`, `checkpoint_integrity_failure`, `model_contract_mismatch`, `model_or_data_unavailable` |
| 500 | `empty_action_mask`, `infeasible_policy_action`, `comparison_contract_violation`, `inference_failure`, `internal_error` |
| other | `http_error` (unknown route or method) |
