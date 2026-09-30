from simulation.resistance_state import ResistanceState
from simulation.stochastic_transition_model import StochasticTransitionModel


class EmptyCandidateGenerator:
    def generate(self, state, action):
        return ()


def test_sampled_transition_is_applied_to_state():
    model = StochasticTransitionModel()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    next_state, sampled = model.step(
        state,
        action=0,
        seed=1,
    )

    assert next_state != state
    assert sampled.scenario_id == "REF_UNIFORM_SUPPORTED"


def test_same_seed_reproduces_transition():
    model = StochasticTransitionModel()

    state = ResistanceState(
        (0, 0, 0, 0, 0, 0, 0)
    )

    next_state_1, sampled_1 = model.step(
        state,
        action=0,
        seed=42,
    )

    next_state_2, sampled_2 = model.step(
        state,
        action=0,
        seed=42,
    )

    assert next_state_1 == next_state_2
    assert sampled_1 == sampled_2


def test_no_candidates_preserve_state():
    model = StochasticTransitionModel(
        candidate_generator=EmptyCandidateGenerator()
    )

    state = ResistanceState(
        (1, 1, 1, 1, 1, 1, 1)
    )

    next_state, sampled = model.step(
        state,
        action=0,
        seed=42,
    )

    assert next_state == state
    assert sampled.candidate.outcome == "no_change"
    assert sampled.candidates == ()
    assert sampled.probability == 1.0