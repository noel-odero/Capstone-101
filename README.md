# StewardLab — Antimicrobial Resistance Decision Support

### Exploring how reinforcement learning can help preserve future antibiotic treatment options.

Antimicrobial resistance is one of the challenges facing modern healthcare. What makes it particularly interesting is that selecting an antibiotic is not always just about what works today. The decisions made now can influence how resistance develops and which antibiotics remain available in the future.

This is the problem I set out to explore through my capstone project.

**StewardLab** is a web-based research platform I developed to investigate how reinforcement learning can support sequential antibiotic-selection decisions. It focuses on *Escherichia coli* (*E. coli*) and uses a computational resistance model to examine how different antibiotic-selection strategies influence resistance over time.

The platform compares two reinforcement-learning algorithms, **Proximal Policy Optimization (PPO)** and **Deep Q-Network (DQN)**, against a baseline that randomly selects from currently susceptible antibiotics.

Rather than simply presenting model performance in a notebook, I wanted to create an environment where researchers could interact with the work. With StewardLab, researchers can record resistance profiles, evaluate different strategies, inspect antibiotic sequences and resistance transitions, and revisit previous analyses to identify patterns across experiments.

The platform also includes **Analysis Insights**, which supports comparisons across saved evaluations, and **Model Explorer**, which allows researchers to investigate the 128 possible resistance states represented by the seven-antibiotic model and understand where transition evidence is available or missing.

StewardLab is currently a research prototype. Its findings are based on a computational model and should not be interpreted as clinical treatment recommendations. The interactive 3D urinary-tract illustration is included to support the visual experience; it does not represent measured bacterial clearance or biological evolution. A scientifically grounded evolution visualization remains an area for future development.

---

## Project Demonstration and Technical Report

The following materials provide a more detailed explanation of the work, including the original research objectives, implementation decisions, experimental results, testing, and current limitations.

