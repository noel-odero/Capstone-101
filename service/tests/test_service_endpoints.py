import json

import pytest

from ml.src.ppo_inference import DEFAULT_MANIFEST_PATH, InferenceContext
from service.tests.conftest import EXPECTED_CHECKPOINT_SHA256
from simulation.resistance_state import ANTIBIOTICS

UNSUPPORTED = {"FOSFOMYCIN"}


def assert_error(response, status, codes):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] in codes
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert "Traceback" not in response.text
    return error


def test_health_reports_real_model_readiness(client):
    response = client.get("/internal/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["model_ready"] is True
    assert body["model_id"] == "ppo_public_v2_seed_19000"
    assert body["checkpoint_sha256"] == EXPECTED_CHECKPOINT_SHA256
    assert response.headers["X-Request-ID"]


def test_model_metadata_comes_from_manifest_and_engine(client, runtime):
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))

    body = client.get("/internal/model").json()

    assert body["model_id"] == manifest["model_id"]
    assert body["checkpoint_sha256"] == runtime.engine.checkpoint_sha256 == EXPECTED_CHECKPOINT_SHA256
    assert body["manifest_checkpoint_sha256"] == manifest["checkpoint"]["sha256"].lower()
    assert body["interaction_data_sha256"] == manifest["simulator"]["interaction_data_sha256"]
    assert (body["scenario_id"], body["horizon"]) == ("REF_UNIFORM_SUPPORTED", 8)
    assert body["antibiotic_order"] == list(ANTIBIOTICS)
    assert body["observation"] == manifest["observation"]
    assert body["action_masking"] == {"rule": "susceptible_actions_only"}
    assert "unsupported_no_candidate" in body["transition_status_definitions"]
    assert all(not path.startswith(("/", "\\")) and ":" not in path for path in body["provenance_files"].values())
    assert "not clinical advice" in body["disclaimer"].lower()


def test_antibiotics_use_canonical_order_and_source_classes(client):
    body = client.get("/internal/antibiotics").json()

    assert [item["name"] for item in body["antibiotics"]] == list(ANTIBIOTICS)
    assert [item["action_id"] for item in body["antibiotics"]] == list(range(7))
    assert all(item["drug_class"] for item in body["antibiotics"])
    assert body["resistance_encoding"] == {"susceptible": 0, "resistant": 1}


def test_validate_all_susceptible_profile(client):
    body = client.post("/internal/profiles/validate", json={"resistance_profile": [0] * 7}).json()

    assert body["valid"] is True and body["is_terminal"] is False
    assert body["feasible_action_ids"] == list(range(7))
    assert body["susceptible_option_count"] == 7 and body["resistant_antibiotics"] == []
    support = {item["antibiotic"]: item["has_candidate_transition"] for item in body["feasible_actions"]}
    assert {name for name, supported in support.items() if not supported} == UNSUPPORTED


def test_validate_all_resistant_profile_is_a_valid_terminal_result(client):
    response = client.post("/internal/profiles/validate", json={"resistance_profile": [1] * 7})

    body = response.json()
    assert response.status_code == 200 and body["valid"] is True
    assert body["is_terminal"] is True and body["terminal_reason"] == "no_effective_antibiotic"
    assert body["feasible_actions"] == [] and body["feasible_action_ids"] == []
    assert body["susceptible_option_count"] == 0 and body["resistant_count"] == 7


def test_model_explorer_evidence_matches_pinned_generator_for_every_state(client, runtime, monkeypatch):
    from pathlib import Path
    from simulation.resistance_state import ResistanceState
    from simulation.transition_generator import CandidateTransitionGenerator

    pinned_path = runtime.manifest.interaction_data_path
    generator = CandidateTransitionGenerator(interactions_file=Path(pinned_path) if pinned_path else None)

    def no_policy_call(*args, **kwargs):
        pytest.fail("Inspecting model evidence must not invoke a learned policy.")

    monkeypatch.setattr(runtime.engine, "recommend", no_policy_call)
    for index in range(128):
        profile = [int(bit) for bit in f"{index:07b}"]
        response = client.post("/internal/profiles/validate", json={"resistance_profile": profile})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["interaction_data_sha256"] == runtime.manifest.interaction_data_sha256
        assert body["scenario_id"] == runtime.manifest.scenario_id
        assert len(body["transition_evidence"]) == 7
        for action in body["transition_evidence"]:
            action_id = action["action_id"]
            assert action["eligible"] == (profile[action_id] == 0)
            expected = generator.generate(ResistanceState(tuple(profile)), action_id) if action["eligible"] else ()
            assert action["candidates"] == [
                {"target_drug": item.target_drug, "outcome": item.outcome, "source_ids": list(item.source_ids)}
                for item in expected
            ]


