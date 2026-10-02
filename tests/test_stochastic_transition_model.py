from simulation.resistance_state import ResistanceState
from simulation.stochastic_transition_model import StochasticTransitionModel


class EmptyCandidateGenerator:
    def generate(self, _state, _action):
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
    assert sampled.candidate is None
    assert sampled.status == "unsupported_no_candidate"
    assert sampled.candidates == ()
    assert sampled.probability is None
    assert sampled.no_transition_probability is None


def test_sensitivity_no_transition_preserves_state_and_status():
    from simulation.transition_sampler import TransitionSampler

    model = StochasticTransitionModel(
        candidate_generator=EmptyCandidateGenerator(),
        sampler=TransitionSampler("SENSITIVITY_Q_050"),
    )
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    next_state, sampled = model.step(state, action=0, seed=42)

    assert next_state == state
    assert sampled.status == "unsupported_no_candidate"


def test_sensitivity_gate_no_transition_is_distinct_from_neutral():
    from simulation.candidate_transition import CandidateTransition
    from simulation.transition_sampler import TransitionSampler

    class OneResistanceCandidateGenerator:
        def generate(self, _state, _action):
            return (CandidateTransition("GENTAMICIN", "cross_resistance", ("A",)),)

    model = StochasticTransitionModel(
        candidate_generator=OneResistanceCandidateGenerator(),
        sampler=TransitionSampler("SENSITIVITY_Q_000"),
    )
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    next_state, sampled = model.step(state, action=0, seed=42)

    assert next_state == state
    assert sampled.status == "no_transition"
    assert sampled.candidate is None