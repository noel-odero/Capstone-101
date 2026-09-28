# Antibiotic Action Space

## 1. Purpose

The action space defines the antibiotics that the reinforcement-learning agent can select during a simulation episode.

The current action space is an MVP modelling decision. It is not a clinical recommendation or a claim that these are the preferred antibiotics for treating MDR *E. coli* UTI.

The machine-readable action space is maintained in:

`data/processed/action_space.csv`

## 2. Selection Criteria

Antibiotics were considered for the MVP action space using three criteria:

1. **Clinical relevance** to *E. coli* urinary tract infections.
2. **Pathogen relevance** to the MDR *E. coli* problem being modelled.
3. **Available evolutionary evidence** describing cross-resistance, collateral sensitivity or related resistance interactions.

The objective was to construct a sufficiently connected and evidence-supported computational environment while keeping the initial action space small enough for reliable evaluation and interpretation.

## 3. Locked MVP Action Space

The current action space contains seven antibiotics:

| Antibiotic | Primary basis for inclusion |
|---|---|
| Ciprofloxacin | Strong evolutionary interaction evidence and UTI relevance |
| Nitrofurantoin | UTI relevance and UPEC/evolutionary evidence |
| Fosfomycin | UPEC evidence and evolutionary interaction evidence |
| Trimethoprim | UTI relevance and multiple evolutionary relationships |
| Gentamicin | Documented collateral-sensitivity relationships and *E. coli* relevance |
| Mecillinam | Documented evolutionary relationships and UTI relevance |
| Ceftazidime | Documented evolutionary relationship and relevance to resistant *E. coli* |

Five of the seven drugs have documented relationships in the Sakenova et al. (2025) dataset:

- ciprofloxacin
- nitrofurantoin
- fosfomycin
- trimethoprim
- ceftazidime

The remaining drugs are supported by other experimental evidence in the evidence registry.

## 4. Evidence Coverage

The action space was not selected solely from Sakenova et al. (2025).

Instead, the final set integrates evidence from multiple sources:

- Sakenova et al. (2025)
- Podnecky et al. (2018)
- Nichol et al. (2019)
- James et al. (2024)

This prevents the action space from being determined by the coverage or experimental design of a single study.

## 5. Internal Connectivity

The selected antibiotics form a partially connected evolutionary interaction network in the current evidence registry.

Examples include:

- ciprofloxacin → gentamicin: CS
- ciprofloxacin → fosfomycin: CS
- ciprofloxacin → ceftazidime: CR
- ciprofloxacin → trimethoprim: CR
- ciprofloxacin → mecillinam: CR
- nitrofurantoin → ciprofloxacin: CR
- trimethoprim → nitrofurantoin: CR
- mecillinam → gentamicin: CS

These relationships are evidence observations, not transition probabilities.

## 6. Cefotaxime

Cefotaxime is retained in the evidence registry but is not part of the current MVP action space.

Nichol et al. (2019) reported both collateral sensitivity and cross-resistance following cefotaxime evolution across independent *E. coli* populations. This mixed evidence is important for modelling evolutionary uncertainty.

However, the currently registered cefotaxime relationships are primarily with antibiotics outside the seven-drug MVP network. Including cefotaxime at this stage would therefore add an action without providing sufficient connectivity to the current interaction environment.

Cefotaxime remains an extension candidate.

## 7. Interpretation of the Action Space

The seven-drug action space should be interpreted as:

> The set of antibiotics currently supported for computational experimentation within the capstone's MVP resistance environment.

It should not be interpreted as:

- a recommended clinical treatment sequence;
- a ranking of antibiotics;
- a complete representation of UTI treatment;
- a complete representation of *E. coli* resistance biology;
- evidence that all seven drugs are clinically interchangeable.

## 8. Future Extensions

The action space may be expanded if additional evidence provides sufficient support for additional antibiotics and their relationships within the simulated network.

Potential extension candidates remain outside the locked MVP until their clinical relevance, evidence coverage and integration requirements are evaluated.

Any expansion should update both:

`data/processed/action_space.csv`

and the corresponding scientific documentation.

## 9. Source of Truth

The structured action-space definition is:

`data/processed/action_space.csv`

The underlying evidence is maintained in:

`data/processed/evidence_registry.csv`

This document provides the scientific rationale and scope of the current action-space decision.