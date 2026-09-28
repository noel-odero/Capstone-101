# Treatment Effectiveness Model

## Purpose

The treatment effectiveness model determines whether a selected antibiotic is effective against the current simulated bacterial resistance state.

This model provides the treatment-effectiveness component of the simulation. It does not determine infection clearance, clinical cure, or overall treatment success.

## Effectiveness Rule

For antibiotic action `a` and true bacterial resistance state `S_t`:

- If the bacterial population is susceptible to the selected antibiotic, treatment is considered effective.
- If the bacterial population is resistant to the selected antibiotic, treatment is considered ineffective.

Formally:

E(S_t, a) =
    1 if S_t(a) = 0
    0 if S_t(a) = 1

where:

- `E(S_t, a)` is treatment effectiveness.
- `S_t(a)` is the resistance status for antibiotic `a`.
- `0` represents susceptibility.
- `1` represents resistance.

## True State vs Observation

Treatment effectiveness is determined from the simulation's true bacterial state.

The RL agent does not directly access this state. The agent receives only the defined observation described in `observable-state.md`.

This separation prevents the simulation from giving the agent information that would not be available through the proposed decision-support system.

## Relationship to Treatment Success

Treatment effectiveness is not equivalent to treatment success.

An effective treatment indicates that the selected antibiotic is active against the current simulated resistance state. Overall treatment success is determined at the episode level through the simulation's termination and clearance criteria.

The model therefore separates:

1. **Treatment effectiveness** — whether the selected antibiotic is effective against the current state.
2. **Treatment success** — whether the treatment strategy achieves the defined infection-clearance condition.
3. **Stewardship quality** — the efficiency of achieving successful treatment, including cumulative antibiotic exposure and resistance-related costs.

## Scope

The MVP does not model:

- Minimum inhibitory concentrations (MICs)
- Antibiotic dosage
- Pharmacokinetics
- Pharmacodynamics
- Patient-specific drug concentrations
- Clinical cure probabilities

These would require additional clinical and pharmacological parameters that are outside the scope of the current simulation.

The effectiveness model therefore uses a binary susceptibility/resistance abstraction.

## Implementation

The model is implemented in:

`simulation/treatment_effectiveness.py`

The selected action is first mapped to an antibiotic using the defined action space. The corresponding antibiotic is then checked against the true `ResistanceState`.

Invalid actions are rejected by the action-space implementation.

## Limitations

The binary effectiveness model is a computational abstraction. It does not claim that susceptibility guarantees clinical cure or that resistance guarantees treatment failure in an individual patient.

Its purpose is to provide a reproducible treatment-effectiveness signal for the simulation and reinforcement-learning environment.