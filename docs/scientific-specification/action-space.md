# Treatment Action Space

## Purpose and Scope

The treatment action space defines which antibiotics the reinforcement-learning agent can select during a simulation episode. The seven-drug set is an MVP modeling decision for computational experiments involving MDR *E. coli* urinary tract infections. It is not a clinical recommendation or a claim that these are the preferred antibiotics for treating an individual infection.

## Selection Criteria

Antibiotics were considered using the following criteria:

1. Clinical relevance to *E. coli* urinary tract infections.
2. Relevance to the MDR *E. coli* problem being modeled.
3. Available evolutionary evidence describing cross-resistance, collateral sensitivity, or related resistance interactions.
4. Representation of multiple antibiotic classes.

The goal was to create a sufficiently connected, evidence-supported computational environment that remains small enough for reliable evaluation and interpretation.

## MVP Action Set and Encoding

The action space contains seven discrete actions. IDs and ordering are fixed and must remain consistent across the simulation, training and evaluation pipelines, and any API.

| Action ID | Antibiotic | Primary basis for inclusion |
|---:|---|---|
| 0 | Ciprofloxacin | Strong evolutionary interaction evidence and UTI relevance |
| 1 | Nitrofurantoin | UTI relevance and UPEC/evolutionary evidence |
| 2 | Fosfomycin | UPEC evidence and evolutionary interaction evidence |
| 3 | Trimethoprim | UTI relevance and multiple evolutionary relationships |
| 4 | Gentamicin | Documented collateral-sensitivity relationships and *E. coli* relevance |
| 5 | Mecillinam | Documented evolutionary relationships and UTI relevance |
| 6 | Ceftazidime | Documented evolutionary relationship and relevance to resistant *E. coli* |

## Evidence Coverage and Connectivity

The action set is not based solely on Sakenova et al. (2025). It integrates evidence from Sakenova et al. (2025), Podnecky et al. (2018), Nichol et al. (2019), and James et al. (2024). Five drugs (ciprofloxacin, nitrofurantoin, fosfomycin, trimethoprim, and ceftazidime) have documented relationships in the Sakenova dataset; other selections are supported by experimental evidence recorded in the evidence registry.

Examples of relationships within the selected action set include:

- ciprofloxacin -> gentamicin: collateral sensitivity (CS)
- ciprofloxacin -> fosfomycin: CS
- ciprofloxacin -> ceftazidime: cross-resistance (CR)
- ciprofloxacin -> trimethoprim: CR
- ciprofloxacin -> mecillinam: CR
- nitrofurantoin -> ciprofloxacin: CR
- trimethoprim -> nitrofurantoin: CR
- mecillinam -> gentamicin: CS

These are reported evidence relationships, not transition probabilities. The action set represents antibiotics currently supported for computational experimentation; it is not a recommended treatment sequence, ranking, complete representation of UTI treatment or *E. coli* resistance biology, or evidence that the drugs are clinically interchangeable.

## Computational Representation and Sources of Truth

The structured action-space definition is maintained in `data/processed/action_space.csv`. It is the machine-readable source of action IDs, antibiotic names, and associated metadata. The evidence supporting interactions is recorded in `data/processed/evidence_registry.csv`.

`ActionSpace` in `simulation/action_space.py` loads and validates the action table, maps action IDs to antibiotics, and checks that its ordering matches the resistance-state ordering. The environment exposes the seven actions as a discrete action space.

This document records the scientific rationale, scope, and stable action-ID mapping for the current MVP. 