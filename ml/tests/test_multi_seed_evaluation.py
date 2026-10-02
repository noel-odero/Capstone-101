from copy import deepcopy
import json

import pytest

from ml.src.greedy_policy import GreedyPolicy
from ml.src.metrics import calculate_metrics
from ml.src.multi_seed_evaluation import run_multi_seed_evaluation
from ml.src.random_policy import RandomPolicy
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ResistanceState
from simulation.reward import RewardWeights
from simulation.transition_sampler import TransitionSampler


PROFILES = [(0,) * 7, (1, 0, 0, 1, 0, 0, 0)]
SEEDS = [(10, 100), (20, 200)]


def environment_factory():
    return AntibioticEnvironment(max_steps=2)


@pytest.mark.parametrize("policy", [RandomPolicy, GreedyPolicy])
def test_complete_reproducible_results_and_metrics(policy):
    first = run_multi_seed_evaluation(environment_factory, policy, SEEDS, initial_states=PROFILES)
    second = run_multi_seed_evaluation(environment_factory, policy, SEEDS, initial_states=PROFILES)
    assert first == second
    assert first.seed_pairs == tuple(SEEDS)
    assert first.initial_resistance_profiles == tuple(PROFILES)
    assert len(first.runs) == 2
    identities = []
    for index, run in enumerate(first.runs):
        assert run.run_id == index
        assert run.environment_base_seed == SEEDS[index][0]
        assert run.policy_base_seed == SEEDS[index][1]
        assert run.metrics == calculate_metrics(run.evaluation)
        assert run.metrics.policy_name.endswith(policy.__name__)
        assert run.metrics.scenario_id == "REF_UNIFORM_SUPPORTED"
        assert run.episode_identities == ((index, 0), (index, 1))
        identities.extend(run.episode_identities)
        for episode in run.evaluation.episodes:
            assert episode.environment_seed == SEEDS[index][0] + episode.episode_id
            assert episode.policy_seed == SEEDS[index][1] + episode.episode_id
            assert episode.initial_resistance_profile == PROFILES[episode.episode_id]
            assert episode.steps
            assert len(episode.observations) == len(episode.steps) + 1
    assert len(set(identities)) == 4
    json.dumps(first.to_dict(), allow_nan=False)


def test_seed_order_preserved_and_cross_stream_equal_seeds_allowed():
    plan = [(20, 20), (10, 10)]
    result = run_multi_seed_evaluation(environment_factory, RandomPolicy, plan, initial_states=PROFILES)
    assert result.seed_pairs == tuple(plan)
    assert result.runs[0].evaluation.episodes[0].environment_seed == 20


@pytest.mark.parametrize(("plan", "stream"), [
    ([(10, 100), (11, 200)], "environment"),
    ([(10, 100), (20, 101)], "policy"),
    ([(10, 100), (10, 100)], "environment"),
])
def test_expanded_overlaps_rejected_before_creating_environments(plan, stream):
    def should_not_create():
        raise AssertionError("Validate the plan before executing any run")

    with pytest.raises(ValueError, match=f"expanded {stream}"):
        run_multi_seed_evaluation(should_not_create, RandomPolicy, plan, initial_states=PROFILES)


@pytest.mark.parametrize(("plan", "exception"), [
    ([], ValueError), ([(1,)], ValueError), ([(-1, 2)], ValueError),
    ([(True, 1)], TypeError), ([(1, 2.5)], TypeError), ("12", TypeError),
])
def test_invalid_seed_plan(plan, exception):
    with pytest.raises(exception):
        run_multi_seed_evaluation(environment_factory, RandomPolicy, plan, initial_states=PROFILES)


@pytest.mark.parametrize(("profiles", "exception"), [
    ([], ValueError), ([(0, 1)], ValueError), ([(2,) * 7], ValueError),
    ("0000000", TypeError),
])
def test_invalid_initial_states(profiles, exception):
    with pytest.raises(exception):
        run_multi_seed_evaluation(environment_factory, RandomPolicy, SEEDS, initial_states=profiles)


def test_fresh_environment_and_policy_instances_and_closure():
    environments = []
    policies = []

    class TrackedEnvironment(AntibioticEnvironment):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def create_environment():
        environment = TrackedEnvironment(max_steps=2)
        environments.append(environment)
        return environment

    def create_policy(action_space, seed):
        policy = RandomPolicy(action_space, seed=seed)
        policies.append(policy)
        return policy

    run_multi_seed_evaluation(create_environment, create_policy, SEEDS, initial_states=PROFILES)
    assert len(environments) == len({id(value) for value in environments}) == 2
    assert all(environment.closed for environment in environments)
    assert len(policies) == len({id(value) for value in policies}) == 4


