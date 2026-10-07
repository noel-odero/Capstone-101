# Antibiotic Stewardship Decision-Support System for Multidrug-Resistant *E. coli*

## 1. Project overview

### The problem

Antimicrobial resistance (AMR) is a growing global health challenge. Bacteria can develop resistance to antibiotics, making infections harder to treat and reducing the number of effective treatment options available.

A particularly important challenge is multidrug-resistant (MDR) *Escherichia coli* (*E. coli*), a bacterium associated with urinary tract infections (UTIs) and other infections. When *E. coli* becomes resistant to multiple antibiotics, choosing an effective treatment becomes more difficult. Treatment decisions can also influence which antibiotics remain effective in the future.

This project focuses on understanding and comparing antibiotic treatment strategies for MDR *E. coli*. Rather than treating each antibiotic choice as an isolated decision, the project explores how a sequence of treatment actions may affect bacterial resistance over time.

### My approach

The key idea is to make the possible consequences of different treatment actions easier to inspect and compare.

The system models bacterial resistance, simulates how resistance may change following antibiotic exposure, and uses decision-making methods to explore treatment strategies. This allows us to compare not only whether a treatment is currently effective in the simulation, but also how a sequence of actions may affect future treatment options.

The project has three major components:

1. **Bacterial resistance simulation:** Represents the resistance profile of an *E. coli* population and simulates possible changes in resistance after treatment actions.
2. **Decision-making model:** Uses computational policies and reinforcement learning methods to explore and compare sequences of antibiotic choices.
3. **Decision-support interface:** The planned user-facing component will make simulated treatment strategies, resistance trajectories, and comparisons easier to understand.

The current repository focuses primarily on the scientific simulation and computational decision-making foundations. It is not a clinical prescribing system and does not make recommendations for individual patients.


## 2. Development progress by sprint

The project is being developed incrementally. Each sprint establishes a foundation for the next.

### Sprint 1: Scientific specification

**Goal:** Define what the system represents before implementing the simulation.

During this sprint, I established the scientific and computational boundaries of the project.

Key work completed:

* Defined the problem scope around MDR *E. coli* urinary tract infections.
* Selected seven antibiotics for the initial computational action space:

  * Ciprofloxacin
  * Nitrofurantoin
  * Fosfomycin
  * Trimethoprim
  * Gentamicin
  * Mecillinam
  * Ceftazidime
* Defined the bacterial resistance state as a seven-element binary representation.
* Defined the observable information available to the decision-making model.
* Established how treatment effectiveness is represented.
* Specified how resistance transitions should be interpreted and modeled.
* Created an evidence registry to track scientific smyces and the relationships they report.
* Defined the reward function and evaluation metrics.
* Established an eight-step simulation horizon and episode termination conditions.

**Outcome:** A scientific specification that defines the system's scope, assumptions, state, actions, transitions, rewards, and evaluation goals.

### Sprint 2: Mathematical foundation of the simulation

**Goal:** Translate the scientific specification into a structured mathematical model that can be implemented.

This sprint focused on representing resistance interactions and uncertainty in a form suitable for computation.

Key work completed:

* Organized literature findings into an empirical interaction table.
* Represented cross-resistance, collateral sensitivity, neutral relationships, and unresolved interactions.
* Created a transition-parameter layer to distinguish observed evidence from parameters the simulator can actually use.
* Created a transition-uncertainty layer to record unresolved probabilities, unknown directionality, context dependence, heterogeneous observations, and model abstractions.
* Defined candidate transition generation from applicable evidence.
* Specified how candidates are deduplicated and sampled.
* Established a reference transition scenario and controlled software fixtures for testing transition behavior.
* Defined how uncertainty and probability provenance should be documented.

A key scientific limitation identified during this work was that the available literature does not directly provide defensible episode-level transition probabilities for my simplified seven-antibiotic binary model.

As a result, the simulator does not invent empirical probabilities. Its reference scenario is an explicit computational assumption, and separate sensitivity scenarios explore how alternative assumptions can affect simulated outcomes.

**Outcome:** A mathematical and data foundation that separates scientific observations, modeling assumptions, and computational transition behavior.

### Sprint 3: Simulation implementation

**Goal:** Implement the mathematical model as a functioning, reproducible simulation environment.

Key work completed:

* Implemented the seven-antibiotic action space.
* Implemented the bacterial resistance state and its validation.
* Implemented the observation representation and encoding.
* Implemented treatment action execution.
* Implemented cross-resistance, collateral-sensitivity, and neutral transition handling.
* Implemented candidate generation and stochastic transition sampling.
* Implemented episode progression and termination.
* Added reproducible random-seed handling.
* Built a Gymnasium-compatible environment.
* Created a simulation inspection notebook to explore and verify the environment's behavior.

The simulation distinguishes the underlying resistance state from the information observed by a decision-making policy. This provides a foundation for later work involving incomplete or delayed observations.

