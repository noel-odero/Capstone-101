import dataclasses
from itertools import product
from types import SimpleNamespace

import pytest

from service import rollout
from service.errors import ComparisonContractError
from simulation.resistance_state import ResistanceState
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_sampler import TransitionSampler

ALL_SUSCEPTIBLE = (0,) * 7
SAMPLE_PROFILES = [
    profile for index, profile in enumerate(product((0, 1), repeat=7)) if index % 4 == 0 and not all(profile)
]


def build(runtime, profile=ALL_SUSCEPTIBLE, environment_seed=100001, policy_seed=900001):
    ppo_run, ppo_episode, ppo_metrics = rollout._evaluate(runtime, "ppo", profile, environment_seed, policy_seed)
    greedy_run, greedy_episode, greedy_metrics = rollout._evaluate(runtime, "greedy", profile, environment_seed, policy_seed)
    ppo = rollout._strategy_result(runtime, "ppo", ppo_episode, ppo_metrics, environment_seed, None)
    greedy = rollout._strategy_result(runtime, "greedy", greedy_episode, greedy_metrics, environment_seed, policy_seed)
    return ppo_run, greedy_run, ppo, greedy


def contract(runtime, built, profile=ALL_SUSCEPTIBLE, environment_seed=100001, runtime_override=None):
    ppo_run, greedy_run, ppo, greedy = built
    return rollout._comparison_contract(runtime_override or runtime, profile, environment_seed, ppo_run, greedy_run, ppo, greedy)


def with_config(run, **changes):
    return dataclasses.replace(run, environment_configuration={**run.environment_configuration, **changes})


def test_comparison_reports_the_verified_shared_configuration(client, runtime):
    body = client.post(
        "/internal/compare", json={"resistance_profile": [0, 1, 0, 0, 0, 0, 0], "environment_seed": 77, "policy_seed": 5}
    ).json()

    contract_ = body["comparison_contract"]
    assert contract_["verified"] is True
    assert contract_["checks_passed"] == [
        "initial_profile", "environment_seed", "scenario_id", "horizon", "interaction_data_sha256",
        "reward_specification", "action_mask_configuration", "transition_seed_schedule",
    ]
    shared = contract_["shared"]
    assert shared["initial_profile"] == body["ppo"]["initial_profile"] == body["dqn"]["initial_profile"] == body["greedy"]["initial_profile"] == [0, 1, 0, 0, 0, 0, 0]
    assert shared["environment_seed"] == body["ppo"]["environment_seed"] == body["dqn"]["environment_seed"] == body["greedy"]["environment_seed"] == 77
    assert shared["scenario_id"] == body["provenance"]["scenario_id"] == runtime.manifest.scenario_id
    assert shared["horizon"] == body["provenance"]["horizon"] == runtime.engine.horizon
    assert shared["interaction_data_sha256"] == body["provenance"]["interaction_data_sha256"] == runtime.manifest.interaction_data_sha256
    assert shared["reward_specification"] == body["provenance"]["reward_specification"] == runtime.config.reward_configuration
    assert shared["action_mask_configuration"] == runtime.config.action_mask_configuration
    assert contract_["transition_seed_schedule"]["shared_by_step_index"] is True
    assert contract_["transition_seed_schedule"]["steps_compared"] == 8


def test_contract_states_that_seeds_do_not_guarantee_identical_outcomes(client):
    body = client.post("/internal/compare", json={"resistance_profile": [0] * 7, "environment_seed": 3}).json()

    assert body["comparison_contract"]["transition_outcomes_guaranteed_identical"] is False
    assert "do not guarantee identical transition outcomes" in body["pairing_semantics"]
    assert "do not make the outcomes equal" in body["comparison_contract"]["transition_seed_schedule"]["meaning"]


def test_valid_pair_passes_and_reports_observed_divergence(runtime):
    result = contract(runtime, build(runtime))

    assert result["verified"] is True
    observed = result["observed"]
    assert observed["steps_compared"] == 8 and 0 <= observed["steps_with_same_action"] <= 8
    assert observed["trajectories_identical"] is (observed["first_divergent_step"] is None)


@pytest.mark.parametrize(
    "changes",
    [
        {"scenario_id": "SENSITIVITY_Q_050"},
        {"horizon": 9},
        {"interaction_data_sha256": "0" * 64},
        {"reward_specification": {"objective": "other", "normalization": 7, "terminal_convention": "x"}},
        {"action_mask_configuration": {"enabled": False, "rule": "none"}},
    ],
)
def test_baseline_run_with_a_different_configuration_is_rejected(runtime, changes):
    ppo_run, greedy_run, ppo, greedy = build(runtime)

    with pytest.raises(ComparisonContractError):
        contract(runtime, (ppo_run, with_config(greedy_run, **changes), ppo, greedy))


@pytest.mark.parametrize(
    "changes",
    [
        {"interaction_data_sha256": "0" * 64},
        {"action_mask_configuration": {"enabled": False, "rule": "none"}},
    ],
)
def test_both_runs_differing_from_the_pinned_model_are_rejected_by_explicit_checks(runtime, changes):
    ppo_run, greedy_run, ppo, greedy = build(runtime)

    with pytest.raises(ComparisonContractError) as error:
        contract(runtime, (with_config(ppo_run, **changes), with_config(greedy_run, **changes), ppo, greedy))

    assert error.value.details == [{"check": next(iter(changes))}]


