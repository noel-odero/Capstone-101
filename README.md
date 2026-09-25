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
ml/           Machine learning, simulation and experiments
backend/      ASP.NET Core API
frontend/     React frontend
docs/         Project and technical documentation
experiments/  Experiment configurations and results