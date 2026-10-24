# Saved samples

Open **Samples** in the workspace navigation to record a label and seven binary resistance states. Saving records the initial resistance profile and server timestamp in PostgreSQL under the signed-in account, without starting an analysis. The form resets after a successful save so another sample can be entered immediately.

The library supports label search, date sorting, and **All / Not analyzed / Analyzed** categories. A sample is "Analyzed" only when it has a durably saved comparison. Failed or cancelled attempts do not change this status. Repeated analyses retain the same sample identity and original profile; their results accumulate under **Saved results**.

**New Analysis** opens the configuration form with the saved profile locked. Select **Review Analysis**, then **Run Analysis** to open the existing 3D resistance view, charts and metrics. **Analysis Results** remains available separately in the navigation. Seeds remain configurable. The API verifies sample ownership and the profile before executing Python; persistence checks them again and commits the sample link in the same transaction as the comparison. The database also enforces the owner-scoped foreign key. Profiles are immutable in this version: record a new sample for different starting conditions.

**Analysis History** provides **All analyses / Samples not analyzed / Samples analyzed** categories. Linked analyses display their sample label. **View Analysis** reopens their 3D resistance view. Existing records remain available and are not retrospectively matched to samples by profile, because multiple samples can have identical profiles.

The platform compares frozen PPO and DQN policies with a random susceptible-action baseline. These actions run inference and model-based evaluation, not model training. The underlying environment is a computational simulation, not a clinically validated predictor. Labels should identify samples without patient-identifying details.

API additions:

- `GET /api/v1/samples`: the current account's samples and saved comparison references.
- `POST /api/v1/samples`: `{ label, resistanceProfile }`.
- `GET /api/v1/samples/{id}`: an owned sample; another account's sample returns 404.
- `POST /api/v1/comparisons`: accepts optional `sampleId`; a mismatched profile returns 422. Sample links are returned on stored comparisons.

Migration: `AddSamples` adds `samples` and an optional, owner-scoped sample foreign key on `experiment_runs`. Existing experiments are preserved. Apply using the standard development migration command before starting the updated API.
