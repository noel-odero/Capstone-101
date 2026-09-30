from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.resistance_state import ResistanceState
from simulation.stochastic_transition_model import (
    SampledTransition,
)


class StubEpisodeStep:
    def __init__(self, next_state):
        self.next_state = next_state

    def execute(
        self,
        state,
        action,
        treatment_step,
        seed=None,
        rng=None,
    ):
        class Result:
            pass

        result = Result()
        result.next_state = self.next_state
        return result


def test_episode_progression_increments_treatment_step():
    next_state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    progression = EpisodeProgression(
        episode_step=StubEpisodeStep(next_state)
    )

    next_episode = progression.step(
        episode,
        action=0,
    )

    assert next_episode.treatment_step == 1


def test_episode_progression_uses_episode_step_next_state():
    next_state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    progression = EpisodeProgression(
        episode_step=StubEpisodeStep(next_state)
    )

    next_episode = progression.step(
        episode,
        action=0,
    )

    assert next_episode.resistance_state == next_state


def test_episode_progression_preserves_original_episode():
    next_state = ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    progression = EpisodeProgression(
        episode_step=StubEpisodeStep(next_state)
    )

    progression.step(
        episode,
        action=0,
    )

    assert episode.resistance_state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    assert episode.treatment_step == 0