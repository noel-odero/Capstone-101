# Transition-data research: 23 October 2026

Public researcher data can reduce our current gaps. Downloaded source files contain measured, directional effects for **fosfomycin, gentamicin and ceftazidime**, the three antibiotics with no outgoing directed relationships in our current extraction. These are candidates for a better evidence layer, not ready-made probabilities for our simulation.

This was a targeted literature and supplementary-data audit, not an exhaustive systematic review. It uses **public data only**; no author requests are required or planned. This document records the pre-integration findings. The subsequent [integration and retraining instructions](public-data-integration.md) describe the 20 measured records now added to the training CSV; model checkpoints remain unchanged.

## What is actually missing

At audit time, the interaction CSV contained 25 records: 10 directed records and 15 chemical-genetic predictions with unknown direction. That table is now archived under `data/versions/interactions-v1/`. `CandidateTransitionGenerator` excludes unknown directions. The original directed outgoing counts were:

| Origin | CIP | NIT | FOS | TMP | GEN | MEC | CAZ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current records | 5 | 1 | 0 | 2 | 0 | 2 | 0 |

An empty candidate set also occurs when a known relationship cannot change the current binary state: a CS target is already susceptible or an XR target is already resistant. Both situations currently receive `unsupported_no_candidate`. Consequently, the benchmark's flagged-step percentage is **not a direct estimate of missing literature**.

There are three separate research needs:

1. Directed drug relationships, including neutral and conflicting observations.
2. Measurements that justify our binary state changes.
3. Conditional transition probabilities over a defined exposure interval, starting state and biological context.

The public files below improve the first need and help audit the second. They do not establish the third for all our starting profiles.

## Verified public data