def test_requested_profile_and_seed_must_match_what_was_run(runtime):
    built = build(runtime)

    with pytest.raises(ComparisonContractError) as profile_error:
        contract(runtime, built, profile=(1,) + (0,) * 6)
    with pytest.raises(ComparisonContractError) as seed_error:
        contract(runtime, built, environment_seed=100002)

    assert profile_error.value.details == [{"check": "initial_profile"}]
    assert seed_error.value.details == [{"check": "environment_seed"}]


def test_pinned_scenario_horizon_and_reward_are_enforced(runtime):
    built = build(runtime)
    horizon = SimpleNamespace(config=runtime.config, engine=SimpleNamespace(horizon=9), manifest=runtime.manifest)
    scenario = SimpleNamespace(
        config=runtime.config,
        engine=runtime.engine,
        manifest=dataclasses.replace(runtime.manifest, scenario_id="SENSITIVITY_Q_050"),
    )
    reward = SimpleNamespace(
        config=SimpleNamespace(
            reward_configuration={"objective": "other"}, action_mask_configuration=runtime.config.action_mask_configuration
        ),
        engine=runtime.engine,
        manifest=runtime.manifest,
    )

    for override, check in ((scenario, "scenario_id"), (horizon, "horizon"), (reward, "reward_specification")):
        with pytest.raises(ComparisonContractError) as error:
            contract(runtime, built, runtime_override=override)
        assert error.value.details == [{"check": check}]


def test_diverging_transition_seed_schedules_are_rejected(runtime):
    ppo_run, greedy_run, ppo, greedy = build(runtime)
    steps = [dict(step) for step in ppo["steps"]]
    steps[0]["transition_seed"] += 1

    with pytest.raises(ComparisonContractError) as error:
        contract(runtime, (ppo_run, greedy_run, {**ppo, "steps": steps}, greedy))

    assert error.value.details == [{"check": "transition_seed_schedule"}]


@pytest.mark.parametrize("tamper", ["profile", "environment_seed"])
@pytest.mark.parametrize("tampered_strategy", ["greedy", "dqn"])
def test_mismatched_strategy_fails_without_returning_results(client, monkeypatch, tamper, tampered_strategy):
    original = rollout._evaluate

    def tampered(runtime, strategy, profile, environment_seed, policy_seed):
        if strategy == tampered_strategy and tamper == "profile":
            profile = (1,) + tuple(profile[1:])
        if strategy == tampered_strategy and tamper == "environment_seed":
            environment_seed += 1
        return original(runtime, strategy, profile, environment_seed, policy_seed)

    monkeypatch.setattr(rollout, "_evaluate", tampered)

    response = client.post("/internal/compare", json={"resistance_profile": [0] * 7, "environment_seed": 5, "policy_seed": 5})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "comparison_contract_violation"
    assert response.json()["error"]["details"] == [{"check": "existing_matched_run_validation"}]
    assert "ppo" not in response.json() and "steps" not in response.text


def test_same_state_action_and_seed_is_deterministic_but_a_shared_seed_gives_different_outcomes_per_action(runtime):
    model = StochasticTransitionModel(sampler=TransitionSampler(runtime.manifest.scenario_id))
    state = ResistanceState(ALL_SUSCEPTIBLE)

    for seed in (1, 12345, 2**31 - 5):
        outcomes = {action: model.step(state, action, seed=seed) for action in range(7)}

        assert outcomes == {action: model.step(state, action, seed=seed) for action in range(7)}
        assert len({sampled.status for _, sampled in outcomes.values()}) > 1
        assert len({sampled.candidates for _, sampled in outcomes.values()}) > 1


def test_matched_seed_schedules_still_produce_action_dependent_outcomes(runtime):
    action_dependent = []
    for profile in SAMPLE_PROFILES:
        body = rollout.compare(runtime, resistance_profile=list(profile), environment_seed=100001, policy_seed=900001)
        ppo, greedy, observed = body["ppo"]["steps"], body["greedy"]["steps"], body["comparison_contract"]["observed"]

        assert body["comparison_contract"]["verified"] is True
        assert all(left["transition_seed"] == right["transition_seed"] for left, right in zip(ppo, greedy))
        divergence = observed["first_divergent_step"]
        if divergence is None:
            assert [s["action_id"] for s in ppo] == [s["action_id"] for s in greedy]
            continue
        assert [(s["action_id"], s["resistance_profile_after"]) for s in ppo[:divergence]] == [
            (s["action_id"], s["resistance_profile_after"]) for s in greedy[:divergence]
        ]
        left, right = ppo[divergence], greedy[divergence]
        assert left["resistance_profile_before"] == right["resistance_profile_before"]
        assert left["transition_seed"] == right["transition_seed"]
        if left["action_id"] != right["action_id"] and (left["transition_status"], left["resistance_profile_after"]) != (
            right["transition_status"], right["resistance_profile_after"]
        ):
            action_dependent.append((profile, divergence))

    assert action_dependent, "expected at least one step where an equal transition seed gave different outcomes"
