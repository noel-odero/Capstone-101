from copy import deepcopy

import pytest

from simulation.candidate_transition import CandidateTransition
from simulation.episode_progression import EpisodeProgression
from simulation.episode_step import EpisodeStep
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_sampler import TransitionSampler
from ml.src.evaluation_runner import run_evaluation
from ml.src.greedy_policy import GreedyPolicy
from ml.src.random_policy import RandomPolicy
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ResistanceState


class FixedPolicy:
    def __init__(self, action_space, seed=None):
        self.seed = seed

    def select_action(self, observation):
        return 2


class ScriptedEnvironment(AntibioticEnvironment):
    def __init__(self, mode="terminated"):
        super().__init__(max_steps=2)
        self.mode = mode
        self.shared_info = {}

    def step(self, action):
        self.episode = self.episode.advance(self.episode.resistance_state)
        step = self.episode.treatment_step
        self.last_action = tuple(int(index == action) for index in range(7))
        self.shared_info.update({
            "antibiotic": "FOSFOMYCIN", "effective": True,
            "transition_status": "unsupported_no_candidate",
            "scenario_id": "REF_UNIFORM_SUPPORTED",
            "source_ids": [], "candidate_scenario_probabilities": [],
            "transition_seed": step,
        })
        return (
            self._observation(), float(step),
            self.mode == "terminated" and step == 2,
            self.mode == "truncated" and step == 1,
            self.shared_info,
        )


@pytest.mark.parametrize("policy_factory", [RandomPolicy, GreedyPolicy])
def test_real_policies_run_multiple_reproducible_episodes(policy_factory):
    initial_states = [(0,) * 7, (1, 0, 0, 1, 0, 0, 0), (0, 1, 0, 0, 0, 0, 0)]
    first = run_evaluation(
        AntibioticEnvironment(), policy_factory, 3,
        environment_seed=42, policy_seed=18, initial_states=initial_states,
    )
    second = run_evaluation(
        AntibioticEnvironment(), policy_factory, 3,
        environment_seed=42, policy_seed=18, initial_states=initial_states,
    )
    assert first == second
    assert first.scenario_id == "REF_UNIFORM_SUPPORTED"
    assert len(first.episodes) == 3
    for index, episode in enumerate(first.episodes):
        assert episode.episode_id == index
        assert episode.environment_seed == 42 + index
        assert episode.policy_seed == 18 + index
        assert episode.initial_resistance_profile == initial_states[index]
        assert episode.observations[0][:7] == initial_states[index]
        assert episode.observations[-1][:7] == episode.final_resistance_profile
        assert len(episode.observations) == episode.treatment_step_count + 1
        assert 1 <= episode.treatment_step_count <= 8
        assert episode.terminated or episode.truncated
        for step in episode.steps:
            assert 0 <= step.action < 7
            assert step.info["scenario_id"] == first.scenario_id
            assert "candidate_scenario_probabilities" in step.info
            assert "source_ids" in step.info
            if policy_factory is GreedyPolicy:
                assert step.observation[step.action] == 0
                assert step.info["effective"] is True


def test_single_episode_records_sequences_sums_and_independent_metadata():
    environment = ScriptedEnvironment()
    result = run_evaluation(environment, FixedPolicy, 1)
    episode = result.episodes[0]
    assert episode.actions == (2, 2)
    assert episode.antibiotics == ("FOSFOMYCIN", "FOSFOMYCIN")
    assert episode.rewards == (1.0, 2.0)
    assert episode.cumulative_reward == 3.0
    assert episode.treatment_step_count == 2
    assert episode.effectiveness == (True, True)
    assert episode.terminated and not episode.truncated
    assert episode.termination_reason == "maximum_horizon"
    assert episode.steps[0].info["transition_seed"] == 1
    environment.shared_info["source_ids"].append("LATER_MUTATION")
    assert episode.steps[0].info["source_ids"] == []
    assert episode.steps[1].info["source_ids"] == []
    assert episode.steps[0].observation == episode.initial_observation
    assert episode.steps[1].observation == episode.steps[0].next_observation


def test_stops_on_truncation():
    result = run_evaluation(ScriptedEnvironment(mode="truncated"), FixedPolicy, 1)
    episode = result.episodes[0]
    assert episode.truncated and not episode.terminated
    assert episode.termination_reason == "truncated"
    assert episode.treatment_step_count == 1


def test_resistance_exhaustion_terminates_before_horizon():
    class ExhaustingEnvironment(ScriptedEnvironment):
        def step(self, action):
            self.episode = self.episode.advance(ResistanceState((1,) * 7))
            return self._observation(), -1.0, True, False, {
                "antibiotic": "FOSFOMYCIN",
                "effective": True,
                "transition_status": "cross_resistance",
            }

    episode = run_evaluation(ExhaustingEnvironment(), FixedPolicy, 1).episodes[0]
    assert episode.treatment_step_count == 1
    assert episode.termination_reason == "no_effective_antibiotic"
    assert episode.final_resistance_profile == (1,) * 7