| Study | Material actually inspected | Contribution and limit |
| --- | --- | --- |
| [Sakenova et al., 2025](https://www.nature.com/articles/s41564-024-01857-w) | Downloaded Source Data Fig. 3, Extended Data Fig. 2, Fig. 6 and Supplementary Table 3 | Fig. 3 contains **10 directed pairs within our seven-drug set**, represented by 18 outcome-group rows. Six pairs are absent from our current directed extraction. Experimental measurements resolve directions that OCDM predictions alone cannot establish. |
| [Phillips et al., 2026](https://academic.oup.com/g3journal/article/16/5/jkag046/8503885) | Downloaded `CEFBOR_MIC_pub.xlsx` from the authors' [Figshare deposit](https://doi.org/10.25387/g3.29630732); read `raw_MIC` and `MIC_compiled` | The ceftazidime-only arm supports **CAZ → CIP increased MIC**. Keep this arm separate from combination-selection arms. |
| [Ibacache-Quiroga et al., 2018](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2018.00427/full) | Downloaded supplementary archive through Europe PMC; parsed `DataSheet1.docx`, Tables S5 and S6 | Gentamicin-evolved clones have measured CIP, FOS and TMP responses. **GEN → FOS increased MIC** is a clear addition. Normal and hypermutator backgrounds must remain separate. |
| [James et al., 2024](https://www.nature.com/articles/s44259-024-00037-4) | Downloaded the authors' [GitHub data archive](https://github.com/Alhubb/Collateral-Effects-of-AMR); read `Data/MIC_all_tidy.csv` | 117 MIC rows: three assayed drugs, 13 strain labels and three measurements per combination. Useful for checking our existing TMP-origin mappings; does not add FOS-origin experiments. |
| [Podnecky et al., 2018](https://www.nature.com/articles/s41467-018-06143-y) | Inspected article, supplementary PDF and data-availability statement | Clinical-strain evidence for CIP, MEC, NIT and TMP origins. Supplementary Fig. 2 contains a broader IC90 matrix than our selected conserved relationships. Native replicate data were not verified publicly; supplementary genomic XLS files are not that susceptibility matrix. No additional measurements were transcribed from the rendered heatmap. |
| [Chowdhury and Findlay, 2025](https://academic.oup.com/jac/article/80/11/3107/8277598) | Inspected article's directional and sequential results and data-availability statement | Repeated CIP/GEN experiments can test whether our assumed transitions transfer to a sequential setting. The linked BioProject holds sequence data; a machine-readable phenotype table was not verified. |

Exact download URLs, SHA-256 hashes, archive members and inspection locations are recorded in [the source manifest](../../data/research/transition-data-2026-10-23/sources.json). The useful public measurements are retained in [the research data folder](../../data/research/transition-data-2026-10-23/). Full downloaded archives remain in the ignored local directory `experiments/results/transition-data-audit-2026-10-23/`. Files were read as data; downloaded analysis code was not executed.

| Retained file | Contents |
| --- | --- |
| [Sakenova directional outcomes](../../data/research/transition-data-2026-10-23/sakenova-directed-outcomes.csv) | 18 outcome groups for ten directed pairs; group means, lineage denominators and source row numbers. |
| [Gentamicin susceptibility measurements](../../data/research/transition-data-2026-10-23/ibacache-gen-mic.csv) | 60 sampled clones and two ancestors; GEN, CIP, FOS and TMP MICs. Whitespace removed from numeric cells; censoring signs retained. |
| [James MIC measurements](../../data/research/transition-data-2026-10-23/james-mic.csv) | Original 117-row CSV copied from the public archive without transformation; original column names retained. |
| [Ceftazidime/ciprofloxacin measurements](../../data/research/transition-data-2026-10-23/phillips-caz-cip-mic.csv) | CEF-only arm and ancestor, duplicate MICs, population labels and the missing-clone marker; combination arms excluded. |

## Concrete effects we can investigate

The following are endpoint observations, **not probabilities per simulation action**.

| Measured direction | Observation | Source location | Why it matters |
| --- | --- | --- | --- |
| FOS → TMP | CS in 12/12 reported lineages | Sakenova Fig. 3, Excel row 63 | Fills an absent FOS-origin relationship. |
| GEN → CIP | CS in 5/12; neutral in 7/12 | Sakenova Fig. 3, rows 50–51 | Fills an absent GEN-origin relationship while preserving heterogeneity. |
| MEC → NIT | CS in 3/9; neutral in 6/9 | Sakenova Fig. 3, rows 15–16 | Adds a measured direction; denominator is nine, not twelve. |
| NIT → MEC | CS in 9/12; neutral in 3/12 | Sakenova Fig. 3, rows 13–14 | Shows why reciprocity must be measured separately. |
| MEC → CIP | XR in 4/9; neutral in 5/9 | Sakenova Fig. 3, rows 111–112 | Adds a direction absent from our extraction. |
| TMP → MEC | Neutral in 12/12 | Sakenova Fig. 3, row 126 | Measured neutrality should remain distinct from untested data. |
| GEN → FOS | FOS MIC at least 8 µg/mL in the tabulated clones, against respective ancestors of 0.25 and 1 µg/mL | Ibacache-Quiroga Tables S5/S6 | Adds another GEN-origin effect. Values are censored lower bounds, not exact MICs. |
| CAZ → CIP | Reported compiled mean MIC fold change approximately 4.22 in the CEF-only arm | Phillips `MIC_compiled`, row 14; `raw_MIC`, columns I–J | Fills an absent CAZ-origin relationship with accessible raw measurements. |

All 18 relevant Sakenova outcome groups are preserved in the extracted CSV, including source row numbers, group means and denominators. They cover ten directed pairs; six were absent from the original extraction, with one of those six neutral-only. They are **not eighteen independent interactions**. Their curated derivatives are now included in the training table through the integration script.

For Phillips, the design has three evolution populations per arm with three sampled clones each. The CEF 1C MIC entry is marked `no o/n` and excluded in the methods. Recalculation from the eight valid clones gives population mean CIP fold changes of 4, 6.6667 and 2; averaging these reproduces the published compiled value, 4.2222. Duplicate measurements and sibling clones must not become independent evolution trials.

For Ibacache-Quiroga, Tables S5/S6 contain 22 MG1655-derived and 38 ΔdnaQ-derived clones. Those 60 sampled clones are not 60 independent clinical backgrounds or 60 independent evolution populations.

Sakenova Fig. 6 contains combination-selection outcomes and self-drug controls. It does **not** supply the missing single-drug CAZ → CIP measurement. The Phillips ceftazidime-only arm is the appropriate lead for that direction.

## Findings that change how we should interpret the model

**Binary resistance needs a mapping audit.** James reports TMP-associated increases in nitrofurantoin MIC below the clinical resistance breakpoint. Our current `TMP → NIT, CR` record can produce a binary susceptible-to-resistant flip. Relative reduced susceptibility alone does not establish that flip. Likewise, a fall in MIC does not necessarily restore clinical susceptibility. Preserve absolute measurements, assay definitions and the intended meaning of our binary research state. [James et al.](https://pubmed.ncbi.nlm.nih.gov/39036800/)

**Context can change the effect.** Our current James record describes TMP → FOS as neutral, while Sakenova's experimental dataset reports CS. Keep both with their strain and exposure metadata; do not overwrite one or combine them into an unqualified average. [James et al.](https://www.nature.com/articles/s44259-024-00037-4), [Sakenova source data](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41564-024-01857-w/MediaObjects/41564_2024_1857_MOESM7_ESM.xlsx)

**Endpoint frequencies are not exposure hazards.** These studies often measure susceptibility after resistance evolution to a selecting drug. Our action selects a currently susceptible drug for one abstract simulation step. An endpoint fraction cannot directly estimate `P(next profile | current seven-bit profile, one action)`. It also does not specify joint changes in several antibiotics or effects of treatment history.

The sequential study illustrates this problem: GEN adaptation produced CIP CS in 13/16 strains, while CIP adaptation produced GEN CS in only 1/16 under that study's conditions. Those are useful context-specific observations, not universal constants to replace either the clinical-strain results or Sakenova's measurements. [Chowdhury and Findlay](https://academic.oup.com/jac/article/80/11/3107/8277598)

**Coverage remains partial.** Seven drugs have 42 possible directed, non-self pairs. Neither a few added relationships nor an outgoing edge for every drug completes that matrix, covers all 128 starting profiles, or validates repeated eight-step dynamics. The present uniform candidate sampler remains a scenario assumption until a compatible transition model is specified and evaluated.

## Decision using public data only

The four retained extracts are usable now for evidence curation and mapping checks. They give measured leads for all three currently absent origins and preserve neutral, mixed and censored observations. Public data therefore support improving the relationship layer without waiting for anyone.

The following remain limitations: untested drug pairs, limited clinical backgrounds, incomplete starting-state coverage, incompatible endpoints and unknown per-action probabilities. Native replicate records not found in the public material are outside this audit's scope. We will retain these limitations rather than invent values, pool incompatible studies or delay the work for author responses.

## Recommended next implementation

1. Split the existing unsupported status into absent directional evidence and state-inapplicable relationships. Keep measured neutral outcomes separate.
2. Add a staged evidence table with exact drug identities, strain/background, selecting regimen, endpoint, ancestor and evolved MIC/IC90, units, censoring, lineage/replicate hierarchy and source location. Retain joint susceptibility panels where available.
3. Review the binary mapping, conflicting results and eligibility rules before promoting any records. Do not infer a reverse direction or substitute a related antibiotic.
4. Define a versioned research scenario appropriate to the measurements. Compare plausible mappings and strain strata, including unchanged outcomes. Estimate endpoint distributions only with their actual sampling units and uncertainty; leave unidentifiable per-step probabilities as explicit assumptions.
5. Freeze a new data version and rerun PPO, DQN and baseline comparisons together. Existing frozen results remain results for the old environment.

## Search scope and exclusions

Searches combined exact study titles, `E. coli`, `collateral sensitivity`, `cross-resistance`, `fosfomycin`, `gentamicin`, `ceftazidime`, `experimental evolution`, `source data` and `data availability`. Publisher articles, supplements and author-linked repositories were prioritized.

Screening required the selecting drug to be an origin, not merely an assay target. For example, [Lázár et al., 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3817406/) lists FOS and GEN among assayed drugs but not among its twelve selected evolution drugs. Its table therefore does not establish FOS- or GEN-origin experiments. Pseudomonas and Stenotrophomonas studies were excluded as direct E. coli parameter sources. Chemical-genetic predictions, surveillance correlations, sequencing accessions and review articles were not treated as measured directional transition data.

Validation for this audit checked eight downloaded asset hashes, all four retained extracts, the 18 outcome groups, the ten distinct directed pairs and their reported group denominators. The Phillips compiled fold change was reproduced from the raw measurements using the population hierarchy. No application tests or retraining were needed for this documentation and data-screening work.