A pre-Sprint-4 validation checkpoint was also completed. It clarified the reference and sensitivity scenario semantics, corrected uncertainty metadata inconsistencies, preserved transition provenance in environment outputs, improved action validation, aligned observation bounds with the configured horizon, and added support for controlled initial resistance states.

**Outcome:** A tested and reproducible simulation environment that can execute treatment actions and generate resistance trajectories under explicitly documented assumptions.

### Sprint 4: Computational baselines and evaluation

**Goal:** Establish baseline decision-making methods and a deterministic reference for evaluating future approaches.

This sprint moved the project from a working simulator toward systematic policy comparison.

Key work completed:

* Implemented a **random policy** that selects uniformly from the available action space without using susceptibility or treatment history.
* Implemented a **greedy policy** that selects uniformly among antibiotics marked susceptible in the current observation.
* Created a separate **deterministic reference environment** with explicitly documented computational assumptions.
* Implemented **value iteration** to calculate optimal values and policies within the deterministic reference environment.
* Built the baseline evaluation and comparison infrastructure, following the sprint's planned evaluation cards.
* Established the metrics and reporting process for comparing policy behavior across simulation runs.

The deterministic reference environment contains 1,152 planning states at the default eight-step horizon: 128 resistance profiles across nine time points. It selects the lexicographically first applicable candidate and treats its selected next state as having probability one. This is a computational planning fixture, not a biological prediction.

The random and greedy policies provide comparison points for later reinforcement learning experiments. The deterministic reference and value-iteration solution provide an exact computational benchmark within the reference model's assumptions.

**Outcome:** A baseline and evaluation foundation that makes it possible to compare decision-making approaches systematically before introducing and assessing reinforcement learning.

---

## 3. How the simulation works

### Bacterial resistance state

The simulator represents resistance using a binary vector containing one value for each antibiotic.

* `0` means susceptible.
* `1` means resistant.

For example:

```text
0000000
```

represents a state susceptible to all seven antibiotics.

```text
1000000
```

represents resistance to ciprofloxacin and susceptibility to the other six antibiotics.

```text
1111111
```

represents resistance to all seven antibiotics. This is a terminal state in the current simulation.

The seven positions always follow the canonical antibiotic ordering defined in `data/processed/action_space.csv`.

This representation is deliberately simplified. It models resistance phenotypes rather than full bacterial genomes, minimum inhibitory concentrations, dosage, or detailed pharmacological effects.

### Actions

Each action corresponds to selecting one of the seven antibiotics.

The action space contains seven discrete actions, numbered from `0` to `6`.

| Action ID | Antibiotic     |
| --------: | -------------- |
|         0 | Ciprofloxacin  |
|         1 | Nitrofurantoin |
|         2 | Fosfomycin     |
|         3 | Trimethoprim   |
|         4 | Gentamicin     |
|         5 | Mecillinam     |
|         6 | Ceftazidime    |

The underlying Gymnasium action space remains fixed at seven actions. Under the
current objective, the feasible policy actions are the antibiotics marked
susceptible in the current state. Environments expose an action mask, but
`step()` does not itself reject a masked action; optimization policies must
honor the mask. Unrestricted policies are negative controls, not feasible
competitors.

### Observation

The decision-making model does not receive the resistance state as an arbitrary Python object. It receives an encoded observation.

The observation has 15 values:

* Seven susceptibility indicators.
* Seven values representing the last selected action in one-hot form.
* One value representing the treatment step.

Unknown susceptibility can be represented separately in the observation format. The current default environment begins with a fully susceptible state and produces known susceptibility indicators.

This structure provides the basis for future experiments involving partial observability.

### Resistance transitions

After an antibiotic action, the simulator determines whether any evidence-supported transition candidates apply to the current state and action.

The model distinguishes:

* **Cross-resistance:** Resistance to one antibiotic is associated with increased resistance to another.
* **Collateral sensitivity:** Resistance to one antibiotic is associated with increased susceptibility to another.
* **Neutral outcomes:** An observed relationship that does not change the modeled resistance state.
* **No applicable candidate:** No modeled evidence-supported transition is available for the current state and action.

The primary reference scenario, `REF_UNIFORM_SUPPORTED`, uniformly selects among applicable deduplicated candidates whenever at least one is available. This scenario is a computational assumption, not an estimate of the biological probability that resistance will emerge.

Additional sensitivity scenarios use explicit occurrence assumptions to explore how different transition-occurrence settings influence results. Those settings are not empirical biological estimates.

The environment preserves transition provenance, including scenario information, selected outcomes, and supporting evidence identifiers, to make simulated trajectories easier to inspect.



## 4. State, reward, and episode design

### Reward function

Treatment effectiveness is a feasibility constraint: if any antibiotic is
susceptible in the current simulated state, policies must select from only those
actions. The reward then minimizes resistance burden across the fixed horizon:

$$
r_t = -\frac{N_R(s_{t+1})}{7}
$$

