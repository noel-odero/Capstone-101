from copy import deepcopy
from itertools import product

import pytest

from ml.src.value_iteration import value_iteration
from simulation.decoder import decode_observation
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.environment import AntibioticEnvironment
from simulation.episode import EpisodeState
from simulation.resistance_state import ResistanceState


def planning_state(profile, treatment_step=0):
    return EpisodeState(
        ResistanceState(tuple(int(value) for value in profile)),
        treatment_step,
    )


@pytest.mark.parametrize(
    ("first_action", "expected_profile", "expected_action"),
    [(1, "1000000", 1), (2, "0000000", 2)],
)
def test_stochastic_observation_reconstructs_correct_vi_lookup(
    first_action, expected_profile, expected_action
):
    reference = DeterministicReferenceEnvironment(max_steps=2)
    result = value_iteration(reference)
    environment = AntibioticEnvironment(max_steps=2)
    environment.reset(seed=42)
    observation, _, terminated, _, _ = environment.step(first_action)
    assert not terminated

    decoded = decode_observation(tuple(observation))
    observed_state = EpisodeState(
        ResistanceState(tuple(int(value) for value in decoded.susceptibility)),
        int(decoded.treatment_step),
    )

    assert observed_state == planning_state(expected_profile, 1)
    assert observed_state == environment.episode
    assert result.policy[observed_state] == expected_action
    environment.close()


@pytest.mark.parametrize("gamma", [0.0, 0.5, 1.0])
def test_full_state_set_satisfies_bellman_equations_and_tie_rule(gamma):
    environment = DeterministicReferenceEnvironment()
    result = value_iteration(environment, gamma=gamma)
    states = set(environment.states())

    assert len(states) == 1152
    assert set(result.state_values) == set(result.action_values) == set(result.policy) == states
    assert result.gamma == gamma

    for state in states:
        assert set(result.action_values[state]) == set(range(7))
        if environment.is_terminal(state):
            assert result.state_values[state] == 0.0
            assert result.policy[state] is None
            assert all(value == 0.0 for value in result.action_values[state].values())
            continue

        for action in range(7):
            next_state, reward, terminal, _ = environment.transition(state, action)
            continuation = 0.0 if terminal else result.state_values[next_state]
            assert result.action_values[state][action] == pytest.approx(
                reward + gamma * continuation
            )
        maximum = max(result.action_values[state].values())
        assert result.state_values[state] == maximum
        assert result.policy[state] == min(
            action for action, value in result.action_values[state].items()
            if value == maximum
        )


def test_terminal_entry_preserves_reward_and_has_zero_continuation():
    environment = DeterministicReferenceEnvironment()
    result = value_iteration(environment)
    last_step = planning_state("0000000", 7)
    early_terminal = planning_state("1111110")

    assert result.action_values[last_step][0] == pytest.approx(0.4)
    assert result.action_values[last_step][2] == pytest.approx(0.9)
    next_state, reward, terminal, _ = environment.transition(early_terminal, 0)
    assert terminal
    assert next_state == planning_state("1111111", 1)
    assert reward == pytest.approx(-1.6)
    assert result.action_values[early_terminal][0] == pytest.approx(-1.6)


@pytest.mark.parametrize("gamma", [0.0, 0.5, 1.0])
def test_known_immediate_reward_plus_continuation(gamma):
    environment = DeterministicReferenceEnvironment(max_steps=2)
    result = value_iteration(environment, gamma=gamma)
    state = planning_state("0000000")

    assert result.action_values[state][2] == pytest.approx(0.9 + gamma * 0.9)
    assert result.state_values[state] == pytest.approx(0.9 + gamma * 0.9)


def test_exact_ties_choose_lowest_action_id():
    environment = DeterministicReferenceEnvironment(max_steps=1)
    result = value_iteration(environment)
    state = planning_state("0000000")

    assert result.action_values[state][2] == result.action_values[state][4]
    assert result.action_values[state][4] == result.action_values[state][6]
    assert result.policy[state] == 2


@pytest.mark.parametrize("gamma", [0.5, 1.0])
def test_matches_exhaustive_action_sequences_for_every_initial_profile(gamma):
    environment = DeterministicReferenceEnvironment(max_steps=2)
    result = value_iteration(environment, gamma=gamma)

    for initial_state in environment.states():
        if initial_state.treatment_step != 0:
            continue
        returns = []
        for actions in product(range(7), repeat=2):
            state = initial_state
            rewards = []
            for action in actions:
                if environment.is_terminal(state):
                    break
                state, reward, terminal, _ = environment.transition(state, action)
                rewards.append(reward)
                if terminal:
                    break
            total = sum(gamma ** step * reward for step, reward in enumerate(rewards))
            returns.append((actions[0], total))

        optimal_return = max(total for _, total in returns)
        assert result.state_values[initial_state] == pytest.approx(optimal_return)
        if environment.is_terminal(initial_state):
            assert result.policy[initial_state] is None
        else:
            assert result.policy[initial_state] == min(
                action for action, total in returns if total == optimal_return
            )


@pytest.mark.parametrize("gamma", [-0.01, 1.01, float("nan"), float("inf"), -float("inf")])
def test_rejects_invalid_discount_values(gamma):
    with pytest.raises(ValueError, match="finite and between"):
        value_iteration(DeterministicReferenceEnvironment(), gamma=gamma)


@pytest.mark.parametrize("gamma", [True, False, None, "1", 1 + 0j])
def test_rejects_invalid_discount_types(gamma):
    with pytest.raises(TypeError, match="real number"):
        value_iteration(DeterministicReferenceEnvironment(), gamma=gamma)


def test_planning_does_not_mutate_or_depend_on_interactive_episode():
    environment = DeterministicReferenceEnvironment()
    before_reset = value_iteration(environment)
    assert environment.episode is None
    environment.reset(seed=18, options={"initial_resistance_state": (1, 0, 1, 0, 0, 0, 0)})
    environment.step(2)
    episode = environment.episode
    random_state = deepcopy(environment.np_random.bit_generator.state)
    action_random_state = deepcopy(environment.action_space.np_random.bit_generator.state)

    after_reset = value_iteration(environment)

    assert environment.episode is episode
    assert environment.np_random.bit_generator.state == random_state
    assert environment.action_space.np_random.bit_generator.state == action_random_state
    assert before_reset == after_reset == value_iteration(environment)