**[Watch the Product Walkthrough](https://youtu.be/2YR4e5tgVp4)**

The walkthrough demonstrates the main features of StewardLab, explains how the frontend communicates with the backend and scientific service, and shows how researchers can configure and investigate evaluations.

**[Read the Final Technical Report](https://docs.google.com/document/d/12dkIiZMbPTCwuP494iQ0ZfUVn4C5nMtgvuq__3-Om0s/edit?usp=sharing)**

The report covers alignment with the original project proposal, implemented functionalities, system architecture, object-oriented programming principles, algorithm development, testing strategies and results, performance measurements, and areas requiring further improvement.

---

## How the Application Works

StewardLab is designed around a straightforward research workflow.

A researcher begins by recording an initial resistance profile. Each profile describes susceptibility or resistance to seven antibiotics using a binary representation, where `0` means susceptible and `1` means resistant within the model.

The researcher can save the profile as a labeled sample and evaluate it immediately or return to it later.

When an analysis is started, StewardLab evaluates the frozen PPO and DQN policies alongside the random susceptible-action baseline. The scientific environment records the antibiotics selected, the resulting resistance states, and the performance metrics across an eight-step decision horizon.

Once the analysis is complete, the results are saved so the researcher can inspect them without rerunning the models.

The application also supports research beyond individual evaluations. Through Analysis History and Analysis Insights, researchers can revisit their work, compare outcomes across different starting profiles, and investigate situations where one strategy performed differently from another.

This is an important part of what I wanted to achieve: a platform that supports an ongoing research process rather than a one-time model demonstration.

## Technology Stack and System Architecture

StewardLab combines a React frontend, an ASP.NET Core backend, a Python scientific service, and PostgreSQL for persistent storage.

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript, Vite | Research workspace, user interactions, charts, and 3D illustration |
| Backend | C#, ASP.NET Core, .NET 10 | Authentication, validation, application workflows, and API endpoints |
| Scientific service | Python 3.11, FastAPI | Loads frozen models and performs scientific evaluations |
| Machine learning | PPO, DQN, Stable-Baselines3 | Training, inference, and evaluation of antibiotic-selection policies |
| Database | PostgreSQL 17, Entity Framework Core | Stores accounts, samples, analyses, and research records |
| Development environment | Node.js 22.12+, Docker Desktop | Frontend tooling and local database infrastructure |

The application follows this general architecture:

```text
Researcher
    |
    v
React + TypeScript Frontend
    |
    v
ASP.NET Core REST API
    |
    +--------------------> PostgreSQL
    |                      (Saved research data)
    |
    v
Python FastAPI Service
    |
    v
Frozen PPO and DQN Models
    |
    v
Resistance Environment
```

The browser communicates with the ASP.NET Core API, which handles application-level operations and calls the Python service whenever scientific computation is required.

The Python service loads the trained models locally, so external model-hosting services are not required.

I chose this separation to keep the scientific logic independent from the interface and database implementation, making the application easier to test, maintain, and extend.

## Repository Structure

The repository is organized according to the responsibilities of the different components.

| Directory | Contents |
|---|---|
| `frontend/` | React application, research pages, charts, and illustrative 3D view |
| `backend/` | ASP.NET Core API, authentication, application services, and PostgreSQL persistence |
| `service/` | Internal FastAPI service for scientific evaluation |
| `simulation/` | Resistance states, action masks, transitions, and reward calculations |
| `ml/` | PPO and DQN training, inference, and evaluation |
| `experiments/` | Scientific data integration, benchmark configurations, audits, and model selection |
| `data/` | Processed research inputs, source extracts, and derivation inputs |
| `artifacts/frozen/` | Frozen policy checkpoints, manifests, and checksums |
| `docs/` | API documentation, scientific assumptions, and research methodology |

Keeping these components separate was particularly important because the project involves both software engineering and scientific experimentation.

---

## Running StewardLab Locally

The following instructions explain how to set up and run the application on a Windows development environment using PowerShell.

### Prerequisites

Before starting, make sure the following are installed:

- **Python 3.11**
- **Node.js 22.12 or later**, including npm
- **.NET 10 SDK**, matching `backend/global.json`
- **Docker Desktop**, with the Docker engine running
- **Git**, to clone the repository

The documented setup uses Windows and PowerShell. Other operating systems may require adjustments to virtual-environment paths, shell commands, and Docker configuration.

A development machine capable of running Docker, PostgreSQL, the Python scientific service, the .NET API, and the React development server is required. The local performance measurements were collected on Windows 11 using an AMD Ryzen 5 PRO 8540U processor and approximately 32 GB RAM. This is the tested environment, not a minimum hardware requirement.

### Step 1 — Clone the Repository

Start by cloning the project and navigating into its root directory.

```powershell
git clone https://github.com/noel-odero/Capstone-101.git
cd Capstone-101
```

All commands in the following setup instructions should be run from the repository root unless otherwise stated.

### Step 2 — Install Project Dependencies

Create a Python virtual environment and install the scientific and service dependencies.

```powershell
py -3.11 -m venv .venv

.\.venv\Scripts\python.exe -m pip install `
  -r ml/requirements-lock.txt `
  -r service/requirements-dev.txt
```

For an inference-only Python environment, `service/requirements.txt` can be used instead.

Next, restore the .NET dependencies and install the frontend packages.

```powershell
dotnet restore backend\Amr.sln --locked-mode

npm --prefix frontend ci
```

On Windows, it is recommended to use the Python executable inside `.venv`, since the plain `python` command may resolve to the Microsoft Store alias.

### Step 3 — Set Up PostgreSQL

StewardLab uses PostgreSQL to store researcher accounts, samples, evaluations, and saved results.

For local development, the database runs inside a Docker container named `amr-test-pg`, using the `postgres:17-alpine` image and host port `55432`.

If this is your first time setting up the project, create the container with a local password:

```powershell
$pgPassword = Read-Host 'Local PostgreSQL password'

docker run -d --name amr-test-pg `
  -e "POSTGRES_PASSWORD=$pgPassword" `
  -p 127.0.0.1:55432:5432 `
  postgres:17-alpine

$admin = "Host=127.0.0.1;Port=55432;Username=postgres;Password=$pgPassword;Database=postgres"

[Environment]::SetEnvironmentVariable(
  'AMR_TEST_POSTGRES',
  $admin,
  'User'
)

Remove-Variable pgPassword
```

This creates the local PostgreSQL container and stores its administrative connection string in a user-level environment variable.

If the container already exists, use its existing credentials and connection string rather than creating another one.

Credentials and local environment files should not be committed to Git.

### Step 4 — Apply Database Migrations

Before starting the API for the first time, the database schema must be created using Entity Framework Core migrations.

Open a PowerShell terminal and run:

```powershell
cd backend

$admin = [Environment]::GetEnvironmentVariable(
  'AMR_TEST_POSTGRES',
  'User'
)

$env:ConnectionStrings__Amr = [regex]::Replace(
  $admin,
  'Database=[^;]*',
  'Database=amr_frontend_dev'
)

dotnet tool restore

dotnet tool run dotnet-ef database update `
  --project src/Amr.Infrastructure `
  --startup-project src/Amr.Api
```

After completing the migrations, return to the repository root:

```powershell
cd ..
```

Migrations should also be applied after pulling repository changes that introduce database schema updates.

### Step 5 — Start the Application

StewardLab consists of multiple services, so each should be started in its own terminal.

**Start PostgreSQL**

Make sure Docker Desktop is running, then execute:

```powershell
docker start amr-test-pg
```

If the container is already running, Docker may report that it is already started.

**Start the Python scientific service**

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn `
  service.main:app `
  --host 127.0.0.1 `
  --port 8000 `
  --workers 1
```

This starts the internal scientific service responsible for loading the frozen models and evaluating antibiotic-selection strategies.

**Start the ASP.NET Core API**

Open another PowerShell terminal at the repository root:

```powershell
$admin = [Environment]::GetEnvironmentVariable(
  'AMR_TEST_POSTGRES',
  'User'
)

$env:ConnectionStrings__Amr = [regex]::Replace(
  $admin,
  'Database=[^;]*',
  'Database=amr_frontend_dev'
)

$env:ASPNETCORE_ENVIRONMENT = 'Development'
$env:ASPNETCORE_URLS = 'http://127.0.0.1:5080'

dotnet run --project backend\src\Amr.Api --no-launch-profile
```

The API requires a valid database connection string and will not start without `ConnectionStrings__Amr`.

**Start the frontend**

Finally, open another terminal:

```powershell
cd frontend

npm run dev
```

Once the development server is running, open:

**http://localhost:5173**

You can now create an account, sign in, record samples, and begin evaluating antibiotic-selection strategies.

The development command also retains the larger HTTP header limit needed when localhost cookies accumulate.

### Step 6 — Verify That Everything Is Running

To confirm that the backend is responding, run:

```powershell
Invoke-RestMethod http://127.0.0.1:5080/api/v1/health
```

You can also check the frontend's proxied authentication-session endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:5173/api/v1/auth/session
```

The session endpoint may report an unauthenticated state before sign-in; this is expected.

Application readiness depends on the Python scientific service, verified model artifacts, and an up-to-date database schema.

If the health endpoint reports `database_migrations_pending`, return to Step 4 and apply the outstanding migrations.

To stop the application, use `Ctrl+C` in each service terminal. PostgreSQL can remain running for future development sessions.

---

## Testing and Validation

Testing has been an important part of developing StewardLab because the application needs to be reliable at both the software and scientific levels.

The project includes tests for resistance-state handling, reward calculations, transition logic, action masking, model inference, backend application services, database persistence, API behavior, and frontend interactions.

The latest completed local verification recorded **1,188 passing tests** across the Python scientific suite, frontend tests, .NET unit tests, .NET integration tests, and live-service integration tests.

To run the main scientific and frontend checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider

.\.venv\Scripts\python.exe -B -m ml.src.artifact_checksums

npm --prefix frontend run build

npm --prefix frontend run lint

npm --prefix frontend test
```

The .NET unit tests, PostgreSQL integration tests, and live-service tests are documented separately in the API documentation.

Beyond automated testing, I also evaluated different resistance profiles, including fully susceptible, partially resistant, and fully resistant conditions.

For example, a profile of `1111111` represents a terminal state in which no antibiotic remains eligible. The scientific service handles this without attempting another action.

Invalid inputs, such as a profile containing fewer than seven values or a nonbinary value, are rejected with validation errors.

Local performance testing also measured the scientific comparison endpoint. For the tested nonterminal profiles, median warm-request times were approximately 28–30 milliseconds. These measurements cover the internal scientific service and should not be interpreted as full browser-to-database response times.

Further browser compatibility, hardware performance, and 3D frame-rate testing remain outstanding.

---

## Research Assumptions and Limitations

StewardLab was developed to investigate a research question, and its results should always be understood within the assumptions of the computational environment.

The model represents resistance using seven binary indicators and evaluates decisions across a fixed eight-step horizon. Although this makes the problem manageable for reinforcement learning, it does not capture the full complexity of bacterial evolution or clinical treatment.

The transition evidence is also incomplete. Some eligible antibiotic actions have no applicable transition candidates. When this occurs, the environment records an unsupported transition rather than treating the unchanged resistance state as evidence of treatment success.

The environment does not currently account for bacterial population sizes, antibiotic dosage, patient recovery, or other clinical factors that would be necessary for real-world prescribing decisions.

For this reason, the results should be interpreted as comparisons of algorithms under defined research assumptions, not evidence that a particular antibiotic sequence should be used in clinical practice.

These limitations are documented so that researchers can understand what the platform can and cannot currently establish.

---

## Further Documentation

For anyone interested in understanding the implementation or extending the project, I have included additional technical and scientific documentation.

- **[API and Architecture](docs/api.md)** explains the backend structure, database integration, API contracts, and testing.
- **[Scientific Model](docs/scientific-model.md)** describes the resistance environment, transition assumptions, reward function, and evaluation metrics.
- **[Research and Retraining](docs/research.md)** documents scientific data provenance, experimental evaluation, benchmark configuration, and frozen-model selection.

These documents provide the technical detail behind the functionality presented in the web application.

---

## Conclusion

StewardLab began as an investigation into whether reinforcement learning could help preserve future antibiotic options by considering the longer-term effects of antibiotic-selection decisions.

Over the course of development, it has grown into a research platform that brings together reinforcement learning, scientific modeling, backend engineering, persistent data management, and interactive analysis.

The platform currently allows researchers to compare PPO, DQN, and a random susceptible-action baseline, inspect how resistance states change, organize their experiments, and return to previous findings.

There is still work to be done, particularly in strengthening the scientific evidence, improving validation, and extending the platform's research capabilities.

However, the current implementation provides a foundation for investigating sequential antibiotic decisions in a way that is transparent, reproducible, and open to further research.

**The goal of StewardLab is not simply to show which algorithm performs better, but to make it possible to understand why, under what conditions, and with what limitations.**