def test_sensitivity_configuration_and_provenance_are_preserved():
    class CandidateGenerator:
        def generate(self, _state, _action):
            return (CandidateTransition("GENTAMICIN", "cross_resistance", ("TEST",)),)

    model = StochasticTransitionModel(
        candidate_generator=CandidateGenerator(),
        sampler=TransitionSampler("SENSITIVITY_Q_000"),
    )
    progression = EpisodeProgression(episode_step=EpisodeStep(transition_model=model))
    environment = AntibioticEnvironment(max_steps=1, episode_progression=progression)
    result = run_evaluation(environment, FixedPolicy, 1)
    info = result.episodes[0].steps[0].info

    assert result.scenario_id == "SENSITIVITY_Q_000"
    assert info["transition_status"] == "no_transition"
    assert info["no_transition_probability"] == 1.0
    assert info["candidate_scenario_probabilities"][0]["source_ids"] == ["TEST"]
    assert environment.episode_progression is progression
    assert model.sampler.scenario_id == "SENSITIVITY_Q_000"


def test_initially_terminal_episode_has_no_policy_action():
    class NoActionPolicy(FixedPolicy):
        def select_action(self, observation):
            raise AssertionError("An initially terminal episode must not request an action")

    result = run_evaluation(
        AntibioticEnvironment(), NoActionPolicy, 1,
        initial_states=[ResistanceState((1,) * 7)],
    )
    episode = result.episodes[0]
    assert episode.terminated and not episode.truncated
    assert episode.termination_reason == "no_effective_antibiotic"
    assert episode.treatment_step_count == 0
    assert episode.actions == episode.rewards == episode.effectiveness == ()
    assert episode.cumulative_reward == 0.0
    assert len(episode.observations) == 1
    assert episode.initial_resistance_profile == episode.final_resistance_profile == (1,) * 7


def test_fresh_policy_per_episode_with_documented_seed():
    created = []

    def factory(action_space, seed):
        policy = RandomPolicy(action_space, seed=seed)
        created.append(policy)
        return policy

    result = run_evaluation(ScriptedEnvironment(), factory, 3, policy_seed=100)
    assert len({id(policy) for policy in created}) == 3
    for episode in result.episodes:
        control = RandomPolicy(AntibioticEnvironment().action_space, seed=episode.policy_seed)
        assert episode.actions == tuple(control.select_action() for _ in range(2))


def test_runner_does_not_consume_extra_environment_rng_or_reconfigure():
    environment = AntibioticEnvironment(max_steps=2)
    control = AntibioticEnvironment(max_steps=2)
    config = (environment.action_space, environment.episode_progression,
              environment.episode_termination, environment.reward_function)
    unrelated_policy = RandomPolicy(environment.action_space, seed=51)
    unrelated_rng = deepcopy(unrelated_policy._random.getstate())
    result = run_evaluation(environment, FixedPolicy, 1, environment_seed=42)
    control.reset(seed=42)
    for action in result.episodes[0].actions:
        control.step(action)
    assert environment.np_random.bit_generator.state == control.np_random.bit_generator.state
    assert config == (environment.action_space, environment.episode_progression,
                      environment.episode_termination, environment.reward_function)
    assert unrelated_policy._random.getstate() == unrelated_rng


@pytest.mark.parametrize(("count", "exception"), [(0, ValueError), (-1, ValueError), (True, TypeError), (1.5, TypeError)])
def test_invalid_episode_count(count, exception):
    with pytest.raises(exception):
        run_evaluation(AntibioticEnvironment(), RandomPolicy, count)


@pytest.mark.parametrize("kwargs", [
    {"environment_seed": -1}, {"policy_seed": -1},
    {"initial_states": []}, {"initial_states": [(0, 1)]},
    {"initial_states": [(0, 0, 0, 0, 0, 0, 2)]},
])
def test_invalid_configuration(kwargs):
    environment = AntibioticEnvironment()
    with pytest.raises(ValueError):
        run_evaluation(environment, RandomPolicy, 1, **kwargs)
    assert environment.episode is None


@pytest.mark.parametrize("kwargs", [
    {"environment_seed": True}, {"policy_seed": None},
    {"policy_seed": 1.5}, {"initial_states": "0000000"},
])
def test_invalid_configuration_types(kwargs):
    environment = AntibioticEnvironment()
    with pytest.raises(TypeError):
        run_evaluation(environment, RandomPolicy, 1, **kwargs)
    assert environment.episode is None


def test_factory_must_return_observation_policy():
    def invalid_factory(_action_space, seed):
        return object()

    with pytest.raises(TypeError, match="select_action"):
        run_evaluation(AntibioticEnvironment(), invalid_factory, 1)


def test_rejects_deterministic_environment_and_unseedable_policy_instance():
    with pytest.raises(TypeError, match="stochastic"):
        run_evaluation(DeterministicReferenceEnvironment(), RandomPolicy, 1)
    environment = AntibioticEnvironment()
    with pytest.raises(TypeError, match="policy_factory"):
        run_evaluation(environment, RandomPolicy(environment.action_space), 1)


def test_policy_error_propagates_without_fallback():
    class BrokenPolicy(FixedPolicy):
        def select_action(self, observation):
            raise ValueError("policy failure")

    with pytest.raises(ValueError, match="policy failure"):
        run_evaluation(AntibioticEnvironment(), BrokenPolicy, 1)


def test_nonterminating_environment_is_not_silently_truncated():
    with pytest.raises(RuntimeError, match="horizon"):
        run_evaluation(ScriptedEnvironment(mode="never"), FixedPolicy, 1)