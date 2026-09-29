from simulation.candidate_transition import CandidateTransition
from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.resistance_state import ResistanceState
from simulation.transition_sampler import SampledTransition


class StubTreatmentExecutor:
    def execute(self, state, action):
        return None


class StubTransitionGenerator:
    def __init__(self, candidate):
        self.candidate = candidate

    def generate(self, state, action):
        return (self.candidate,)


class StubTransitionSampler:
    def __init__(self, candidate):
        self.candidate = candidate

    def sample(self, candidates, seed=None):
        return SampledTransition(
            candidate=self.candidate
        )


def build_progression(candidate):
    return EpisodeProgression(
        treatment_executor=StubTreatmentExecutor(),
        transition_generator=StubTransitionGenerator(candidate),
        transition_sampler=StubTransitionSampler(candidate),
    )


def test_episode_progression_increments_treatment_step():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="neutral",
        source_ids=("TEST",),
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    next_episode = build_progression(candidate).step(
        episode,
        action=0,
    )

    assert next_episode.treatment_step == 1


def test_episode_progression_applies_sampled_transition():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("TEST",),
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    next_episode = build_progression(candidate).step(
        episode,
        action=0,
    )

    assert next_episode.resistance_state == ResistanceState(
        (0, 0, 0, 0, 1, 0, 0)
    )


def test_episode_progression_preserves_original_episode():
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome="cross_resistance",
        source_ids=("TEST",),
    )

    episode = EpisodeState(
        resistance_state=ResistanceState(
            (0, 0, 0, 0, 0, 0, 0)
        )
    )

    build_progression(candidate).step(
        episode,
        action=0,
    )

    assert episode.resistance_state == ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    assert episode.treatment_step == 0