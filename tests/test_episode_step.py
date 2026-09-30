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