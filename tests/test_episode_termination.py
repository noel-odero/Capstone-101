from simulation.action_space import ActionSpace
from simulation.episode import EpisodeState
from simulation.episode_termination import EpisodeTermination
from simulation.resistance_state import ResistanceState


def test_episode_terminates_at_maximum_steps():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        ),
        treatment_step=8,
    )

    termination = EpisodeTermination()

    assert termination.is_terminated(episode) is True


def test_episode_does_not_terminate_before_maximum_steps():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        ),
        treatment_step=7,
    )

    termination = EpisodeTermination()

    assert termination.is_terminated(episode) is False


def test_episode_terminates_when_all_antibiotics_are_resistant():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (1, 1, 1, 1, 1, 1, 1)
        ),
        treatment_step=3,
    )

    termination = EpisodeTermination()

    assert termination.is_terminated(episode) is True


def test_episode_does_not_terminate_when_some_antibiotics_remain_effective():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (1, 1, 1, 1, 1, 1, 0)
        ),
        treatment_step=3,
    )

    termination = EpisodeTermination()

    assert termination.is_terminated(episode) is False


def test_episode_termination_accepts_custom_max_steps():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        ),
        treatment_step=5,
    )

    termination = EpisodeTermination(max_steps=5)

    assert termination.is_terminated(episode) is True


def test_episode_termination_rejects_invalid_max_steps():
    try:
        EpisodeTermination(max_steps=0)
        assert False
    except ValueError:
        assert True