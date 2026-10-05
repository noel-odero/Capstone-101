# Resistance Transition Model

## Purpose

The resistance transition model defines how the simulated bacterial resistance state may change following antibiotic exposure.

The model supports sequential treatment by allowing the resistance state at time `t+1` to depend on the current state and the antibiotic selected at time `t`.

The transition is represented as:

$$
S_t + A_t \rightarrow S_{t+1}
$$

where `S_t` is the current resistance state and `A_t` is the selected antibiotic action.

The model is intended to represent plausible resistance-state dynamics within the simulation. It does not claim to reproduce patient-level bacterial evolution or to predict the exact evolutionary response of an individual infection.

---

## Transition Types

The MVP simulation supports four transition categories.

### 1. Unchanged State

The resistance state may remain unchanged following antibiotic exposure.

This transition is required because antibiotic exposure does not necessarily produce an observable change in the simulated resistance profile.

An unchanged transition preserves the complete current resistance state.

### 2. Cross-Resistance

A treatment exposure may be associated with increased resistance to another antibiotic.

A cross-resistance transition changes a previously susceptible resistance-state component from susceptible to resistant.

The transition is represented as a candidate evolutionary outcome supported by experimental evidence. The existence of a documented cross-resistance relationship does not imply that the transition occurs after every exposure.

### 3. Collateral Sensitivity

A treatment exposure may be associated with increased susceptibility to another antibiotic.

A collateral-sensitivity transition changes a previously resistant resistance-state component from resistant to susceptible.

As with cross-resistance, collateral sensitivity is treated as a possible transition outcome rather than a deterministic consequence of treatment.

### 4. Heterogeneous Outcomes

The same treatment exposure may produce different resistance outcomes across simulated trajectories.

Experimental evolution studies in *E. coli* demonstrate that bacterial populations can follow divergent evolutionary trajectories and exhibit different cross-resistance or collateral-sensitivity outcomes.

The simulator therefore does not treat every documented interaction as a deterministic transition.

Instead, evidence-supported interactions may define multiple candidate outcomes from which the simulation can sample under an explicitly defined uncertainty scenario.

---

## Evidence Sources

Transition candidates are informed by the evidence registry.

Relevant evidence includes:

- Podnecky et al. (2018), experimental collateral-resistance and collateral-sensitivity relationships in clinical UPEC isolates.
- Nichol et al. (2019), repeated cefotaxime evolution experiments demonstrating divergent evolutionary trajectories.
- James et al. (2024), experimental collateral responses in clinical UPEC isolates.
- Sakenova et al. (2025), systematic *E. coli* chemical-genetic mapping of cross-resistance and collateral-sensitivity relationships.

These sources provide evidence for possible resistance interactions but do not automatically provide clinical transition probabilities.

The evidence layer therefore constrains which transition relationships may be represented by the simulator without being treated as a direct source of episode-level probability estimates.

---

## Evidence Interpretation

A documented resistance interaction is treated as evidence that a transition relationship may be represented in the simulation.

The presence of an interaction does not imply that:

- the transition occurs in every exposure;
- the transition is deterministic;
- the relationship applies to every *E. coli* strain;
- the transition probability is known;
- the relationship is clinically guaranteed.

The simulator therefore distinguishes between evidence for an interaction and quantitative evidence for its probability.

Evidence source information is retained as provenance so that simulated transitions can be traced back to the experimental observations that support them.

---

## Transition Probability Representation

Transition probabilities must be represented computationally so that stochastic resistance trajectories can be simulated.

However, the MVP does not assign empirical probabilities directly from the existence of a published cross-resistance or collateral-sensitivity relationship.

The current evidence audit found no directly defensible episode-level transition probabilities for the seven-antibiotic binary resistance-state model.

In particular, strain-level observations such as 8/10 or 7/10 cannot automatically be interpreted as:

$$
P(S_{t+1}\mid S_t,A_t)=0.8
$$

or:

$$
P(S_{t+1}\mid S_t,A_t)=0.7
$$

because those observations describe experimental outcomes across strains or replicates under particular experimental conditions rather than repeated observations of the same episode-level state-action transition.

The transition model therefore separates:

1. empirical evidence about possible interactions;
2. uncertainty about how those interactions should be parameterised;
3. computational probability assumptions used by a particular simulation scenario.

---

## Reference Uncertainty Scenario

### `REF_UNIFORM_SUPPORTED`

Because empirical episode-level transition probabilities remain unresolved, the initial simulator uses a predefined reference uncertainty scenario called `REF_UNIFORM_SUPPORTED`.

The purpose of this scenario is to provide a transparent and reproducible computational parameterisation of unresolved uncertainty.

The probabilities generated by this scenario are **reference-scenario assumptions**. They are not interpreted as empirical biological probabilities.

The formal pipeline is:

```text
Empirical evidence
       ↓
Possible transition outcomes
       ↓
Reference uncertainty scenario
       ↓
Probability distribution
       ↓
Sampled candidate transition
       ↓
Next resistance state
````

### Candidate Generation

For a given resistance state and selected antibiotic, the simulator first generates all evidence-supported candidate transitions that are applicable to the current state.

For cross-resistance:

* the selected antibiotic must match the documented source antibiotic;
* the target antibiotic must currently be susceptible;
* the candidate outcome changes the target antibiotic to resistant.

For collateral sensitivity:

* the selected antibiotic must match the documented source antibiotic;
* the target antibiotic must currently be resistant;
* the candidate outcome changes the target antibiotic to susceptible.

For neutral relationships:

* the relationship may be represented as an applicable candidate;
* applying the candidate does not change the resistance state.

Only currently supported directionality is used by the MVP transition generator. Relationships for which directionality remains unknown are not silently converted into directional transitions.

### Candidate Deduplication

Candidate transitions are deduplicated by:

* target antibiotic;
* transition outcome.

Multiple evidence sources supporting the same candidate do not create additional probability mass.

Instead, all supporting source identifiers are retained as provenance.

For example, if multiple sources support:

```text
CIPROFLOXACIN → GENTAMICIN = collateral sensitivity
```

the simulator represents this as one candidate transition with multiple supporting evidence sources.

The number of supporting sources therefore does not determine the probability of a candidate.

If different sources support different outcomes for the same relationship, those outcomes remain distinct competing candidates.

The simulator does not assign probabilities based on the number of papers supporting each outcome.

---

## Uniform Candidate Sampling

When multiple distinct applicable candidate transitions exist, `REF_UNIFORM_SUPPORTED` assigns equal computational probability to each candidate and selects one on every step where the set is nonempty. The scenario therefore forces one supported candidate outcome per such step. It is a computational reference, not an estimate of the chance that a biological resistance transition occurs after exposure.

For `N` applicable candidates:

$$
P(C_i)=\frac{1}{N}
$$

where `C_i` is an applicable candidate transition.

For example, if three distinct candidate transitions are applicable:

```text
Candidate 1 → 1/3
Candidate 2 → 1/3
Candidate 3 → 1/3
```

These probabilities are introduced by the reference scenario.

They do **not** mean that the biological outcomes are equally likely.

The scenario is intentionally used as a transparent reference configuration in the absence of defensible empirical probability estimates.

Under this primary scenario, applicable neutral candidates compete uniformly with resistance-changing candidates, preserving the current reference behavior. The sampler reports the conditional candidate-selection probability; that value is not a biological resistance-emergence probability.

### Transition-Occurrence Sensitivity Scenarios

Sensitivity scenarios make the transition-occurrence assumption explicit using `SENSITIVITY_Q_025`, `SENSITIVITY_Q_050`, and `SENSITIVITY_Q_075`, with occurrence weights 0.25, 0.50, and 0.75. Boundary settings `SENSITIVITY_Q_000` and `SENSITIVITY_Q_100` are also supported for implementation validation. These are illustrative computational assumptions, not empirical estimates or claims about bacterial biology.

For a sensitivity scenario with at least one applicable resistance-changing candidate, the no-transition outcome has probability `1 - q`. Conditional on a transition, each of the `N` deduplicated applicable resistance-changing candidates has probability `1/N`, so each has full scenario probability `q/N`. Neutral candidates are excluded from this resistance-changing distribution and receive zero probability while resistance-changing candidates are applicable. If only neutral candidates are applicable, one is selected uniformly as a supported neutral outcome; the occurrence weight does not apply. If no candidate of any kind is applicable, the state remains unchanged with status `unsupported_no_candidate`, distinct from both a neutral outcome and a sensitivity-gate `no_transition`.

For every sensitivity distribution with resistance-changing candidates, the candidate probabilities and no-transition probability sum to one. The primary reference scenario retains its existing behavior, including neutral candidates in its uniform candidate set. Results under the reference and sensitivity scenarios are outcomes under different computational assumptions and must not be interpreted as biological transition estimates.

---

## Single Candidate Application

The MVP applies exactly one sampled candidate transition per environment step.

This is a computational representation constraint rather than a biological claim that evolution changes only one resistance phenotype at a time.

Longitudinal experimental evolution data demonstrate that multiple resistance phenotypes can change during an evolutionary trajectory.

However, the available pairwise evidence does not establish a defensible joint probability distribution for simultaneous changes across the seven-antibiotic resistance state.

Therefore, the initial reference scenario does not independently sample multiple target antibiotics within a single environment transition.

This constraint keeps the MVP transition process explicit and reproducible while avoiding unsupported assumptions about joint evolutionary probabilities.

---

## No Applicable Candidate

If no evidence-supported candidate transition is applicable to the current state and selected action, the simulator retains the current resistance state.

This event means:

```text
no modeled evidence-supported transition
```

It does **not** mean:

```text
biological evolution did not occur
```

The distinction is important because the absence of a modeled transition does not establish the absence of biological evolutionary change.

The simulator should record this event explicitly so that the assumption remains visible during simulation analysis.

The corresponding computational status may be recorded as:

```text
unsupported_no_candidate
```

---

## Probability Provenance

Probability provenance must distinguish empirical evidence from computational assumptions.

The following probability-source categories are used:

* `empirical` - probability directly estimated from sufficiently comparable experimental data;
* `calibrated` - probability obtained through an explicitly documented calibration procedure;
* `model_assumption` - probability introduced as a modeling assumption;
* `reference_scenario` - probability introduced by a predefined reference uncertainty scenario;
* `unresolved` - no probability has been established.

`REF_UNIFORM_SUPPORTED` therefore uses:

```text
probability_source = reference_scenario
```

It must not label its probabilities as empirical.

This distinction is required for reproducibility and scientific interpretation.

---

## Stochasticity

The simulation supports stochastic resistance transitions.

Under the `REF_UNIFORM_SUPPORTED` scenario:

1. the current resistance state and selected antibiotic determine which candidate transitions are applicable;
2. duplicate candidates are removed while preserving evidence provenance;
3. one candidate is selected according to the scenario's probability distribution;
4. the selected candidate is applied to the current resistance state;
5. the resulting state becomes the next simulation state.

When only one candidate is applicable, that candidate is selected deterministically.

When multiple distinct candidates are applicable, each candidate receives equal computational probability under the reference scenario.

When no applicable candidate exists, the resistance state is retained unchanged and the event is recorded as an unsupported-no-candidate transition.

The transition result distinguishes a selected neutral candidate, an occurrence-gate `no_transition` result in a sensitivity scenario, and `unsupported_no_candidate`. A result without a selected candidate has no candidate-selection probability. The gate's `no_transition_probability` is only defined when resistance-changing candidates exist; an unsupported candidate set uses the deterministic unchanged-state fallback and reports `unsupported_no_candidate` instead.

Random seeds are recorded to support reproducible experiments and multi-seed evaluation.

The same state, action, scenario and seed should produce the same sampled transition.

Different seeds may produce different outcomes when multiple candidates are available.

---

## Reproducibility and Transition Metadata

Each sampled transition should preserve sufficient metadata to reconstruct and audit the computational decision.

Where applicable, the transition record should contain:

* scenario identifier;
* random seed;
* current resistance state;
* selected antibiotic;
* applicable candidate set;
* candidate probabilities;
* selected candidate;
* transition outcome;
* evidence source identifiers;
* transition status.

This metadata supports debugging, experiment reproducibility, scientific auditability and later inspection of why a simulated resistance state changed.

---

## Explicit Exclusions

`REF_UNIFORM_SUPPORTED` does not:

* infer episode-level transition probabilities from strain frequencies;
* interpret observations such as 8/10 or 7/10 as episode-level transition probabilities;
* treat the number of supporting papers as probability mass;
* treat confidence scores as probabilities;
* assume unsupported biological outcomes are impossible;
* independently sample each candidate target;
* infer joint transition probabilities from pairwise evidence;
* convert continuous IC50 trajectories directly into binary transition probabilities;
* claim that one resistance-state component is the only component that can biologically change during an evolutionary episode.

The reference scenario is therefore a controlled computational abstraction for evaluating sequential treatment policies under unresolved evolutionary uncertainty.

---

## Impossible Transitions

The simulation excludes transitions that violate the defined binary resistance representation.

For example:

* resistance values may only be `0` or `1`;
* a resistance state must contain exactly seven antibiotic dimensions;
* an antibiotic cannot transition to an undefined action-space drug;
* an unchanged state must preserve the current resistance profile;
* collateral sensitivity cannot change a susceptible state into another value;
* cross-resistance cannot change a resistant state into another value.

Transitions unsupported by the evidence model or explicit simulation assumptions are not treated as evidence-based biological transitions.

The absence of an evidence-supported transition should not be interpreted as proof that the corresponding biological event is impossible.

---

## True State and Observation

Resistance transitions operate on the simulation's true bacterial state.

The RL agent does not directly observe the true future state.

After a transition occurs, the environment generates the corresponding observation according to the observation model.

This preserves the distinction between:

* the simulated biological state;
* the state transition process;
* the information available to the decision-making agent.

The current MVP observation representation may expose susceptibility information directly. Future observation extensions may introduce unknown, noisy or delayed susceptibility information without changing the underlying distinction between state and observation.

---

## Scope and Limitations

The MVP represents resistance at the antibiotic-level phenotype rather than modelling individual bacterial mutations, resistance genes, molecular mechanisms, or whole-genome evolution.

The model does not claim to reproduce patient-level bacterial evolution.

Experimental evidence is used to constrain plausible transition relationships, while uncertainty is explicitly retained where quantitative transition probabilities are unavailable.

Clinical surveillance data may be used to define plausible initial resistance states and scenario distributions, but are not assumed to identify causal within-treatment evolutionary transition probabilities.

The binary seven-antibiotic representation is a computational abstraction of a more complex biological system.

The reference uncertainty scenario is therefore intended for simulation-based evaluation of sequential treatment policies rather than direct clinical prediction.

---

## Relationship to Later Components

The resistance transition model provides the state dynamics used by:

* the simulation environment;
* the treatment sequence evaluator;
* the reinforcement-learning environment;
* the reward function;
* resistance-emergence metrics;
* future-treatment-option metrics.

The transition model therefore forms the core biological-dynamics component of the sequential treatment simulation.

Its separation from the evidence registry, uncertainty configuration and reinforcement-learning policy allows each component to be evaluated independently.

The resulting architecture is:

```text
Evidence Registry
       ↓
Empirical Interactions
       ↓
Transition Candidates
       ↓
Uncertainty / Reference Scenario
       ↓
Transition Sampling
       ↓
Next Resistance State
       ↓
Observation
       ↓
RL Policy
```
