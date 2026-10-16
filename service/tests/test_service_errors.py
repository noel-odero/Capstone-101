import dataclasses
import json

from fastapi.testclient import TestClient
import pytest

from ml.src.ppo_inference import (
    DEFAULT_MANIFEST_PATH,
    REPO_ROOT,
    CheckpointIntegrityError,
    ContractMismatchError,
    EmptyActionMaskError,
    InferenceError,
    InfeasibleActionError,
    InvalidContextError,
)
from service import rollout
from service.errors import ModelNotReadyError, ServiceError, to_service_error
from service.main import create_app
from simulation.resistance_state import ANTIBIOTICS

GOOD_BODY = {"resistance_profile": [0] * 7, "last_action": None, "treatment_step": 0}
SECRET = r"C:\secret\machine\path.csv"


def manifest_with(tmp_path, **overrides):
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    for dotted, value in overrides.items():
        section, _, key = dotted.partition(".")
        if key:
            manifest[section][key] = value
        else:
            manifest[section] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def assert_safe(response):
    assert "Traceback" not in response.text
    assert str(REPO_ROOT) not in response.text and SECRET not in response.text
    assert "secret" not in response.text.lower()


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InvalidContextError("bad context"), 422, "invalid_context"),
        (CheckpointIntegrityError(f"Checkpoint file not found: {SECRET}"), 503, "checkpoint_integrity_failure"),
        (ContractMismatchError(f"differs {SECRET}"), 503, "model_contract_mismatch"),
        (FileNotFoundError(SECRET), 503, "model_or_data_unavailable"),
        (EmptyActionMaskError("none"), 500, "empty_action_mask"),
        (InfeasibleActionError("outside"), 500, "infeasible_policy_action"),
        (InferenceError(SECRET), 500, "inference_failure"),
        (RuntimeError(SECRET), 500, "internal_error"),
    ],
)
def test_exceptions_map_to_documented_safe_errors(error, status, code):
    mapped = to_service_error(error)

    assert (mapped.status_code, mapped.code) == (status, code)
    assert SECRET not in mapped.message


def test_service_errors_pass_through_unchanged():
    error = ModelNotReadyError()
    assert to_service_error(error) is error and isinstance(error, ServiceError)


def test_service_is_not_ready_until_startup_runs_and_never_calls_the_model():
    client = TestClient(create_app(), raise_server_exceptions=False)  # no lifespan: no model loaded

    health = client.get("/internal/health")
    model = client.post("/internal/recommend", json=GOOD_BODY)

    assert health.status_code == 503
    assert health.json()["status"] == "unavailable" and health.json()["model_ready"] is False
    assert health.json()["error_code"] == "model_not_loaded"
    assert model.status_code == 503 and model.json()["error"]["code"] == "model_not_loaded"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"checkpoint": {"path": "artifacts/ppo/ppo_seed_12000/final_model.zip", "sha256": "0" * 64}}, "checkpoint_integrity_failure"),
        ({"checkpoint": {"path": "artifacts/ppo/does_not_exist/final_model.zip", "sha256": "0" * 64}}, "checkpoint_integrity_failure"),
        ({"simulator.interaction_data_sha256": "0" * 64}, "model_contract_mismatch"),
        ({"simulator.horizon": 9}, "model_contract_mismatch"),
        ({"simulator.scenario_id": "SENSITIVITY_Q_050"}, "model_contract_mismatch"),
        ({"simulator.action_names": list(reversed(ANTIBIOTICS))}, "model_contract_mismatch"),
    ],
)
def test_integrity_and_contract_failures_make_the_service_unready(tmp_path, overrides, code):
    path = manifest_with(tmp_path, **overrides)

    with TestClient(create_app(path), raise_server_exceptions=False) as client:
        health = client.get("/internal/health")
        responses = [
            client.get("/internal/model"),
            client.get("/internal/antibiotics"),
            client.post("/internal/profiles/validate", json={"resistance_profile": [0] * 7}),
            client.post("/internal/recommend", json=GOOD_BODY),
            client.post("/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "ppo"}),
            client.post("/internal/compare", json={"resistance_profile": [0] * 7}),
        ]

    assert health.status_code == 503
    assert health.json()["model_ready"] is False and health.json()["status"] == "unavailable"
    assert health.json()["error_code"] == code and health.json()["checkpoint_sha256"] is None
    assert_safe(health)
    for response in responses:
        assert response.status_code == 503
        assert response.json()["error"]["code"] == code
        assert_safe(response)


def test_missing_manifest_is_reported_as_unavailable_without_leaking_the_path(tmp_path):
    with TestClient(create_app(tmp_path / "missing.json"), raise_server_exceptions=False) as client:
        response = client.get("/internal/health")

    assert response.status_code == 503 and response.json()["error_code"] == "model_or_data_unavailable"
    assert str(tmp_path) not in response.text


def test_unexpected_failure_returns_safe_500_with_correlating_request_id(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError(f"secret {SECRET}")

    monkeypatch.setattr(rollout, "simulate", boom)

    response = client.post("/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "ppo"})

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error" and error["request_id"] == response.headers["X-Request-ID"]
    assert_safe(response)


def test_missing_data_file_during_a_run_is_503_without_path(client, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError(SECRET)

    monkeypatch.setattr(rollout, "compare", missing)

    response = client.post("/internal/compare", json={"resistance_profile": [0] * 7})

    assert response.status_code == 503 and response.json()["error"]["code"] == "model_or_data_unavailable"
    assert_safe(response)


@pytest.mark.parametrize(
    ("error", "code"),
    [(EmptyActionMaskError("none"), "empty_action_mask"), (InfeasibleActionError("outside"), "infeasible_policy_action")],
)
def test_engine_invariant_failures_are_errors_not_substitutions(client, runtime, monkeypatch, error, code):
    def fail(context):
        raise error

    monkeypatch.setattr(runtime.engine, "recommend", fail)

    recommend = client.post("/internal/recommend", json=GOOD_BODY)
    simulate = client.post("/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "ppo", "environment_seed": 1})

    for response in (recommend, simulate):
        assert response.status_code == 500 and response.json()["error"]["code"] == code
        assert "steps" not in response.text and "action_id" not in response.json()


def test_live_transition_data_drift_is_rejected_not_simulated(client, runtime):
    original = runtime.manifest
    object.__setattr__(runtime, "manifest", dataclasses.replace(original, interaction_data_sha256="0" * 64))
    try:
        response = client.post(
            "/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "greedy", "environment_seed": 1}
        )
    finally:
        object.__setattr__(runtime, "manifest", original)

    assert response.status_code == 503 and response.json()["error"]["code"] == "model_contract_mismatch"
    assert "steps" not in response.text