def test_validate_mixed_profile_names_and_feasibility(client):
    body = client.post("/internal/profiles/validate", json={"resistance_profile": [1, 0, 1, 0, 0, 1, 0]}).json()

    assert body["resistant_antibiotics"] == ["CIPROFLOXACIN", "FOSFOMYCIN", "MECILLINAM"]
    assert body["susceptible_antibiotics"] == ["NITROFURANTOIN", "TRIMETHOPRIM", "GENTAMICIN", "CEFTAZIDIME"]
    assert body["feasible_action_ids"] == [1, 3, 4, 6]
    assert body["susceptible_option_count"] == 4


@pytest.mark.parametrize(
    ("payload", "codes"),
    [
        ({"resistance_profile": [0] * 6}, {"request_validation_error"}),
        ({"resistance_profile": [0] * 8}, {"request_validation_error"}),
        ({"resistance_profile": [0, 0, 2, 0, 0, 0, 0]}, {"invalid_context"}),
        ({"resistance_profile": [-1] + [0] * 6}, {"invalid_context"}),
        ({"resistance_profile": [True] + [0] * 6}, {"request_validation_error"}),
        ({"resistance_profile": [1.0] + [0] * 6}, {"request_validation_error"}),
        ({"resistance_profile": ["0"] * 7}, {"request_validation_error"}),
        ({"resistance_profile": "0000000"}, {"request_validation_error"}),
        ({"resistance_profile": None}, {"request_validation_error"}),
        ({}, {"request_validation_error"}),
        ({"resistance_profile": [0] * 7, "horizon": 3}, {"request_validation_error"}),
    ],
)
def test_validate_rejects_malformed_profiles(client, payload, codes):
    assert_error(client.post("/internal/profiles/validate", json=payload), 422, codes)


def test_recommend_matches_direct_engine_inference(client, runtime):
    profile = (1, 0, 0, 1, 0, 0, 0)
    context = InferenceContext(profile, last_action=1, treatment_step=2)
    direct = runtime.engine.recommend(context)

    response = client.post(
        "/internal/recommend", json={"resistance_profile": list(profile), "last_action": 1, "treatment_step": 2}
    )

    body = response.json()
    assert response.status_code == 200 and body["status"] == "recommended" and body["is_terminal"] is False
    assert (body["action_id"], body["antibiotic"]) == (direct.action_id, direct.antibiotic)
    assert body["feasible_action_ids"] == list(direct.feasible_action_ids)
    assert [item["antibiotic"] for item in body["feasible_actions"]] == list(direct.feasible_antibiotics)
    assert body["transition_status"] == direct.transition_status
    assert body["has_candidate_transition"] == direct.has_candidate_transition
    assert body["model_id"] == "ppo_public_v2_seed_19000" and body["checkpoint_sha256"] == EXPECTED_CHECKPOINT_SHA256
    assert (body["last_action_id"], body["last_action_antibiotic"], body["treatment_step"]) == (1, "NITROFURANTOIN", 2)
    assert "clinically effective" in body["interpretation"]


