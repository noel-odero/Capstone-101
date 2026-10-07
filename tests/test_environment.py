import numpy as np
import pytest

from simulation.episode import EpisodeState
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.episode_termination import EpisodeTermination
from simulation.environment import AntibioticEnvironment
from simulation.candidate_transition import CandidateTransition
from simulation.resistance_state import ResistanceState
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_sampler import TransitionSampler


class RecordingEpisodeStep(EpisodeStep):
    result = None

    def execute(self, *args, **kwargs):
        self.result = super().execute(*args, **kwargs)
        return self.result


class EmptyCandidateGenerator:
    def generate(self, _state, _action):
        return ()


class FixedCandidateGenerator:
    def __init__(self, candidate):
        self.candidate = candidate

    def generate(self, _state, _action):
        return (self.candidate,)


@pytest.mark.parametrize(
    ("initial_state", "action", "status", "resistance_change"),
    [
        ((0, 0, 0, 0, 0, 0, 0), 1, "cross_resistance", 1),
        ((0, 0, 1, 1, 1, 1, 1), 0, "collateral_sensitivity", -1),
        ((0, 1, 0, 0, 0, 0, 0), 3, "neutral", 0),
        ((0, 0, 0, 0, 0, 0, 0), 2, "unsupported_no_candidate", 0),
    ],
)
def test_stochastic_observation_matches_true_state_after_transition(
    initial_state, action, status, resistance_change
):
    environment = AntibioticEnvironment()
    initial_observation, _ = environment.reset(
        seed=42,
        options={"initial_resistance_state": initial_state},
    )
    assert np.array_equal(initial_observation[:7], initial_state)

    observation, _, terminated, truncated, info = environment.step(action)

    assert environment.episode is not None
    actual_state = environment.episode.resistance_state
    assert info["transition_status"] == status
    assert sum(actual_state.resistance) - sum(initial_state) == resistance_change
    assert np.array_equal(observation[:7], actual_state.resistance)
    assert np.array_equal(observation[:7], environment._observation()[:7])
    assert environment.observation_space.contains(observation)
    assert observation[14] == 1
    assert not terminated and not truncated
    if resistance_change == 0:
        assert np.array_equal(observation[:7], initial_observation[:7])
    environment.close()


def test_environment_has_correct_action_space():
    environment = AntibioticEnvironment()

    assert environment.action_space.n == 7


def test_environment_has_correct_observation_space():
    environment = AntibioticEnvironment()

    assert environment.observation_space.shape == (15,)


def test_reset_returns_initial_observation():
    environment = AntibioticEnvironment()

    observation, info = environment.reset(seed=42)

    assert observation.shape == (15,)
    assert observation.dtype == np.float32
    assert info == {}


def test_initial_observation_is_fully_susceptible():
    environment = AntibioticEnvironment()

    observation, _ = environment.reset(seed=42)

    susceptibility = observation[:7]
    last_action = observation[7:14]
    treatment_step = observation[14]

    assert np.array_equal(
        susceptibility,
        np.zeros(7),
    )

    assert np.array_equal(
        last_action,
        np.zeros(7),
    )

    assert treatment_step == 0


def test_action_mask_tracks_current_susceptibility():
    environment = AntibioticEnvironment()
    assert environment.action_masks().all()

    environment.reset(options={"initial_resistance_state": (1, 0, 1, 0, 0, 0, 0)})
    assert environment.action_masks().tolist() == [False, True, False, True, True, True, True]

    environment.reset(options={"initial_resistance_state": (1,) * 7})
    assert not environment.action_masks().any()


def test_reset_accepts_valid_initial_resistance_state():
    environment = AntibioticEnvironment()

    observation, _ = environment.reset(
        seed=42,
        options={"initial_resistance_state": (1, 0, 1, 0, 0, 0, 0)},
    )

    assert np.array_equal(
        observation[:7],
        np.array([1, 0, 1, 0, 0, 0, 0]),
    )
    assert environment.episode == EpisodeState(
        ResistanceState((1, 0, 1, 0, 0, 0, 0))
    )


@pytest.mark.parametrize(
    "initial_state",
    [
        (1, 0),
        (0, 0, 0, 0, 0, 0, 2),
        "0000000",
        None,
    ],
)
def test_reset_rejects_invalid_initial_resistance_state(initial_state):
    environment = AntibioticEnvironment()

    with pytest.raises((TypeError, ValueError)):
        environment.reset(
            options={"initial_resistance_state": initial_state}
        )


def test_reset_rejects_unknown_or_malformed_options():
    environment = AntibioticEnvironment()

    with pytest.raises(ValueError, match="Unsupported reset options"):
        environment.reset(options={"initial_state": (0,) * 7})

    with pytest.raises(TypeError, match="dictionary"):
        environment.reset(options=(0,) * 7)


def test_reset_reproducible_for_same_seed_and_initial_state():
    options = {"initial_resistance_state": (1, 0, 0, 0, 0, 0, 0)}
    first = AntibioticEnvironment()
    second = AntibioticEnvironment()

    first.reset(seed=18, options=options)
    second.reset(seed=18, options=options)
    first_result = first.step(1)
    second_result = second.step(1)

    assert np.array_equal(first_result[0], second_result[0])
    assert first_result[1:] == second_result[1:]


