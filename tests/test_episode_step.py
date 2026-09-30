import random

from simulation.episode_step import EpisodeStep
from simulation.resistance_state import ResistanceState


def test_episode_step_executes_treatment_and_returns_next_observation():
    episode_step = EpisodeStep()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result = episode_step.execute(
        state=state,
        action=0,
        treatment_step=0,
        seed=1,
    )

    assert result.previous_state == state
    assert result.treatment.action == 0
    assert result.treatment.antibiotic == "CIPROFLOXACIN"
    assert result.treatment.effective is True
    assert result.observation.treatment_step == 1


def test_episode_step_records_selected_action_in_observation():
    episode_step = EpisodeStep()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result = episode_step.execute(
        state=state,
        action=2,
        treatment_step=3,
        seed=1,
    )

    assert result.observation.last_action == (
        0,
        0,
        1,
        0,
        0,
        0,
        0,
    )


def test_episode_step_observation_matches_next_state():
    episode_step = EpisodeStep()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result = episode_step.execute(
        state=state,
        action=0,
        treatment_step=0,
        seed=1,
    )

    expected_susceptibility = tuple(
        0 if value == 1 else 1
        for value in result.next_state.resistance
    )

    assert result.observation.susceptibility == expected_susceptibility


def test_episode_step_calculates_reward():
    episode_step = EpisodeStep()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result = episode_step.execute(
        state=state,
        action=0,
        treatment_step=0,
        seed=1,
    )

    assert isinstance(result.reward, float)


def test_episode_step_is_reproducible_with_same_seed():
    episode_step = EpisodeStep()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    result_1 = episode_step.execute(
        state=state,
        action=0,
        treatment_step=0,
        seed=42,
    )

    result_2 = episode_step.execute(
        state=state,
        action=0,
        treatment_step=0,
        seed=42,
    )

    assert result_1.next_state == result_2.next_state
    assert result_1.sampled_transition == result_2.sampled_transition
    assert result_1.reward == result_2.reward
    assert result_1.observation == result_2.observation


def test_persistent_rng_reproduces_sequence_of_episode_steps():
    episode_step = EpisodeStep()

    initial_state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    actions = (0, 1, 2, 3, 4)

    rng_one = random.Random(42)
    rng_two = random.Random(42)

    state_one = initial_state
    state_two = initial_state

    results_one = []
    results_two = []

    for treatment_step, action in enumerate(actions):
        result_one = episode_step.execute(
            state=state_one,
            action=action,
            treatment_step=treatment_step,
            rng=rng_one,
        )

        result_two = episode_step.execute(
            state=state_two,
            action=action,
            treatment_step=treatment_step,
            rng=rng_two,
        )

        results_one.append(result_one)
        results_two.append(result_two)

        state_one = result_one.next_state
        state_two = result_two.next_state

    assert results_one == results_two