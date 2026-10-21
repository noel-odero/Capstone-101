# Workbench benchmark against the proposed product

Reviewed 21 October 2026 against the supplied antibiotic stewardship workbench concept and the current frontend, public API, Python service and scientific code. This is a product-capability benchmark, not a new statistical comparison of policy performance.

## Finding

The platform implements the central research loop: configure a binary seven-antibiotic profile, run a PPO-versus-baseline comparison, inspect trajectories and simulated metrics, and reopen persisted runs. It is a credible core for the proposed workbench, but it does **not yet implement the entire end product**. Scenario/horizon selection, unknown inputs, full evidence/provenance presentation, exports and aggregate evaluation remain gaps.

The public landing page now presents StewardLab as a working research-product name. The authenticated application retains its existing AMR Decision Support name until a platform-wide naming decision is made.

## Capability comparison

| Proposed capability | Current status | Evidence and practical limitation |
| --- | --- | --- |
| Research tool for stewardship pharmacists/researchers | Core present | Scenario and comparison workflows exist. There is no patient-management workflow or clinical eligibility model. |
| Seven named antibiotic choices | Implemented | `data/processed/action_space.csv`, `frontend/src/domain/antibiotics.ts`; choices are an action space, not seven concurrent prescriptions. |
| Configure susceptible/resistant profiles | Implemented | `ProfileEditor.tsx` has seven toggles, profile-code entry and two presets. The binary model has 128 profiles; the all-resistant profile is terminal and cannot start an actionable sequence. |
| Unknown susceptibility | Not implemented | `service/schemas.py` explicitly excludes unknown values; `resistanceStateSchema` accepts only 0/1. Unknowns must not silently become susceptible. |
| Select a documented transition scenario | Not implemented | The frozen manifest fixes `REF_UNIFORM_SUPPORTED`. `CompareRequest` and `CreateComparisonRequest` do not accept a scenario. A label showing a scenario is not a scenario selector. |
| Choose simulation horizon | Not implemented | The model fixes eight steps. The results-page horizon control has one supported value; it is not a configurable duration. |
| Compare PPO against the existing baseline | Implemented | `useCreateComparison.ts`, `SimulationPage.tsx`, `service/schemas.py`. Both strategies share starting conditions and record seeds. |
| A genuinely greedy optimizer as the alternative | Terminology correction needed in the concept | `ml/src/greedy_policy.py` uses uniform random choice among susceptible actions. The accurate public label is Random Susceptible Baseline. It does not search for an optimal sequence. |
| Susceptible-action feasibility | Implemented | Live model metadata reports `susceptible_actions_only`. Susceptible-action rate is mask adherence, not clinical efficacy or a differentiating treatment-success score. |
| Resistance trajectories and burden | Implemented | `TrajectoryChart.tsx`, `ComparisonMetrics.tsx` and returned API metrics. Charts show per-state counts; cumulative normalized burden summarizes the whole episode. |
| Remaining susceptible options | Implemented | Returned `finalSusceptibleCount`. It is related to resistance burden but measures the final state rather than the whole trajectory. |
| Inspect selected actions and state changes | Implemented | `StepInspector.tsx` displays action, susceptibility, transition support, outcome, reward and feasible actions. |
| Inspect evidence source IDs and candidate transitions | Partial | API step traces contain `sourceIds`, `candidateTransitions`, sampled probabilities and transition seeds. The current inspector does not display source IDs or the complete candidate evidence. This needs explicit UI work. |
| Reproducibility and assumptions visible to the researcher | Partial | Seeds can be supplied when creating a run, and returned data contain model/data hashes, scenario and seeds. `SimulationRunHeader.tsx` can display them but is not currently mounted on the results page. Current Profile metadata shows only part of the provenance. API storage alone is not complete user-facing auditability. |
| Save and revisit simulations | Implemented | Completed runs are persisted by the public API; `HistoryPage.tsx` provides paginated history and links to run details. User authentication scopes access. |
| Saved, named scenario library | Not implemented | Two profile presets are available. There is no reusable, named scenario collection or assumptions-management UI. |
| Export analysis for review | Not implemented | No user-facing JSON/CSV/report download exists. Reading raw API JSON is not equivalent to an export workflow. |
| Distinguish single runs from aggregate policy evidence | Partial | Current run views include a single-run caveat. Multi-seed evaluation and uncertainty tooling exist offline in `ml/src/matched_policy_evaluation.py`, `multi_seed_evaluation.py`, `statistical_comparison.py` and `ppo_seed_study.py`; there is no aggregate evaluation API/dashboard. |
| Determine clinical clearance, duration, doses or patient suitability | Outside the current model | No bacterial-load, infection-clearance, dosing, allergy, renal-function or pregnancy model exists. The 3D clearance animation is explicitly illustrative. Eight steps are computational decisions, not eight days or treatment courses. |
| Consistent research-only product language | Partial | The new landing page uses the requested research wording. Existing workbench titles such as Recommended Antibiotic Sequence / Top Recommendation should become PPO-selected sequence / First simulated action in a future copy pass. |