def test_recommend_reports_unsupported_transition_consistently(client):
    body = client.post(
        "/internal/recommend", json={"resistance_profile": [0] * 7, "last_action": None, "treatment_step": 0}
    ).json()

    chosen = next(item for item in body["feasible_actions"] if item["action_id"] == body["action_id"])
    assert body["has_candidate_transition"] == chosen["has_candidate_transition"]
    assert (body["transition_status"] == "unsupported_no_candidate") == (not body["has_candidate_transition"])


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"resistance_profile": [1] * 7, "last_action": None, "treatment_step": 0}, "no_effective_antibiotic"),
        ({"resistance_profile": [1] * 7, "last_action": 2, "treatment_step": 4}, "no_effective_antibiotic"),
        ({"resistance_profile": [0] * 7, "last_action": 2, "treatment_step": 8}, "maximum_horizon"),
    ],
)
def test_terminal_recommendation_is_a_normal_result_without_an_action(client, payload, reason):
    response = client.post("/internal/recommend", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert (body["status"], body["is_terminal"], body["terminal_reason"]) == ("terminal", True, reason)
    assert body["action_id"] is None and body["antibiotic"] is None
    assert body["feasible_actions"] == [] and body["transition_status"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"resistance_profile": [0] * 7, "last_action": None, "treatment_step": 1},
        {"resistance_profile": [0] * 7, "last_action": 3, "treatment_step": 0},
        {"resistance_profile": [0] * 7, "last_action": 7, "treatment_step": 1},
        {"resistance_profile": [0] * 7, "last_action": -1, "treatment_step": 1},
        {"resistance_profile": [0] * 7, "last_action": None, "treatment_step": -1},
        {"resistance_profile": [0] * 7, "last_action": 3, "treatment_step": 9},
        {"resistance_profile": [0] * 7, "last_action": 3, "treatment_step": 1.5},
        {"resistance_profile": [0] * 7, "last_action": "3", "treatment_step": 1},
        {"resistance_profile": [0] * 7, "last_action": 3},
        {"resistance_profile": [0] * 7, "treatment_step": 1},
        {"resistance_profile": [0, 0, 3, 0, 0, 0, 0], "last_action": None, "treatment_step": 0},
    ],
)
def test_recommend_rejects_invalid_contexts(client, payload):
    assert_error(client.post("/internal/recommend", json=payload), 422, {"invalid_context", "request_validation_error"})


@pytest.mark.parametrize("strategy", ["ppo", "dqn", "greedy"])
def test_simulate_returns_complete_run(client, strategy):
    response = client.post(
        "/internal/simulate",
        json={"resistance_profile": [0, 1, 0, 0, 0, 0, 0], "strategy": strategy, "environment_seed": 11, "policy_seed": 5},
    )

    body = response.json()
    assert response.status_code == 200 and body["kind"] == "simulation"
    assert body["run_id"] and body["created_at_utc"]
    expected = ("3afac9221dd29662708ba37f9a32326f389feb15efc31151706f738c0fd8c72d"
                if strategy == "dqn" else EXPECTED_CHECKPOINT_SHA256)
    assert body["provenance"]["checkpoint_sha256"] == expected
    assert body["provenance"]["scenario_id"] == "REF_UNIFORM_SUPPORTED" and body["provenance"]["horizon"] == 8
    assert body["provenance"]["interaction_data_sha256"] == "af62f389fe92b4ecddfbc1df6c967c5da9992ed928c09dd3a68673819f42591c"
    result = body["result"]
    assert result["strategy"] == strategy and result["initial_profile"] == [0, 1, 0, 0, 0, 0, 0]
    assert len(result["steps"]) == 8 and len(result["states"]) == 9
    assert result["termination_reason"] == "maximum_horizon"
    assert body["seed_configuration"]["environment_seed"] == 11
    assert body["seed_configuration"]["environment_seed_source"] == "client"
    assert set(result["metrics"]) <= set(body["metric_definitions"])


def test_simulate_labels_and_seed_semantics(client):
    ppo = client.post(
        "/internal/simulate",
        json={"resistance_profile": [0] * 7, "strategy": "ppo", "environment_seed": 3, "policy_seed": 9},
    ).json()
    greedy = client.post(
        "/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "greedy", "environment_seed": 3, "policy_seed": 9}
    ).json()

    assert ppo["result"]["display_label"] == "PPO"
    assert ppo["seed_configuration"]["policy_seed"] is None
    assert ppo["seed_configuration"]["policy_seed_source"] == "not_applicable"
    assert greedy["result"]["display_label"] == "Random Susceptible Baseline"
    assert greedy["result"]["implementation"] == "ml.src.greedy_policy.GreedyPolicy"
    assert greedy["seed_configuration"]["policy_seed"] == 9


