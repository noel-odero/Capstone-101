import numpy as np
import pytest
from gymnasium.spaces import Box, Discrete

from ml.src.random_policy import RandomPolicy
from simulation.environment import AntibioticEnvironment


@pytest.mark.parametrize("action_space", [Discrete(7), Discrete(3, start=4)])
def test_policy_selects_valid_integer_actions(action_space):
    policy = RandomPolicy(action_space, seed=42)
    actions = [policy.select_action() for _ in range(1000)]

    assert all(type(action) is int for action in actions)
    assert all(action_space.contains(action) for action in actions)
    assert set(actions) == set(
        range(int(action_space.start), int(action_space.start + action_space.n))
    )


def test_same_seed_reproduces_action_sequence():
    first = RandomPolicy(Discrete(7), seed=42)
    second = RandomPolicy(Discrete(7), seed=42)

    assert [first.select_action() for _ in range(100)] == [
        second.select_action() for _ in range(100)
    ]


def test_different_seeds_produce_different_sequences():
    first = RandomPolicy(Discrete(7), seed=42)
    second = RandomPolicy(Discrete(7), seed=43)

    assert [first.select_action() for _ in range(100)] != [
        second.select_action() for _ in range(100)
    ]


def test_policy_ignores_observation():
    first = RandomPolicy(Discrete(7), seed=42)
    second = RandomPolicy(Discrete(7), seed=42)

    assert [first.select_action(np.zeros(15)) for _ in range(100)] == [
        second.select_action(np.ones(15)) for _ in range(100)
    ]


def test_policy_does_not_consume_action_space_rng():
    action_space = Discrete(7, seed=42)
    control_space = Discrete(7, seed=42)
    policy = RandomPolicy(action_space, seed=18)

    for _ in range(100):
        policy.select_action()

    assert [action_space.sample() for _ in range(100)] == [
        control_space.sample() for _ in range(100)
    ]


def test_policy_rejects_nondiscrete_action_space():
    with pytest.raises(TypeError, match="Discrete action space"):
        RandomPolicy(Box(low=0, high=1, shape=(1,)))


def test_complete_episode_results_are_reproducible():
    episodes = []

    for _ in range(2):
        environment = AntibioticEnvironment()
        policy = RandomPolicy(environment.action_space, seed=18)
        observation, _ = environment.reset(
            seed=42,
            options={"initial_resistance_state": (1, 0, 0, 1, 0, 0, 0)},
        )
        results = []

        for _ in range(environment.episode_termination.max_steps):
            action = policy.select_action(observation)
            assert environment.action_space.contains(action)
            observation, reward, terminated, truncated, info = environment.step(
                action
            )
            results.append(
                (action, observation.tolist(), reward, terminated, truncated, info)
            )
            if terminated or truncated:
                break

        assert results
        assert results[-1][3] or results[-1][4]
        assert all(isinstance(result[2], float) for result in results)
        assert all("transition_status" in result[5] for result in results)
        episodes.append(results)
        environment.close()

    assert episodes[0] == episodes[1]