def test_step_returns_gymnasium_transition():
    environment = AntibioticEnvironment()

    environment.reset(seed=42)

    observation, reward, terminated, truncated, info = (
        environment.step(0)
    )

    assert observation.shape == (15,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_transition_metadata_survives_to_info_and_matches_step_result():
    episode_step = RecordingEpisodeStep()
    progression = EpisodeProgression(episode_step=episode_step)
    environment = AntibioticEnvironment(episode_progression=progression)
    environment.reset(seed=42)

    observation, reward, _, _, info = environment.step(0)
    result = episode_step.result

    assert result is not None
    assert np.array_equal(
        observation,
        np.asarray(result.observation.to_vector(), dtype=np.float32),
    )
    assert reward == result.reward
    assert info["effective"] == result.treatment.effective
    assert info["scenario_id"] == result.sampled_transition.scenario_id
    assert info["transition_status"] == result.sampled_transition.status
    assert info["transition_seed"] == result.sampled_transition.seed
    assert info["source_ids"] == list(
        result.sampled_transition.candidate.source_ids
    )
    assert sum(
        candidate["scenario_probability"]
        for candidate in info["candidate_scenario_probabilities"]
    ) + info["no_transition_probability"] == pytest.approx(1.0)


def test_no_candidate_status_is_exposed_in_info():
    transition_model = StochasticTransitionModel(
        candidate_generator=EmptyCandidateGenerator()
    )
    progression = EpisodeProgression(
        episode_step=EpisodeStep(transition_model=transition_model)
    )
    environment = AntibioticEnvironment(episode_progression=progression)
    environment.reset(seed=42)

    _, _, _, _, info = environment.step(2)

    assert info["transition_status"] == "unsupported_no_candidate"
    assert info["selected_outcome"] is None
    assert info["source_ids"] == []


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    [
        ("cross_resistance", "no_transition"),
        ("neutral", "neutral"),
    ],
)
def test_sensitivity_status_is_exposed_in_info(outcome, expected_status):
    candidate = CandidateTransition(
        target_drug="GENTAMICIN",
        outcome=outcome,
        source_ids=("TEST_SOURCE",),
    )
    transition_model = StochasticTransitionModel(
        candidate_generator=FixedCandidateGenerator(candidate),
        sampler=TransitionSampler("SENSITIVITY_Q_000"),
    )
    progression = EpisodeProgression(
        episode_step=EpisodeStep(transition_model=transition_model)
    )
    environment = AntibioticEnvironment(episode_progression=progression)
    environment.reset(seed=42)

    _, _, _, _, info = environment.step(0)

    assert info["transition_status"] == expected_status
    assert info["scenario_id"] == "SENSITIVITY_Q_000"
    assert info["candidate_scenario_probabilities"][0]["source_ids"] == [
        "TEST_SOURCE"
    ]


def test_step_records_selected_action():
    environment = AntibioticEnvironment()

    environment.reset(seed=42)

    observation, _, _, _, info = environment.step(2)

    assert np.array_equal(
        observation[7:14],
        np.array([0, 0, 1, 0, 0, 0, 0]),
    )

    assert info["antibiotic"] == "FOSFOMYCIN"


def test_step_increments_treatment_step():
    environment = AntibioticEnvironment()

    environment.reset(seed=42)

    observation, _, _, _, _ = environment.step(0)

    assert observation[14] == 1


@pytest.mark.parametrize(
    ("action", "exception"),
    [
        (0.9, TypeError),
        (-1, ValueError),
        (7, ValueError),
        ("0", TypeError),
        (None, TypeError),
        (True, TypeError),
    ],
)
def test_step_rejects_malformed_or_noninteger_actions(action, exception):
    environment = AntibioticEnvironment()
    environment.reset(seed=42)

    with pytest.raises(exception):
        environment.step(action)


def test_step_accepts_numpy_integer_action():
    environment = AntibioticEnvironment()
    environment.reset(seed=42)

    _, _, _, _, info = environment.step(np.int64(0))

    assert info["antibiotic"] == "CIPROFLOXACIN"


def test_custom_termination_horizon_matches_observation_space():
    environment = AntibioticEnvironment(
        max_steps=2,
        episode_termination=EpisodeTermination(max_steps=4),
    )
    observation, _ = environment.reset(seed=42)

    assert environment.observation_space.high[-1] == 4
    assert environment.observation_space.contains(observation)

    for step in range(1, 5):
        observation, _, terminated, _, _ = environment.step(2)
        assert environment.observation_space.contains(observation)
        assert terminated is (step == 4)


def test_constructor_horizon_matches_termination_and_space():
    environment = AntibioticEnvironment(max_steps=3)
    observation, _ = environment.reset(seed=42)

    assert environment.observation_space.high[-1] == 3
    assert environment.observation_space.contains(observation)

    for step in range(1, 4):
        observation, _, terminated, _, _ = environment.step(2)
        assert environment.observation_space.contains(observation)
        assert terminated is (step == 3)


def test_step_before_reset_is_rejected():
    environment = AntibioticEnvironment()

    with pytest.raises(RuntimeError):
        environment.step(0)