def test_reused_environment_instance_rejected():
    environment = environment_factory()
    with pytest.raises(ValueError, match="reused an environment"):
        run_multi_seed_evaluation(lambda: environment, RandomPolicy, SEEDS, initial_states=PROFILES)


def test_reused_policy_instance_rejected():
    shared = RandomPolicy(environment_factory().action_space, seed=1)

    def factory(_action_space, seed):
        return shared

    with pytest.raises(ValueError, match="reused a policy"):
        run_multi_seed_evaluation(environment_factory, factory, SEEDS, initial_states=PROFILES)


@pytest.mark.parametrize("difference", ["horizon", "scenario", "reward", "data", "data_order", "actions"])
def test_configuration_and_transition_data_mismatch_rejected(difference):
    count = 0

    def factory():
        nonlocal count
        environment = environment_factory()
        count += 1
        if count == 2:
            step = environment.episode_progression.episode_step
            if difference == "horizon":
                environment.episode_termination.max_steps = 3
            elif difference == "scenario":
                step.transition_model.sampler = TransitionSampler("SENSITIVITY_Q_050")
            elif difference == "reward":
                step.reward_function.weights = RewardWeights(exposure=0.2)
            elif difference == "data":
                step.transition_model.candidate_generator.interactions[0]["relationship"] = "neutral"
            elif difference == "data_order":
                step.transition_model.candidate_generator.interactions = tuple(reversed(
                    step.transition_model.candidate_generator.interactions
                ))
            else:
                environment.action_space_config.actions = tuple(reversed(environment.action_space_config.actions))
        return environment

    with pytest.raises(ValueError, match="differs across runs"):
        run_multi_seed_evaluation(factory, RandomPolicy, SEEDS, initial_states=PROFILES)


def test_configuration_mutation_during_run_rejected_and_environment_closed():
    environment = environment_factory()
    closed = []
    environment.close = lambda: closed.append(True)

    def policy_factory(action_space, seed):
        environment.episode_progression.episode_step.reward_function.weights = RewardWeights(exposure=0.2)
        return RandomPolicy(action_space, seed=seed)

    with pytest.raises(ValueError, match="changed during a run"):
        run_multi_seed_evaluation(lambda: environment, policy_factory, SEEDS[:1], initial_states=PROFILES)
    assert closed == [True]


def test_zero_step_episodes_preserve_seed_and_identity_and_undefined_rates():
    result = run_multi_seed_evaluation(
        environment_factory, GreedyPolicy, SEEDS,
        initial_states=[ResistanceState((1,) * 7)],
    )
    for run in result.runs:
        episode = run.evaluation.episodes[0]
        assert episode.steps == ()
        assert episode.termination_reason == "no_effective_antibiotic"
        assert run.metrics.episodes[0].treatment_effectiveness_rate is None
        assert run.episode_identities == ((run.run_id, 0),)


def test_random_and_greedy_reuse_matched_conditions_not_paired_draws():
    random_result = run_multi_seed_evaluation(environment_factory, RandomPolicy, SEEDS, initial_states=PROFILES)
    greedy_result = run_multi_seed_evaluation(environment_factory, GreedyPolicy, SEEDS, initial_states=PROFILES)
    assert random_result.environment_configuration == greedy_result.environment_configuration
    assert random_result.seed_pairs == greedy_result.seed_pairs
    assert random_result.initial_resistance_profiles == greedy_result.initial_resistance_profiles
    for random_run, greedy_run in zip(random_result.runs, greedy_result.runs):
        for random_episode, greedy_episode in zip(random_run.evaluation.episodes, greedy_run.evaluation.episodes):
            assert random_episode.environment_seed == greedy_episode.environment_seed
            assert random_episode.policy_seed == greedy_episode.policy_seed
            assert random_episode.initial_resistance_profile == greedy_episode.initial_resistance_profile


def test_inputs_not_mutated_and_export_detached():
    seeds = deepcopy(SEEDS)
    profiles = deepcopy(PROFILES)
    result = run_multi_seed_evaluation(environment_factory, RandomPolicy, seeds, initial_states=profiles)
    assert seeds == SEEDS and profiles == PROFILES
    exported = result.to_dict()
    exported["environment_configuration"]["horizon"] = 999
    assert result.environment_configuration["horizon"] == 2


def test_deterministic_environment_rejected():
    with pytest.raises(TypeError, match="stochastic"):
        run_multi_seed_evaluation(DeterministicReferenceEnvironment, RandomPolicy, SEEDS, initial_states=PROFILES)


def test_changing_policy_identity_across_runs_rejected():
    count = 0

    def policy_factory(action_space, seed):
        nonlocal count
        count += 1
        policy = RandomPolicy if count == 1 else GreedyPolicy
        return policy(action_space, seed=seed)

    with pytest.raises(ValueError, match="identity differs"):
        run_multi_seed_evaluation(environment_factory, policy_factory, SEEDS, initial_states=PROFILES[:1])