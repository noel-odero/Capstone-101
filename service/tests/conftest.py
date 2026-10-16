"""Shared fixtures: the real frozen model is loaded once per test session; protected files are hashed before and after."""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from ml.src.ppo_inference import DEFAULT_MANIFEST_PATH, REPO_ROOT, load_manifest
from service.main import create_app

EXPECTED_CHECKPOINT_SHA256 = "d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093"


def _protected_files() -> list[Path]:
    manifest = load_manifest()
    return [
        manifest.checkpoint_path,
        manifest.training_config_path,
        DEFAULT_MANIFEST_PATH,
        *sorted((REPO_ROOT / "data" / "processed").glob("*.csv")),
    ]


def _hashes() -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in _protected_files()}


@pytest.fixture(scope="session", autouse=True)
def protected_files_unchanged():
    before = _hashes()
    yield before
    assert _hashes() == before, "A test modified the frozen checkpoint, manifest or transition data."


@pytest.fixture(scope="session")
def client():
    if not load_manifest().checkpoint_path.is_file():
        pytest.skip("Frozen seed 12000 checkpoint is not present.")
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def runtime(client):
    state = client.app.state.runtime_state
    assert state.runtime is not None, state.error_message
    return state.runtime
