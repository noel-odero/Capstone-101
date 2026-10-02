import json
import random

import numpy as np
import pytest
from gymnasium.spaces import Box, Discrete

from ml.src.greedy_policy import GreedyPolicy
from simulation.encoder import encode_observation
from simulation.environment import AntibioticEnvironment
from simulation.observation import Observation


def encoded_observation(susceptibility, last_action=(0,) * 7, treatment_step=0):
    return np.asarray(
        encode_observation(
            Observation(tuple(susceptibility), tuple(last_action), treatment_step)
        ),
        dtype=np.float32,
    )


@pytest.mark.parametrize(
    ("susceptibility", "expected_actions"),
    [
        ((0,) * 7, set(range(7))),
        ((1, 0, 1, 0, 1, 0, 1), {1, 3, 5}),
        ((-1, 0, 1, -1, 0, 1, -1), {1, 4}),
    ],
)
def test_selects_uniformly_from_only_observed_susceptible_actions(
    susceptibility, expected_actions
):
    action_space = Discrete(7)
    policy = GreedyPolicy(action_space, seed=42)
    observation = encoded_observation(susceptibility)
    actions = [policy.select_action(observation) for _ in range(1000)]
    reference_rng = random.Random(42)
    choices = tuple(sorted(expected_actions))

    assert all(type(action) is int and action_space.contains(action) for action in actions)
    assert set(actions) == expected_actions
    assert actions == [reference_rng.choice(choices) for _ in range(1000)]


@pytest.mark.parametrize("susceptible_action", range(7))
def test_exactly_one_susceptible_option_always_selected(susceptible_action):
    susceptibility = [1] * 7
    susceptibility[susceptible_action] = 0
    policy = GreedyPolicy(Discrete(7), seed=42)

    assert all(
        policy.select_action(encoded_observation(susceptibility)) == susceptible_action
        for _ in range(30)
    )


@pytest.mark.parametrize("susceptibility", [(1,) * 7, (-1,) * 7, (1, -1, 1, -1, 1, -1, 1)])
def test_no_observed_susceptible_option_is_explicit_error(susceptibility):
    policy = GreedyPolicy(Discrete(7), seed=42)

    with pytest.raises(ValueError, match="No antibiotic is marked susceptible"):
        policy.select_action(encoded_observation(susceptibility))


def test_identical_seeds_reproduce_tie_breaking_without_using_history():
    first = GreedyPolicy(Discrete(7), seed=18)
    second = GreedyPolicy(Discrete(7), seed=18)
    susceptibility = (0, 1, 0, 1, 0, 1, 0)
    first_observation = encoded_observation(susceptibility)
    second_observation = encoded_observation(susceptibility, (0, 1, 0, 0, 0, 0, 0), 5)

    assert [first.select_action(first_observation) for _ in range(100)] == [
        second.select_action(second_observation) for _ in range(100)
    ]


def test_policy_does_not_consume_environment_or_action_space_rng():
    environment = AntibioticEnvironment()
    control = AntibioticEnvironment()
    observation, _ = environment.reset(seed=42)
    control.reset(seed=42)
    environment.action_space.seed(18)
    control.action_space.seed(18)
    policy = GreedyPolicy(environment.action_space, seed=11)

    for _ in range(100):
        policy.select_action(observation)

    assert environment.np_random.integers(2**32) == control.np_random.integers(2**32)
    assert [environment.action_space.sample() for _ in range(100)] == [
        control.action_space.sample() for _ in range(100)
    ]
    environment.close()
    control.close()


@pytest.mark.parametrize("action_space", [Discrete(6), Discrete(7, start=1)])
def test_rejects_action_space_not_matching_observation_order(action_space):
    with pytest.raises(ValueError, match="canonical seven actions"):
        GreedyPolicy(action_space)


def test_rejects_nondiscrete_action_space():
    with pytest.raises(TypeError, match="Discrete action space"):
        GreedyPolicy(Box(low=0, high=1, shape=(1,)))


@pytest.mark.parametrize("observation", [(0,) * 14, (2,) + (0,) * 14])
def test_invalid_observations_use_existing_decoder_validation(observation):
    with pytest.raises(ValueError):
        GreedyPolicy(Discrete(7)).select_action(observation)


def test_observation_only_policy_works_without_environment_reference():
    policy = GreedyPolicy(Discrete(7), seed=42)

    assert policy.select_action(encoded_observation((1, 1, 0, 1, 1, 1, 1))) == 2


@pytest.mark.parametrize("first_action", [1, 2])
def test_greedy_treatment_is_effective_from_corrected_stochastic_observation(
    first_action,
):
    environment = AntibioticEnvironment()
    environment.reset(seed=42)
    observation, _, terminated, _, _ = environment.step(first_action)
    assert not terminated

    policy = GreedyPolicy(environment.action_space, seed=18)
    action = policy.select_action(observation)

    assert observation[action] == 0
    _, _, _, _, info = environment.step(action)
    assert info["effective"] is True
    environment.close()


def test_complete_episode_collects_public_results_and_reproduces():
    trajectories = []

    for _ in range(2):
        environment = AntibioticEnvironment()
        policy = GreedyPolicy(environment.action_space, seed=18)
        observation, _ = environment.reset(
            seed=42,
            options={"initial_resistance_state": (1, 0, 0, 1, 0, 0, 0)},
        )
        trajectory = []

        for _ in range(8):
            action = policy.select_action(observation)
            assert observation[action] == 0
            assert environment.action_space.contains(action)
            next_observation, reward, terminated, truncated, info = environment.step(action)
            assert info["effective"] is True
            assert environment.observation_space.contains(next_observation)
            assert isinstance(reward, float)
            assert "transition_status" in info
            assert "transition_seed" in info
            json.dumps(info)
            trajectory.append(
                (action, observation.tolist(), next_observation.tolist(), reward,
                 terminated, truncated, info)
            )
            observation = next_observation
            if terminated or truncated:
                break

        assert trajectory
        assert trajectory[-1][4] or trajectory[-1][5]
        trajectories.append(trajectory)
        environment.close()

    assert trajectories[0] == trajectories[1]