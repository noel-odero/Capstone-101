"""Regenerates the Python service responses used as fixtures by the .NET client tests.

Run from the repository root with the project's Python environment:
    .\.venv\Scripts\python.exe -B backend/tests/Amr.UnitTests/Fixtures/generate_python_fixtures.py

Every file is the real response of the service, produced in process. Nothing outside this folder is written.
"""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from service import rollout  # noqa: E402
from service.main import create_app  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "python"
PROFILE = [0, 1, 0, 0, 0, 0, 0]


def save(name: str, response) -> None:
    (OUTPUT / f"{name}.json").write_text(json.dumps(response.json(), indent=2) + "\n", encoding="utf-8")
    print(f"{name}: HTTP {response.status_code}")


def healthy_fixtures() -> None:
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        save("health_200", client.get("/internal/health"))
        save("model_200", client.get("/internal/model"))
        save("antibiotics_200", client.get("/internal/antibiotics"))
        save("validate_200_open", client.post("/internal/profiles/validate", json={"resistance_profile": [1, 0, 0, 1, 0, 0, 0]}))
        save("validate_200_terminal", client.post("/internal/profiles/validate", json={"resistance_profile": [1] * 7}))
        save("validate_422_invalid_context", client.post("/internal/profiles/validate", json={"resistance_profile": [0, 2, 0, 0, 0, 0, 0]}))
        save("validate_422_request_validation", client.post("/internal/profiles/validate", json={"resistance_profile": [0] * 6}))
        save("simulate_200_ppo", client.post("/internal/simulate", json={"resistance_profile": PROFILE, "strategy": "ppo", "environment_seed": 100001}))
        save("simulate_200_baseline", client.post("/internal/simulate", json={"resistance_profile": PROFILE, "strategy": "greedy", "environment_seed": 100001, "policy_seed": 900001}))
        save("simulate_200_terminal", client.post("/internal/simulate", json={"resistance_profile": [1] * 7, "strategy": "ppo", "environment_seed": 1}))
        save("compare_200", client.post("/internal/compare", json={"resistance_profile": PROFILE, "environment_seed": 100001, "policy_seed": 900001}))

        original = rollout._evaluate
        try:
            def tampered(runtime, strategy, profile, environment_seed, policy_seed):
                if strategy == "greedy":
                    profile = (1,) + tuple(profile[1:])
                return original(runtime, strategy, profile, environment_seed, policy_seed)

            rollout._evaluate = tampered
            save("compare_500_contract_violation", client.post("/internal/compare", json={"resistance_profile": PROFILE, "environment_seed": 1, "policy_seed": 1}))
        finally:
            rollout._evaluate = original

        original_simulate = rollout.simulate
        try:
            def broken(*args, **kwargs):
                raise RuntimeError("internal detail that must never reach clients")

            rollout.simulate = broken
            save("simulate_500_internal_error", client.post("/internal/simulate", json={"resistance_profile": PROFILE, "strategy": "ppo"}))
        finally:
            rollout.simulate = original_simulate


def unavailable_model_fixtures() -> None:
    manifest = json.loads((ROOT / "ml" / "frozen_ppo_manifest.json").read_text(encoding="utf-8"))
    manifest["checkpoint"]["sha256"] = "0" * 64
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with TestClient(create_app(path), raise_server_exceptions=False) as client:
            save("health_503_model_unavailable", client.get("/internal/health"))
            save("model_503_checkpoint_integrity_failure", client.get("/internal/model"))


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    healthy_fixtures()
    unavailable_model_fixtures()
