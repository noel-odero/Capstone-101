# Public evidence integration and retraining

The active training input is `data/processed/empirical_interactions.csv`. It now contains **45 records: 30 directed records across 18 distinct directed drug pairs, plus 15 predictions with unknown direction that remain excluded from sampling**. Every modeled antibiotic has measured outgoing evidence. These counts describe the curated research model, not clinical coverage.

## Integrated measurements

| Source | Added records | Treatment in the training table |
| --- | ---: | --- |
| `SAK2025_EXP` | 18 | All seven-drug outcome groups from Source Data Fig. 3. CS, XR/CR and neutral observations remain separate, including opposing effects for MEC → TMP. |
| `IBACACHE2018` | 1 | GEN → FOS increased MIC in the MG1655 ancestor cohort. Censored lower bounds and clone nesting are documented. The ΔdnaQ ancestor cohort is excluded. |
| `PHILLIPS2026` | 1 | CAZ → CIP increased MIC in the ceftazidime-only arm. The population-level fold change was reproduced from the raw duplicate measurements; combination arms are excluded. |

The original James records retain their clinical-strain context. Their notes now reference the public MIC data and explicitly identify the TMP → NIT binary flip as a research assumption: the reported MIC increase remained below the clinical resistance breakpoint. The neutral TMP → FOS observation and Sakenova's CS observation both remain identifiable by source.

The [research audit](transition-data-research-2026-10-23.md) and [public extracts](../../data/research/transition-data-2026-10-23/) provide the primary references and exact source locations. The evidence registry, transition-parameter table and uncertainty table were updated together with the training CSV.

`REF_UNIFORM_SUPPORTED` is unchanged: it samples unique applicable `(target, outcome)` candidates uniformly and merges their supporting source IDs. Lineage fractions and MIC fold changes are descriptive evidence, **not fitted per-step probabilities**. Mapping relative susceptibility changes onto binary states remains an explicit research abstraction. Unknown directions are not filled in or reversed.

Across all 448 feasible binary-profile/action combinations, candidate availability increased from 206 to 384. This includes measured neutral outcomes; it is not a measure of treatment effectiveness. State-inapplicable CS/XR relationships and unmeasured transitions still limit the model.

## Dataset and model versions

The original four evidence tables and frozen manifest are preserved under [interactions-v1](../../data/versions/interactions-v1/). Existing checkpoints, their hashes and prior study outputs are unchanged.

The app's existing frozen PPO remains explicitly pinned to the archived v1 interaction CSV. Both its inference engine and simulation rollout use that same file and verify its original hash. Default training environments use the updated CSV. This keeps the app usable while preventing an old checkpoint from silently running with new dynamics.

The new retraining configuration pins the updated table's canonical interaction hash:

```text
b82e2a1bf2c4d04f38d025cfcbd1d76831c495d0ef57bcd40ed9c2df018bea80
```

The benchmark archives the exact CSV in its output directory, rejects a mismatched dataset and checks it again on resume and completion. Old PPO checkpoints fail the new environment contract and are not reused.

## Run the retraining

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -B -m ml.src.dqn_benchmark `
  --config experiments\dqn_public_data_v2_config.json `
  --output-dir experiments\runs\public-data-v2 `
  --workers 3 `
  --resume
```

This trains fresh PPO and masked DQN models for the original 20 seeds, at 100,096 actual steps per model per seed. Both use the updated interactions, the same starting-profile design and matched evaluation seeds. A random susceptible-action baseline is evaluated on the same cases. `--resume` also works on the first invocation; subsequent invocations verify completed work and continue pending seeds. Keep the data, code and configuration unchanged while running or resuming.

Results are written to `experiments/runs/public-data-v2/report.json` and `report.md`, with checkpoints and traces under each `seed_<number>` directory. This research command does **not** replace the model served by the app. Activation of a retrained checkpoint requires a new frozen manifest that pins its checkpoint and v2 data together.

No full retraining was started during this integration; the user will run it.

## Verify the CSV derivation

```powershell
.\.venv\Scripts\python.exe -B experiments\integrate_public_evidence.py --check
```

The script rebuilds all four tables deterministically from the archived v1 tables and retained public extracts. Without `--check`, it writes those outputs only if the current tables match either v1 or the expected integrated version; it refuses to overwrite independently edited tables.
