from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.resistance_state import ResistanceState


def test_episode_progression_returns_episode_step_result():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    result = EpisodeProgression(episode_step=EpisodeStep()).step(
        episode,
        action=0,
        seed=1,
    )

    assert result.previous_state == episode.resistance_state
    assert result.observation.treatment_step == 1
    assert result.next_state != episode.resistance_state
    assert result.sampled_transition.scenario_id == "REF_UNIFORM_SUPPORTED"


def test_episode_progression_preserves_original_episode():
    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    result = EpisodeProgression(episode_step=EpisodeStep()).step(
        episode,
        action=0,
        seed=1,
    )

    assert episode.resistance_state == ResistanceState((0, 0, 0, 0, 0, 0, 0))
    assert episode.treatment_step == 0
    assert result.next_state != episode.resistance_state