def test_simulate_generates_and_reports_seeds_when_omitted(client):
    body = client.post("/internal/simulate", json={"resistance_profile": [0] * 7, "strategy": "greedy"}).json()

    seeds = body["seed_configuration"]
    assert seeds["environment_seed_source"] == seeds["policy_seed_source"] == "service_generated"
    assert isinstance(seeds["environment_seed"], int) and isinstance(seeds["policy_seed"], int)
    assert body["result"]["environment_seed"] == seeds["environment_seed"]


def test_simulate_all_resistant_start_is_a_terminal_run_with_no_steps(client, runtime):
    body = client.post("/internal/simulate", json={"resistance_profile": [1] * 7, "strategy": "ppo", "environment_seed": 1}).json()

    result = body["result"]
    assert result["steps"] == [] and len(result["states"]) == 1
    assert result["states"][0]["is_terminal"] is True and result["states"][0]["last_action_id"] is None
    assert result["termination_reason"] == "no_effective_antibiotic"
    assert result["metrics"]["treatment_steps"] == 0
    assert result["metrics"]["cumulative_resistance_burden"] == runtime.engine.horizon  # existing terminal adjustment of -H
    assert result["metrics"]["resistance_emergence_rate"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"resistance_profile": [0] * 7},
        {"resistance_profile": [0] * 7, "strategy": "value_iteration"},
        {"resistance_profile": [0] * 7, "strategy": "ppo", "environment_seed": -1},
        {"resistance_profile": [0] * 7, "strategy": "ppo", "environment_seed": 2**32},
        {"resistance_profile": [0] * 7, "strategy": "ppo", "environment_seed": True},
        {"resistance_profile": [0] * 7, "strategy": "greedy", "policy_seed": "1"},
        {"resistance_profile": [0] * 7, "strategy": "ppo", "horizon": 3},
        {"resistance_profile": [0] * 7, "strategy": "ppo", "scenario_id": "SENSITIVITY_Q_050"},
        {"resistance_profile": [0, 3, 0, 0, 0, 0, 0], "strategy": "ppo"},
    ],
)
def test_simulate_rejects_invalid_requests_and_fixed_settings(client, payload):
    assert_error(client.post("/internal/simulate", json=payload), 422, {"request_validation_error", "invalid_context"})


def test_compare_returns_all_three_complete_strategy_results(client):
    response = client.post(
        "/internal/compare", json={"resistance_profile": [0, 0, 1, 0, 0, 0, 0], "environment_seed": 21, "policy_seed": 8}
    )

    body = response.json()
    assert response.status_code == 200 and body["kind"] == "comparison"
    for key, label in (("ppo", "PPO"), ("dqn", "DQN"), ("greedy", "Random Susceptible Baseline")):
        result = body[key]
        assert result["strategy"] == key and result["display_label"] == label
        if key != "greedy":
            assert result["model"]["model_id"] == ("ppo_public_v2_seed_19000" if key == "ppo" else "dqn_public_v2_seed_15000")
        assert result["initial_profile"] == [0, 0, 1, 0, 0, 0, 0]
        assert len(result["steps"]) == 8 and len(result["states"]) == 9
        assert result["environment_seed"] == 21
    assert body["ppo"]["policy_seed"] is None and body["greedy"]["policy_seed"] == 8
    assert "identical transition outcomes" in body["pairing_semantics"]
    assert "does not establish a superior strategy" in body["single_run_caveat"]
    assert "winner" not in body


def test_compare_validates_input(client):
    assert_error(client.post("/internal/compare", json={"resistance_profile": [0] * 6}), 422, {"request_validation_error"})
    assert_error(client.post("/internal/compare", json={"resistance_profile": [0, 0, 0, 0, 0, 0, 5]}), 422, {"invalid_context"})


def test_unknown_route_uses_the_error_format(client):
    assert_error(client.get("/internal/nope"), 404, {"http_error"})