Here, $N_R(s_{t+1})$ is the number of resistant antibiotics after the
transition, and seven is the size of the defined action space. Planning uses an
undiscounted horizon ($\gamma=1$). If all antibiotics become resistant early,
that state is treated as persisting through the remaining horizon. This is a
computational resistance-burden objective, not a clinical outcome prediction.

Unnecessary antibiotic exposure is not part of the reward: the current model
has no treatment-need, recovery, or no-treatment action. Cumulative action
count is reported separately as a limited exposure proxy.

### Episode progression

An episode represents a sequence of antibiotic treatment actions and resulting resistance states.

The default maximum episode length is eight treatment actions.

An episode terminates when:

* The maximum number of treatment actions has been reached.
* All seven antibiotics are resistant in the simulated state.

The simulator does not model clinical clearance, mortality, reinfection, adverse drug reactions, or patient recovery. Therefore, reaching the end of an episode should not be interpreted as a patient being cured.



## 5. Repository structure

The repository is organized as a monorepo so that the scientific simulation, data, decision-making code, and future product components can be developed separately.

```text
Capstone-101/
├── backend/                 # Planned API and application backend
├── frontend/                # Planned decision-support interface
├── ml/
│   ├── src/                  # Policies, value iteration, and ML components
│   ├── tests/                # ML and policy tests
│   └── requirements.txt      # Python dependencies
├── simulation/
│   ├── tests/                # Simulation and environment tests
│   ├── environment.py         # Gymnasium environment
│   ├── resistance_state.py    # Bacterial resistance state
│   ├── observation.py         # Observation structure
│   ├── transition_model.py    # Transition interface
│   ├── transition_generator.py
│   ├── transition_sampler.py
│   ├── episode.py
│   ├── reward.py
│   └── deterministic_reference.py
├── data/
│   ├── raw/                   # Original literature-derived data
│   └── processed/             # Structured evidence and model tables
├── experiments/
│   ├── iwasawa/               # Supporting trajectory analysis
│   └── simulation_inspection.ipynb
├── docs/
│   └── scientific-specification/
├── tests/                     # Cross-component tests
├── README.md
└── .venv/                     # Local Python virtual environment (not committed)
```




## 6. Setting up the repository

### Requirements

* Python 3.11
* Git
* Windows PowerShell for the commands below
* A virtual environment for Python dependencies

The current simulation and baseline work uses Python, Gymnasium, NumPy, and the other dependencies listed in `ml/requirements.txt`.

### Clone the repository

```powershell
git clone <repository-url>
cd Capstone-101
```

### Create and activate a virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the Python executable directly for the commands below:

```powershell
.\.venv\Scripts\python.exe
```

### Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r ml/requirements.txt
```

### Run the test suite

From the repository root:

```powershell
python -m pytest
```

The test suite covers the scientific simulation components, transition behavior, environment, policies, deterministic reference, value iteration, and related functionality.

The number of passing tests may change as the project evolves. Refer to the latest validation results rather than relying on a fixed count in this README.

### Run the simulation inspection notebook

Launch Jupyter:

```powershell
python -m jupyter lab
```

Open:

```text
experiments/simulation_inspection.ipynb
```

Run the notebook cells in order to inspect the simulation's behavior, including resistance states, treatment actions, transitions, and episode progression.

The notebook is intended for exploration and inspection. It is not a clinical decision-making interface.



## 7. Current scope and limitations

The current project is a research and software-engineering prototype.

It does not:

* Diagnose infections.
* Identify pathogens from clinical samples.
* Perform antimicrobial susceptibility testing.
* Recommend treatment for individual patients.
* Model antibiotic dosage, pharmacokinetics, or pharmacodynamics.
* Model clinical cure, mortality, adverse drug reactions, or reinfection.
* Claim that simulated transition probabilities represent real-world biological probabilities.
* Replace clinicians, pharmacists, or antimicrobial stewardship teams.


The simulation is intentionally simplified so that treatment strategies and resistance dynamics can be studied and compared in a controlled computational environment. This allows us to investigate whether treatment strategies that account for resistance evolution can maintain treatment effectiveness while reducing resistance emergence and preserving future antibiotic options.

The current focus is MDR *E. coli*, and the seven-antibiotic action space is an initial modeling scope rather than a comprehensive representation of all UTI treatment options.

The future decision-support interface is intended to make the outputs of this work more accessible and interpretable. Its development and validation are separate from the simulation and baseline foundations documented here.


## 8. Project direction

The longer-term goal is to build a decision-support system that helps users explore how treatment choices may influence both immediate effectiveness and future antibiotic options.

The current work establishes the scientific specification, mathematical model, reproducible simulation, and computational baselines needed to investigate that goal.

Future work will build on these foundations by training and evaluating reinforcement learning approaches, examining their performance against established computational baselines, and presenting the resulting comparisons through an accessible interface.

The central question guiding the project is:

**How can we compare sequences of antibiotic treatment actions while accounting for the possibility that those actions change future resistance and treatment options?**
