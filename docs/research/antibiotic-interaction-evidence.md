# Antibiotic Interaction Evidence

## 1. Purpose

The simulation requires evidence describing how resistance to one antibiotic may affect susceptibility to another antibiotic. This evidence is used to define plausible relationships in the *E. coli* resistance environment.

The evidence registry is maintained in:

`data/processed/evidence_registry.csv`

This document describes how that evidence is interpreted and incorporated into the project.

## 2. Interaction Types

The project uses four relationship categories:

- **Cross-resistance (CR):** resistance to one antibiotic is associated with reduced susceptibility to another.
- **Collateral sensitivity (CS):** resistance to one antibiotic is associated with increased susceptibility to another.
- **Neutral:** no meaningful collateral response is reported.
- **Mixed:** different evolutionary replicates or experimental conditions produced different responses.

Relationships are directional unless the source explicitly supports a bidirectional relationship.

For example:

`ciprofloxacin → gentamicin = CS`

means that resistance selected by ciprofloxacin was associated with increased susceptibility to gentamicin in the reported evidence.

## 3. Evidence Sources

### 3.1 Sakenova et al. (2025)

Sakenova et al. systematically investigated antibiotic interactions across 40 antibiotics in *E. coli* using chemical-genetic analysis.

The study provides evidence for cross-resistance, collateral sensitivity and neutral relationships and demonstrates that observed interactions can depend on the underlying resistance mechanism.

**Evidence type:** `chemical_genetic_inference`

This source provides broad interaction coverage but does not by itself provide empirical transition probabilities for sequential treatment.

### 3.2 Podnecky et al. (2018)

Podnecky et al. investigated collateral responses in clinical *E. coli* strains following experimentally selected antibiotic resistance.

The study provides experimental evidence that resistance to one antibiotic can produce reproducible collateral sensitivity or cross-resistance to another antibiotic across multiple clinical strain backgrounds.

**Evidence type:** `experimental_evolution`

### 3.3 Nichol et al. (2019)

Nichol et al. studied 60 independent *E. coli* populations evolved under cefotaxime exposure.

The study demonstrated heterogeneous evolutionary trajectories, with some antibiotic responses varying between replicate populations.

This evidence is particularly important for representing uncertainty in the simulation.

**Evidence type:** `experimental_evolution`

Where different responses were observed across replicate populations, the relationship is recorded as `mixed` rather than forcing it into a deterministic CR or CS category.

### 3.4 James et al. (2024)

James et al. investigated resistance evolution in clinical uropathogenic *E. coli* isolates.

The study provides UPEC-specific evidence for relationships involving trimethoprim, nitrofurantoin and fosfomycin.

**Evidence type:** `UPEC_experiment`

This source is particularly relevant because the capstone focuses on *E. coli* urinary tract infections.

## 4. Evidence Interpretation

Published interaction evidence describes observed relationships; it does not directly provide the transition probabilities required by the simulator.

Therefore, the project does **not** convert:

`CS = 1` or `CR = 1`

directly into a probability such as:

`P(resistance change) = 1.0`

Instead, the evidence registry identifies biologically plausible relationships that constrain the transition model.

Where quantitative probabilities are not available, transition probabilities will be treated as model parameters and subjected to sensitivity analysis rather than presented as experimentally measured values.

## 5. Evidence Hierarchy

Evidence is distinguished by experimental basis rather than collapsed into a single score.

The current registry contains:

- chemical-genetic inference
- experimental evolution
- UPEC-specific experiments

These evidence types are retained separately because they answer different questions and have different limitations.

UPEC-specific experimental evidence provides greater pathogen and clinical-context relevance, while broader *E. coli* experimental and chemical-genetic studies provide additional interaction coverage.

## 6. Role in the Simulation

The evidence registry informs the resistance transition model.

Conceptually:

`S_t + A_t → S_(t+1)`

where:

- `S_t` is the current resistance state,
- `A_t` is the selected antibiotic,
- `S_(t+1)` is the resulting state.

Transitions may represent:

- maintenance of the current state,
- increased resistance,
- decreased resistance,
- cross-resistance,
- collateral sensitivity,
- heterogeneous evolutionary outcomes.

The final transition probabilities will only be assigned where supported by quantitative evidence or explicitly defined modelling assumptions.

## 7. Limitations

The available literature does not provide a complete experimentally measured transition matrix for the final seven-drug action space.

Additional limitations include:

- interaction evidence is often pairwise rather than sequence-specific;
- experimental conditions differ between studies;
- resistance mechanisms can affect the observed relationship;
- chemical-genetic interactions are not equivalent to clinical treatment outcomes;
- clinical surveillance associations cannot by themselves establish evolutionary causation;
- experimental evolution results may vary across strains and replicate populations.


## 8. Current Evidence Set

The machine-readable evidence registry is the authoritative record of individual evidence observations:

`data/processed/evidence_registry.csv`

The registry currently combines evidence from Podnecky et al. (2018), James et al. (2024), Nichol et al. (2019), and Sakenova et al. (2025).

The registry may be expanded as additional relevant evidence is identified.