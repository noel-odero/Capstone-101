# AMR Stewardship System

An AI-based decision support system for antibiotic stewardship in multidrug-resistant
*Escherichia coli* urinary tract infections.

## Project Overview

This project explores the use of reinforcement learning to support sequential
antibiotic treatment strategy evaluation under antimicrobial resistance dynamics.

The system will simulate antibiotic treatment decisions, resistance evolution,
and future treatment options, allowing different treatment strategies to be
compared over multiple steps.

The project is being developed as a Bachelor of Science in Software Engineering
capstone project at African Leadership University.

## Scope

The system is a research and decision-support prototype. It is not intended to:

- Diagnose infections
- Identify pathogens
- Perform antimicrobial susceptibility testing
- Prescribe antibiotics autonomously
- Recommend antibiotic dosage
- Replace clinical judgement
- Integrate directly with electronic health records
- Provide regulatory or clinical trial evidence

## Planned Technology Stack

- Python
- Gymnasium
- Stable-Baselines3
- NumPy / Pandas / SciPy
- ASP.NET Core Web API
- React + TypeScript
- PostgreSQL
- Docker

## Project Structure

```text
simulation/   Resistance simulation and Gymnasium environment
ml/           Machine-learning environment and future policy code
data/         Raw sources and processed evidence/configuration
experiments/  Simulation inspection and exploratory analyses
docs/         Scientific specifications and research notes
tests/        Simulation and evidence-pipeline tests
backend/      ASP.NET Core API placeholder
frontend/     React frontend placeholder
```

`REF_UNIFORM_SUPPORTED` is a computational reference scenario: it uniformly
selects among applicable, deduplicated candidates, and selects a candidate
whenever at least one is applicable. It is not an empirical estimate of the
chance of resistance change. Named sensitivity scenarios use illustrative
transition-occurrence assumptions (`q = 0.25`, `0.50`, and `0.75`); these are
not biological probabilities.

Python 3.11.9
1. Create and activate `.venv` with Python 3.11.
2. Install dependencies with `pip install -r ml/requirements.txt`.
3. Run the test suite from the repository root with `python -m pytest`.
4. Check installed ML packages with `python ml/environment_check.py`.

Sprint 4 baselines and evaluation infrastructure, PPO training, backend, and
frontend implementations are not yet present.