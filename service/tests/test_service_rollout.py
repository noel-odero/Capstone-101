from concurrent.futures import ThreadPoolExecutor
from itertools import product

import pytest

from ml.src.evaluation_runner import run_evaluation
from ml.src.greedy_policy import GreedyPolicy
from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.ppo_inference import NO_CANDIDATE_STATUS, InferenceContext
from ml.src.ppo_training import load_ppo_model, make_training_environment
from service import rollout
from simulation.resistance_state import ANTIBIOTICS

PROFILES = [(0,) * 7, (1, 0, 0, 1, 0, 0, 1), (0, 1, 0, 1, 0, 1, 0), (0, 0, 0, 0, 1, 0, 0), (1, 1, 1, 1, 1, 1, 0)]
ALL_NONTERMINAL = [profile for profile in product((0, 1), repeat=7) if not all(profile)]


def simulate(runtime, strategy, profile, environment_seed, policy_seed=None):
    return rollout.simulate(
        runtime,
        strategy=strategy,
        resistance_profile=list(profile),
        environment_seed=environment_seed,
        policy_seed=policy_seed,
    )["result"]


def direct_episode(runtime, policy_factory, profile, environment_seed, policy_seed):
    environment = make_training_environment(runtime.config)
    try:
        return run_evaluation(
            environment,
            policy_factory,
            1,
            environment_seed=environment_seed,
            policy_seed=policy_seed,
            initial_states=[profile],
        ).episodes[0]
    finally:
        environment.close()


@pytest.mark.parametrize("profile", PROFILES)
def test_ppo_adapter_matches_direct_engine_inference_at_every_step(runtime, profile):
    result = simulate(runtime, "ppo", profile, environment_seed=100001)

    last_action = None
    for index, step in enumerate(result["steps"]):
        context = InferenceContext(tuple(step["resistance_profile_before"]), last_action, index)
        assert runtime.engine.recommend(context).action_id == step["action_id"]
        last_action = step["action_id"]


@pytest.mark.parametrize("profile", PROFILES)
def test_ppo_adapter_matches_path_loaded_policy_through_the_existing_evaluator(runtime, profile):
    model = load_ppo_model(runtime.manifest.checkpoint_path, device="cpu")
    factory = lambda action_space, seed: MaskablePPOObservationPolicy(action_space, model, seed)

    expected = direct_episode(runtime, factory, profile, 100001, 0)
    result = simulate(runtime, "ppo", profile, environment_seed=100001)

    assert [step["action_id"] for step in result["steps"]] == list(expected.actions)
    assert [step["reward"] for step in result["steps"]] == list(expected.rewards)
    assert [step["transition_seed"] for step in result["steps"]] == [s.info["transition_seed"] for s in expected.steps]
    assert result["final_profile"] == list(expected.final_resistance_profile)
    assert result["termination_reason"] == expected.termination_reason


@pytest.mark.parametrize(("profile", "environment_seed", "policy_seed"), [(PROFILES[0], 7, 3), (PROFILES[2], 100002, 900001), (PROFILES[3], 5, 5)])
def test_greedy_adapter_matches_existing_evaluator_with_matching_seeds(runtime, profile, environment_seed, policy_seed):
    expected = direct_episode(runtime, GreedyPolicy, profile, environment_seed, policy_seed)

    result = simulate(runtime, "greedy", profile, environment_seed, policy_seed)

    assert [step["action_id"] for step in result["steps"]] == list(expected.actions)
    assert [step["reward"] for step in result["steps"]] == list(expected.rewards)
    assert [step["transition_status"] for step in result["steps"]] == [s.info["transition_status"] for s in expected.steps]
    assert result["final_profile"] == list(expected.final_resistance_profile)
    assert result["metrics"]["cumulative_resistance_burden"] == -expected.cumulative_reward
    assert result["metrics"]["cumulative_reward"] == expected.cumulative_reward


def test_greedy_policy_seed_changes_choices_and_ppo_ignores_it(runtime):
    greedy = {seed: [s["action_id"] for s in simulate(runtime, "greedy", PROFILES[0], 4, seed)["steps"]] for seed in range(4)}
    ppo = {seed: [s["action_id"] for s in simulate(runtime, "ppo", PROFILES[0], 4, seed)["steps"]] for seed in range(4)}

    assert len({tuple(actions) for actions in greedy.values()}) > 1
    assert len({tuple(actions) for actions in ppo.values()}) == 1


@pytest.mark.parametrize("strategy", ["ppo", "greedy"])
def test_trace_is_internally_consistent(runtime, strategy):
    result = simulate(runtime, strategy, PROFILES[1], environment_seed=31, policy_seed=2)
    steps, states = result["steps"], result["states"]

    assert len(states) == len(steps) + 1
    assert states[0]["state_index"] == 0 and states[0]["resistance_profile"] == list(PROFILES[1])
    assert states[0]["last_action_id"] is None
    previous = list(PROFILES[1])
    for index, step in enumerate(steps):
        before, after = step["resistance_profile_before"], step["resistance_profile_after"]
        assert before == previous == states[index]["resistance_profile"]
        assert after == states[index + 1]["resistance_profile"]
        assert (step["step_index"], step["treatment_step_before"], step["treatment_step_after"]) == (index, index, index + 1)
        assert step["antibiotic"] == ANTIBIOTICS[step["action_id"]]
        assert before[step["action_id"]] == 0 and step["selected_drug_susceptible"] is True
        assert step["action_id"] in [item["action_id"] for item in step["feasible_actions"]]
        assert [item["action_id"] for item in step["feasible_actions"]] == [i for i, v in enumerate(before) if v == 0]
        assert step["newly_resistant_antibiotics"] == [n for n, b, a in zip(ANTIBIOTICS, before, after) if (b, a) == (0, 1)]
        assert step["newly_susceptible_antibiotics"] == [n for n, b, a in zip(ANTIBIOTICS, before, after) if (b, a) == (1, 0)]
        assert step["resistant_count_after"] == sum(after) and step["susceptible_count_after"] == 7 - sum(after)
        assert states[index + 1]["last_action_id"] == step["action_id"]
        assert step["is_terminal_after"] is (index == len(steps) - 1)
        assert (step["termination_reason"] is not None) is (index == len(steps) - 1)
        previous = after
    assert result["final_profile"] == previous
    assert states[-1]["is_terminal"] is True and all(not s["is_terminal"] for s in states[:-1])


