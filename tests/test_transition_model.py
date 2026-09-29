from simulation.resistance_state import ResistanceState
from simulation.transition_model import TransitionModel, TransitionResult


class IdentityTransitionModel:
    def step(
        self,
        state: ResistanceState,
        action: int,
        seed: int | None = None,
    ) -> TransitionResult:
        return TransitionResult(
            next_state=state,
            outcome="no_change",
            source_ids=("simulation_fixture",),
        )


def test_transition_model_contract_accepts_state_action_and_seed():
    model: TransitionModel = IdentityTransitionModel()
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    result = model.step(state, action=0, seed=42)

    assert isinstance(result, TransitionResult)
    assert result.next_state == state
    assert result.outcome == "no_change"
    assert result.source_ids == ("simulation_fixture",)


def test_transition_model_does_not_mutate_input_state():
    model: TransitionModel = IdentityTransitionModel()
    state = ResistanceState((0, 0, 0, 0, 0, 0, 0))

    model.step(state, action=0, seed=42)

    assert state == ResistanceState((0, 0, 0, 0, 0, 0, 0))


def test_transition_result_contains_valid_next_state():
    model: TransitionModel = IdentityTransitionModel()
    state = ResistanceState((1, 0, 0, 0, 0, 0, 0))

    result = model.step(state, action=1, seed=42)

    assert isinstance(result.next_state, ResistanceState)
    assert len(result.next_state.resistance) == 7