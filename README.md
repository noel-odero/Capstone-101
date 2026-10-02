# Antibiotic Stewardship Simulation for MDR *E. coli* UTI
This repository currently contains a scientific simulation and a reproducible computational baseline pipeline for studying sequential antibiotic selection
under resistance dynamics.

The research question is whether choosing treatment with future resistance options in mind changes simulated outcomes compared with simple current-state strategies. This submission establishes the simulation and baselines before PPO development.

## Scope and Safety

This is a research prototype, **not a clinical prescribing system**. It does not diagnose infection, identify pathogens, perform susceptibility testing, select dosage, predict clinical cure, replace clinicians, or establish clinical
effectiveness.

## Current Status

### Simulation

- Seven canonical antibiotic actions, shared between the action space and
	seven-bit resistance state.
- Gymnasium stochastic environment with encoded observations, treatment
	effectiveness, reward, episode termination, reproducible seeds, and transition
	provenance.
- Cross-resistance, collateral-sensitivity, neutral, and unsupported/no-candidate
	outcomes are represented explicitly.
- Reward combines current treatment effectiveness, resistance-count change, and
	antibiotic exposure. Default weights are `1.0`, `0.5`, and `0.1`.

### Baselines and Evaluation

- Seeded uniform random policy.
- Observation-based greedy policy that chooses uniformly among currently
	susceptible antibiotics.
- Separate deterministic reference environment and finite-horizon value
	iteration solution. This is an exact computational fixture, not a claim that
	bacterial evolution is deterministic.
- Episode runner, raw trajectory records, and metrics for effectiveness,
	resistance emergence, future effective antibiotics, exposure, reward, and
	termination.
- Multi-seed orchestration, run-level confidence intervals, and explicitly
	assumption-gated paired strategy comparisons.
- Regenerable Sprint 4 baseline report for random and greedy policies across the
	primary transition scenario and three sensitivity scenarios, plus a separately
	labeled exact deterministic-reference result.

The latest full suite recorded **445 passing tests**. Run the test command below
to verify the current checkout.

## Scientific and Computational Data

The simulator uses curated processed tables rather than reading raw papers at
runtime:

- `data/processed/action_space.csv`: seven drugs and canonical action order.
- `data/processed/empirical_interactions.csv`: 25 curated pairwise interaction
	records used to generate candidates when directionality and state permit.
- `data/processed/evidence_registry.csv`: source and interpretation provenance.
- `data/processed/transition_uncertainty.csv` and
	`transition_parameters.csv`: uncertainty and parameter status; unresolved
	episode-level probabilities remain blank.
- `data/processed/transition_sampling_config.csv`: schema only; currently has no
	configured rows.
- `data/processed/reference_scenarios.csv`: six software fixtures, not observed
	biological outcomes or population estimates.

The candidate generator currently uses supported directional records and does
not convert strain counts, paper counts, evidence strength, or confidence into
transition probabilities. Unknown-directionality interactions remain in the
data but are excluded from directional transitions.

The primary stochastic scenario, `REF_UNIFORM_SUPPORTED`, selects uniformly
among deduplicated applicable candidates whenever candidates exist. This forces
a supported candidate outcome on such steps and is **not** an empirical
probability of resistance emergence. Sensitivity scenarios use illustrative
computational occurrence assumptions `q = 0.25`, `0.50`, and `0.75`; these are
not biological estimates. Scenarios are reported separately.

Raw materials include the Sakenova 2025 supplementary spreadsheet and four
Iwasawa trajectory CSV files. The Iwasawa smoothing script is exploratory and
does not calibrate the simulator's binary transition probabilities.

## Baseline Snapshot

The committed plan uses 20 runs per policy and stochastic scenario, all 128
binary initial resistance profiles with equal computational weight, and an
eight-step horizon. The profiles are not a clinical prevalence distribution.
The complete generated Markdown and JSON report is in the local ignored
`experiments/results/baseline/` directory after regeneration; the JSON includes
all trajectories and is large, so it is not tracked in Git.

Selected mean episode metrics from the generated report:

| Scenario | Policy | Effectiveness | Resistance emergence | Future effective drugs | Exposure | Cumulative reward |
|---|---|---:|---:|---:|---:|---:|
| `REF_UNIFORM_SUPPORTED` | Random | 0.4489 | 0.1869 | 2.6648 | 7.8582 | -1.9499 |
| `REF_UNIFORM_SUPPORTED` | Greedy | 1.0000 | 0.1079 | 3.0930 | 7.9375 | 6.9402 |

These are simulated outcomes, not clinical estimates. Comparisons are reported
as separate metrics; no overall score is used. Paired p-values in the current
report are withheld because symmetry of differences has not been declared.
Run-level intervals and paired bootstrap intervals describe variation under
this simulator and its assumptions, not clinical or biological uncertainty.
No assumption is made that PPO will improve these results.

## Repository Map

```text
simulation/   State, actions, transition model, reward, and stochastic environment
ml/src/       Random/greedy policies, evaluation, metrics, inference, report code
ml/tests/     Tests for ML and evaluation components
data/raw/     Source supplementary and trajectory files
data/processed/ Curated action, evidence, interaction, and uncertainty tables
experiments/  Inspection notebook, report configuration, exploratory analyses
docs/         Scientific specifications and research interpretation
tests/        Simulation and processed-data tests
backend/      ASP.NET API scaffold placeholder
frontend/     React application scaffold placeholder
```

Backend and frontend directories are placeholders. PPO training, API integration,
and user-interface implementation have not begun.

## Setup and Validation

Requires Python 3.11. From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml/requirements.txt
python -m pytest
python ml/environment_check.py
```

The simulation inspection notebook is `experiments/simulation_inspection.ipynb`.
In VS Code, select the project `.venv` notebook kernel; the notebook changes its
working directory to the repository root before importing `simulation`.

Regenerate the baseline artifacts with:

```powershell
python -m ml.src.baseline_report --config experiments/baseline_config.json --output-dir experiments/results/baseline
```

The plan, seed schedules, software versions, configuration/data fingerprints,
raw trajectories, metrics, and uncertainty are retained in the JSON artifact.
Repeated runs with the same code, data, plan, and numerical environment are
expected to reproduce identical artifact hashes.

## Specifications

Start with [the interaction evidence interpretation](docs/research/antibiotic-interaction-evidence.md),
then see the [scientific specifications](docs/scientific-specification/) for the
state, observations, rewards, transitions, horizon, and evaluation contracts.
`docs/scientific-specification/baseline-report.md` explains the report's
interpretation and limitations.