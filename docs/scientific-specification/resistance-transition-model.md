# Resistance Transition Model

## Purpose

The resistance transition model defines how the simulated bacterial resistance state may change following antibiotic exposure.

The model supports sequential treatment by allowing the resistance state at time `t+1` to depend on the current state and the antibiotic selected at time `t`.

The transition is represented as:

`S_t + A_t -> S_(t+1)`

where `S_t` is the current resistance state and `A_t` is the selected antibiotic action.

## Transition Types

The MVP simulation supports four transition categories.

### 1. Unchanged State

The resistance state may remain unchanged following antibiotic exposure.

This transition is required because antibiotic exposure does not necessarily produce an observable change in the simulated resistance profile.

### 2. Cross-Resistance

A treatment exposure may be associated with increased resistance to another antibiotic.

A cross-resistance transition changes one or more previously susceptible resistance-state components from susceptible to resistant.

### 3. Collateral Sensitivity

A treatment exposure may be associated with increased susceptibility to another antibiotic.

A collateral-sensitivity transition may change a previously resistant component from resistant to susceptible.

### 4. Heterogeneous Outcomes

The same treatment exposure may produce different resistance outcomes across simulated trajectories.

Experimental evolution studies in E. coli demonstrate that bacterial populations can follow divergent evolutionary trajectories and exhibit different cross-resistance or collateral-sensitivity outcomes.

The simulator therefore does not treat every documented interaction as a deterministic transition.

## Evidence Sources

Transition candidates are informed by the evidence registry.

Relevant evidence includes:

- Podnecky et al. (2018), experimental collateral-resistance and collateral-sensitivity relationships in clinical UPEC isolates.
- Nichol et al. (2019), repeated cefotaxime evolution experiments demonstrating divergent evolutionary trajectories.
- James et al. (2024), experimental collateral responses in clinical UPEC isolates.
- Sakenova et al. (2025), systematic E. coli chemical-genetic mapping of cross-resistance and collateral-sensitivity relationships.

These sources provide evidence for possible resistance interactions but do not automatically provide clinical transition probabilities.

## Evidence Interpretation

A documented resistance interaction is treated as evidence that a transition relationship may be represented in the simulation.

The presence of an interaction does not imply that:

- the transition occurs in every exposure;
- the transition is deterministic;
- the relationship applies to every E. coli strain;
- the transition probability is known;
- the relationship is clinically guaranteed.

The simulator therefore distinguishes between evidence for an interaction and quantitative evidence for its probability.

## Transition Probability Representation

Transition probabilities must be represented computationally so that stochastic resistance trajectories can be simulated.

However, the MVP does not assign empirical probabilities directly from the existence of a published cross-resistance or collateral-sensitivity relationship.

Instead, each transition candidate records its uncertainty and supporting evidence.

The transition model must therefore support:

- candidate transitions;
- configurable transition probabilities;
- uncertainty metadata;
- supporting evidence sources;
- stochastic sampling using the configured probabilities.

The probability parameterisation will be documented separately from the evidence registry.

## Impossible Transitions

The simulation excludes transitions that violate the defined binary resistance representation.

For example:

- resistance values may only be `0` or `1`;
- a resistance state must contain exactly seven antibiotic dimensions;
- an antibiotic cannot transition to an undefined action-space drug;
- an unchanged state must preserve the current resistance profile;
- collateral sensitivity cannot change a susceptible state into another value;
- cross-resistance cannot change a resistant state into another value.

Transitions unsupported by the evidence model or explicit simulation assumptions are not treated as evidence-based biological transitions.

## True State and Observation

Resistance transitions operate on the simulation's true bacterial state.

The RL agent does not directly observe the true future state.

After a transition occurs, the environment generates the corresponding observation according to the observation model.

This preserves the distinction between the simulated biological state and the information available to the decision-making agent.

## Stochasticity

The simulation supports stochastic transitions.

When multiple transition outcomes are possible, the environment samples a next state according to the configured transition probabilities.

Random seeds are recorded to support reproducible experiments and multi-seed evaluation.

## Scope and Limitations

The MVP represents resistance at the antibiotic-level phenotype rather than modelling individual bacterial mutations, resistance genes, molecular mechanisms, or whole-genome evolution.

The model does not claim to reproduce patient-level bacterial evolution.

Experimental evidence is used to constrain plausible transition relationships, while uncertainty is explicitly retained where quantitative transition probabilities are unavailable.

Clinical surveillance data may be used to define plausible initial resistance states and scenario distributions, but are not assumed to identify causal within-treatment evolutionary transition probabilities.

## Relationship to Later Components

The resistance transition model provides the state dynamics used by:

- the simulation environment;
- the treatment sequence evaluator;
- the reinforcement-learning environment;
- the reward function;
- resistance-emergence metrics;
- future-treatment-option metrics.

The transition model therefore forms the core biological-dynamics component of the sequential treatment simulation.