Evidence paths in the table are relative to the repository root. Frontend page/components are under `frontend/src/features/` and `frontend/src/components/`; request schemas are in `frontend/src/domain/types.ts` and `service/schemas.py`.

## Live verification

The standard stack was started in the requested order using Docker Desktop, `amr-test-pg`, the `.venv` interpreter, .NET on 5080 with `amr_frontend_dev`, and `npm run dev` on 5173. No database migration was needed.

`GET /api/v1/health` returned healthy and `ready: true` for API, Python, model and database. `GET /api/v1/model` confirmed:

| Setting | Live value |
| --- | --- |
| Model | `ppo_seed_12000` |
| Algorithm | `MaskablePPO` |
| Scenario | `REF_UNIFORM_SUPPORTED` |
| Horizon | 8 |
| Antibiotics | 7 |
| Action mask | `susceptible_actions_only` |

This verifies the served configuration, not clinical validity or population-level superiority. No patient data, production records or bulk comparison runs were created for this benchmark.

## Recommended next work

1. **Expose auditability already present in the data.** Mount the provenance header, show source IDs/candidate evidence, and add JSON/CSV export. Rename recommendation-oriented workbench headings to policy-selection language.
2. **Define scenario flexibility before expanding controls.** Document supported alternate scenarios/horizons and validate their compatibility with the frozen model and experimental protocol. Model unknown inputs explicitly before adding an unknown toggle. Add named scenario saving after that contract exists.
3. **Add a separate aggregate research workflow.** Serve verified multi-seed results with matched conditions and uncertainty. Keep those results distinct from a single run, and do not populate aggregate cards with invented statistics.

## Landing-page implementation

- Dark public default with a separate light-mode toggle; existing workbench theme preference is preserved.
- Requested hero copy, left-aligned headline and one main Launch Workbench action, plus the methodology link.
- Animated seven-node conceptual network. Its **20 undirected pairs** are derived from the union of documented interactions in `data/processed/empirical_interactions.csv`, restricted to the seven modeled drugs. `network-edges.json` retains source IDs. Undirected presentation means only that an interaction for the pair is documented; it does not claim reciprocal causation, equal probability, or identical support in every state.
- Colors cycle through explicitly illustrative profiles, independently of the policy or clinical biology. Pause and reduced-motion support are included.
- Three brief capability descriptions. The embedded workbench screenshot and its introductory section were removed following the updated landing-page direction.
- Concise research disclaimer and no invented efficacy, user, patient or model-confidence statistics.
- Login and signup retain their form layout and use the landing page's dark navy/cyan or warm light palette. Public-page appearance is independent of the workbench's stored theme.
- `frontend/tests/e2e/landing.spec.ts` checks preview absence, navigation, independent theme state, matching authentication colors, scientific-API independence and mobile/tablet layouts.

## Completed checks

- Production TypeScript/Vite build passed.
- All 184 unit/component tests passed with `npm test -- --maxWorkers=1`. The parallel run hit two auth/profile lazy-loading timeouts; both passed in the serial suite.
- All 12 Chromium checks passed, including the existing workbench screens, the 3D scene, landing-page navigation, theme separation, and 390px/768px layouts.
- `node scripts/verify-landing.mjs` passed against the running app without mocked responses: desktop dark/light, mobile, preview image loading and no browser errors.
- Live screenshots are in ignored `frontend/playwright-report/landing-live/`; the page is available at http://localhost:5173.