def test_unsupported_steps_leave_the_profile_unchanged_without_inventing_outcomes(runtime):
    unsupported = []
    for seed in range(6):
        for strategy in ("ppo", "greedy"):
            for step in simulate(runtime, strategy, PROFILES[0], seed, seed)["steps"]:
                if step["transition_status"] == NO_CANDIDATE_STATUS:
                    unsupported.append(step)

    assert unsupported
    for step in unsupported:
        assert step["has_candidate_transition"] is False and step["candidate_transitions"] == []
        assert step["selected_outcome"] is None and step["selected_target_drug"] is None and step["source_ids"] == []
        assert step["selected_candidate_probability"] is None and step["no_transition_probability"] is None
        assert step["resistance_profile_after"] == step["resistance_profile_before"]
        assert step["newly_resistant_antibiotics"] == step["newly_susceptible_antibiotics"] == []


def test_supported_transitions_report_outcome_target_sources_and_profile_diff(runtime):
    cross, collateral = [], []
    for seed in range(60):
        for step in simulate(runtime, "greedy", (0, 0, 0, 0, 1, 0, 0), seed, seed)["steps"]:
            if step["selected_outcome"] == "cross_resistance":
                cross.append(step)
            if step["selected_outcome"] == "collateral_sensitivity":
                collateral.append(step)

    assert cross and collateral
    for step in cross:
        assert step["newly_resistant_antibiotics"] == [step["selected_target_drug"]] and step["source_ids"]
        assert step["has_candidate_transition"] is True and step["transition_seed"] is not None
    for step in collateral:
        assert step["newly_susceptible_antibiotics"] == [step["selected_target_drug"]] and step["source_ids"]


def test_every_nonterminal_profile_runs_the_full_horizon_for_both_strategies(runtime):
    for profile in ALL_NONTERMINAL:
        for strategy in ("ppo", "greedy"):
            result = simulate(runtime, strategy, profile, 100001, 900001)
            assert len(result["steps"]) == runtime.engine.horizon == 8
            assert result["termination_reason"] == "maximum_horizon"
            assert result["states"][-1]["treatment_step"] == 8


def test_burden_equals_negated_reward_sum_from_the_simulator(runtime):
    result = simulate(runtime, "greedy", PROFILES[1], 9, 9)

    assert result["metrics"]["cumulative_reward"] == pytest.approx(sum(step["reward"] for step in result["steps"]))
    assert result["metrics"]["cumulative_resistance_burden"] == pytest.approx(-result["metrics"]["cumulative_reward"])
    assert result["metrics"]["unsupported_step_count"] == sum(
        step["transition_status"] == NO_CANDIDATE_STATUS for step in result["steps"]
    )


def test_comparison_pairs_environment_seed_but_not_outcomes(runtime):
    body = rollout.compare(runtime, resistance_profile=list(PROFILES[0]), environment_seed=100001, policy_seed=900001)

    ppo, greedy = body["ppo"], body["greedy"]
    assert ppo["initial_profile"] == greedy["initial_profile"] and ppo["environment_seed"] == greedy["environment_seed"] == 100001
    common = min(len(ppo["steps"]), len(greedy["steps"]))
    assert common == 8
    assert [s["transition_seed"] for s in ppo["steps"][:common]] == [s["transition_seed"] for s in greedy["steps"][:common]]
    assert simulate(runtime, "ppo", PROFILES[0], 100001) == ppo
    assert simulate(runtime, "greedy", PROFILES[0], 100001, 900001) == greedy


def test_concurrent_runs_match_sequential_runs(runtime):
    jobs = [(strategy, PROFILES[index % len(PROFILES)], 100 + index) for index, strategy in enumerate(["ppo", "greedy"] * 6)]
    sequential = [simulate(runtime, strategy, profile, seed, seed) for strategy, profile, seed in jobs]

    with ThreadPoolExecutor(max_workers=6) as pool:
        concurrent = list(pool.map(lambda job: simulate(runtime, job[0], job[1], job[2], job[2]), jobs))

    assert concurrent == sequential


def test_concurrent_http_requests_do_not_share_episode_state(client):
    payloads = [
        {"resistance_profile": list(PROFILES[index % len(PROFILES)]), "strategy": ["ppo", "greedy"][index % 2], "environment_seed": 50 + index, "policy_seed": index}
        for index in range(8)
    ]
    sequential = [client.post("/internal/simulate", json=payload).json()["result"] for payload in payloads]

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda payload: client.post("/internal/simulate", json=payload), payloads))

    assert all(response.status_code == 200 for response in responses)
    assert [response.json()["result"] for response in responses] == sequential
    assert len({response.json()["run_id"] for response in responses}) == len(responses)
