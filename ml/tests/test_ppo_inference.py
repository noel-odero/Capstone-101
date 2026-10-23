import json
from itertools import product
import numpy as np
import pytest
from gymnasium.spaces import Discrete

import ml.src.ppo_inference as inference
from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.ppo_inference import (
    CANDIDATES_AVAILABLE_STATUS,
    DEFAULT_MANIFEST_PATH,
    NO_CANDIDATE_STATUS,
    CheckpointIntegrityError,
    ContractMismatchError,
    EmptyActionMaskError,
    FrozenPolicyInferenceEngine,
    InferenceContext,
    InfeasibleActionError,
    InvalidContextError,
    TerminalStateError,
    load_frozen_engine,
    load_manifest,
    verify_checkpoint_sha256,
)
from ml.src.ppo_training import PPOConfig, load_ppo_model, make_training_environment
from simulation.environment import AntibioticEnvironment
from simulation.resistance_state import ANTIBIOTICS
from simulation.transition_generator import CandidateTransitionGenerator

EXPECTED_SHA256 = "1747b68cb572cc320c7c53ae105dfa9dd6827f689839b35c4f2bcf9520384001"
ALL_PROFILES = tuple(product((0, 1), repeat=len(ANTIBIOTICS)))
GENTAMICIN, CIPROFLOXACIN = ANTIBIOTICS.index("GENTAMICIN"), ANTIBIOTICS.index("CIPROFLOXACIN")


class FirstFeasiblePolicy:
    """Records every observation it receives and picks the lowest-id susceptible action."""

    def __init__(self):
        self.observations = []

    def select_action(self, observation):
        self.observations.append(np.array(observation))
        return int(np.flatnonzero(observation[:7] == 0)[0])


class FixedActionPolicy:
    def __init__(self, action):
        self.action = action
        self.calls = 0

    def select_action(self, observation):
        self.calls += 1
        return self.action


class FakeMaskableModel:
    """Stands in for MaskablePPO.predict: returns the highest feasible action."""

    def __init__(self):
        self.calls = []

    def predict(self, observation, deterministic, action_masks):
        self.calls.append((np.array(observation), deterministic, np.array(action_masks)))
        return np.array([int(np.flatnonzero(action_masks)[-1])]), None


@pytest.fixture(scope="module")
def generator():
    return CandidateTransitionGenerator()


def make_engine(policy, generator, horizon=8):
    return FrozenPolicyInferenceEngine(
        policy=policy,
        candidate_generator=generator,
        horizon=horizon,
        model_id="test_model",
        checkpoint_sha256="0" * 64,
    )


def initial_context(profile=(0,) * 7):
    return InferenceContext(tuple(profile), None, 0)


# --- observation construction and validation -------------------------------------------------


def test_observation_layout_is_resistance_then_last_action_then_step():
    observation = InferenceContext((0, 1, 0, 0, 1, 0, 0), last_action=4, treatment_step=3).to_observation()

    assert observation.dtype == np.float32 and observation.shape == (15,)
    assert observation.tolist() == [0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 3]


def test_initial_context_encodes_zero_last_action_like_reset():
    environment = AntibioticEnvironment()
    reset_observation, _ = environment.reset(options={"initial_resistance_state": (1, 0, 0, 0, 0, 1, 0)})

    context = initial_context((1, 0, 0, 0, 0, 1, 0))

    assert np.array_equal(context.to_observation(), reset_observation)


@pytest.mark.parametrize(
    "profile",
    [(0,) * 6, (0,) * 8, (0, 0, 0, 0, 0, 0, 2), (0, 0, 0, 0, 0, 0, -1), (True,) + (0,) * 6,
     (1.0,) + (0,) * 6, "0000000", None, 5],
)
def test_invalid_resistance_profiles_are_rejected(profile):
    with pytest.raises(InvalidContextError):
        InferenceContext(profile, None, 0)


@pytest.mark.parametrize(
    ("last_action", "treatment_step"),
    [(7, 1), (-1, 1), (True, 1), (1.5, 1), ("1", 1), (None, 1), (3, 0), (3, -1), (3, True),
     (3, 1.5), (3, "1"), (None, -1)],
)
def test_invalid_action_and_step_combinations_are_rejected(last_action, treatment_step):
    with pytest.raises(InvalidContextError):
        InferenceContext((0,) * 7, last_action, treatment_step)


def test_numpy_integers_are_normalized_to_plain_ints():
    context = InferenceContext(np.zeros(7, dtype=np.int64), np.int64(2), np.int64(1))

    assert all(type(value) is int for value in context.resistance_profile)
    assert type(context.last_action) is int and type(context.treatment_step) is int


@pytest.mark.parametrize(
    "observation",
    [
        np.zeros(14), np.zeros(16), np.full(15, np.nan), [0.5] + [0] * 14,
        [-1] + [0] * 14, [0] * 7 + [1, 1] + [0] * 5 + [1], [0] * 7 + [2] + [0] * 7,
        "not-a-vector", [[0] * 15],
    ],
)
def test_malformed_observations_are_rejected(observation):
    with pytest.raises(InvalidContextError):
        InferenceContext.from_observation(observation)


# --- context preservation against the real simulator -------------------------------------------


def test_context_round_trips_every_environment_observation():
    environment = AntibioticEnvironment()
    observation, _ = environment.reset(seed=3, options={"initial_resistance_state": (0, 1, 0, 0, 0, 0, 0)})
    steps_seen = 0
    terminated = False
    while not terminated:
        context = InferenceContext.from_observation(observation)
        assert np.array_equal(context.to_observation(), observation)
        assert context.treatment_step == steps_seen
        observation, _, terminated, _, _ = environment.step(int(np.flatnonzero(environment.action_masks())[0]))
        steps_seen += 1
    assert InferenceContext.from_observation(observation).treatment_step == steps_seen


def test_engine_receives_full_context_at_every_simulated_step(generator):
    policy = FirstFeasiblePolicy()
    engine = make_engine(policy, generator)
    environment = AntibioticEnvironment()
    observation, _ = environment.reset(seed=11, options={"initial_resistance_state": (0,) * 7})
    previous_action = None
    terminated = False
    step = 0
    while not terminated:
        result = engine.recommend(InferenceContext.from_observation(observation))
        assert np.array_equal(policy.observations[-1], observation)
        assert result.context.last_action == previous_action
        assert result.context.treatment_step == step
        previous_action = result.action_id
        observation, _, terminated, _, _ = environment.step(result.action_id)
        step += 1
    assert len(policy.observations) == step
    with pytest.raises(TerminalStateError):
        engine.recommend(InferenceContext.from_observation(observation))


# --- feasibility mask and deterministic inference ------------------------------------------------


def test_mask_matches_environment_for_every_profile():
    environment = AntibioticEnvironment()
    for profile in ALL_PROFILES:
        observation, _ = environment.reset(options={"initial_resistance_state": profile})
        mask = inference._feasibility_mask(initial_context(profile).resistance_state)
        assert np.array_equal(mask, environment.action_masks())
        assert np.array_equal(mask, observation[:7] == 0)


def test_recommendation_is_feasible_named_and_repeatable(generator):
    engine = make_engine(FirstFeasiblePolicy(), generator)
    context = InferenceContext((1, 1, 0, 0, 1, 0, 1), last_action=3, treatment_step=2)

    first, second = engine.recommend(context), engine.recommend(context)

    assert first == second
    assert first.action_id in first.feasible_action_ids
    assert first.feasible_action_ids == (2, 3, 5)
    assert first.feasible_antibiotics == ("FOSFOMYCIN", "TRIMETHOPRIM", "MECILLINAM")
    assert first.antibiotic == ANTIBIOTICS[first.action_id] == "FOSFOMYCIN"
    assert first.observation == tuple(float(v) for v in context.to_observation())


def test_real_policy_adapter_uses_deterministic_masked_prediction(generator):
    model = FakeMaskableModel()
    policy = MaskablePPOObservationPolicy(Discrete(7), model)
    engine = make_engine(policy, generator)

    result = engine.recommend(InferenceContext((1, 0, 0, 1, 0, 0, 0), last_action=0, treatment_step=1))

    observation, deterministic, mask = model.calls[0]
    assert deterministic is True
    assert mask.tolist() == [False, True, True, False, True, True, True]
    assert observation[7] == 1 and observation[14] == 1
    assert result.action_id == 6 and result.antibiotic == "CEFTAZIDIME"


def test_infeasible_policy_action_is_an_error_not_a_substitution(generator):
    engine = make_engine(FixedActionPolicy(0), generator)

    with pytest.raises(InfeasibleActionError):
        engine.recommend(InferenceContext((1, 0, 0, 0, 0, 0, 0), last_action=1, treatment_step=1))


def test_adapter_infeasible_prediction_propagates(generator):
    class BadModel:
        def predict(self, observation, deterministic, action_masks):
            return np.array([0]), None

    engine = make_engine(MaskablePPOObservationPolicy(Discrete(7), BadModel()), generator)

    with pytest.raises(RuntimeError):
        engine.recommend(InferenceContext((1, 0, 0, 0, 0, 0, 0), last_action=1, treatment_step=1))


def test_empty_mask_on_nonterminal_context_is_explicit(generator, monkeypatch):
    policy = FixedActionPolicy(0)
    engine = make_engine(policy, generator)
    monkeypatch.setattr(inference, "_feasibility_mask", lambda state: np.zeros(7, dtype=bool))

    with pytest.raises(EmptyActionMaskError):
        engine.recommend(initial_context())
    assert policy.calls == 0


# --- terminal and out-of-range states ---------------------------------------------------------


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        (InferenceContext((1,) * 7, None, 0), "no_effective_antibiotic"),
        (InferenceContext((1,) * 7, 2, 4), "no_effective_antibiotic"),
        (InferenceContext((1,) * 7, 2, 8), "no_effective_antibiotic"),
        (InferenceContext((0,) * 7, 2, 8), "maximum_horizon"),
    ],
)
def test_terminal_states_raise_without_calling_the_policy(generator, context, reason):
    policy = FixedActionPolicy(0)

    with pytest.raises(TerminalStateError) as error:
        make_engine(policy, generator).recommend(context)

    assert error.value.reason == reason
    assert policy.calls == 0


def test_engine_never_recommends_after_the_environment_reports_termination(generator):
    profiles = [(0,) * 7, (1, 1, 1, 1, 1, 1, 0), (1, 0, 1, 1, 1, 1, 1), (0, 1, 0, 1, 0, 1, 0)]
    for seed, profile in enumerate(profiles):
        engine = make_engine(FirstFeasiblePolicy(), generator)
        environment = AntibioticEnvironment()
        observation, _ = environment.reset(seed=seed, options={"initial_resistance_state": profile})
        rng = np.random.default_rng(seed)
        terminated = False
        while not terminated:
            engine.recommend(InferenceContext.from_observation(observation))
            choice = int(rng.choice(np.flatnonzero(environment.action_masks())))
            observation, _, terminated, _, _ = environment.step(choice)
        with pytest.raises(TerminalStateError):
            engine.recommend(InferenceContext.from_observation(observation))


def test_environment_reset_into_all_resistant_profile_is_terminal_for_the_engine(generator):
    environment = AntibioticEnvironment()
    observation, _ = environment.reset(options={"initial_resistance_state": (1,) * 7})
    policy = FixedActionPolicy(0)

    assert environment.episode_termination.is_terminated(environment.episode)
    with pytest.raises(TerminalStateError):
        make_engine(policy, generator).recommend(InferenceContext.from_observation(observation))
    assert policy.calls == 0


def test_terminal_and_invalid_context_errors_are_distinct_types():
    assert not issubclass(TerminalStateError, InvalidContextError)
    assert not issubclass(InvalidContextError, TerminalStateError)


def test_step_beyond_horizon_and_non_context_are_invalid(generator):
    engine = make_engine(FixedActionPolicy(0), generator)

    with pytest.raises(InvalidContextError):
        engine.recommend(InferenceContext((0,) * 7, 1, 9))
    with pytest.raises(InvalidContextError):
        engine.recommend({"resistance_profile": (0,) * 7})


# --- transition support ---------------------------------------------------------------------------


@pytest.mark.parametrize("drug", ["GENTAMICIN", "FOSFOMYCIN", "CEFTAZIDIME"])
def test_public_data_provides_candidates_for_previously_unsupported_drugs(generator, drug):
    engine = make_engine(FixedActionPolicy(0), generator)
    action = ANTIBIOTICS.index(drug)

    assert any(
        engine.has_candidate_transition(initial_context(p), action)
        for p in ALL_PROFILES if p[action] == 0
    )


def test_result_reports_transition_status_for_selected_action(generator):
    context = initial_context()

    unsupported = make_engine(FixedActionPolicy(ANTIBIOTICS.index("FOSFOMYCIN")), generator).recommend(context)
    supported = make_engine(FixedActionPolicy(CIPROFLOXACIN), generator).recommend(context)

    assert (unsupported.transition_status, unsupported.has_candidate_transition) == (NO_CANDIDATE_STATUS, False)
    assert (supported.transition_status, supported.has_candidate_transition) == (CANDIDATES_AVAILABLE_STATUS, True)


@pytest.mark.parametrize(
    "profile", [(0,) * 7, (1, 0, 0, 0, 0, 0, 0), (0, 1, 0, 1, 0, 0, 0), (1, 0, 1, 0, 1, 0, 1)]
)
def test_reported_support_agrees_with_simulator_step(generator, profile):
    engine = make_engine(FixedActionPolicy(0), generator)
    environment = AntibioticEnvironment()
    for action in np.flatnonzero(initial_context(profile).to_observation()[:7] == 0):
        observation, _ = environment.reset(seed=5, options={"initial_resistance_state": profile})
        context = InferenceContext.from_observation(observation)
        _, _, _, _, info = environment.step(int(action))
        has_candidate = engine.has_candidate_transition(context, int(action))

        assert (info["transition_status"] != NO_CANDIDATE_STATUS) == has_candidate
        if not has_candidate:
            assert environment.episode.resistance_state.resistance == profile


# --- manifest and checkpoint hash ---------------------------------------------------------------------


def write_manifest(tmp_path, **overrides):
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    for dotted_key, value in overrides.items():
        section, _, key = dotted_key.partition(".")
        if key:
            manifest[section][key] = value
        else:
            manifest[section] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_committed_manifest_pins_selected_public_data_ppo_contract():
    manifest = load_manifest()

    assert manifest.model_id == "ppo_public_v2_seed_19000"
    assert manifest.checkpoint_sha256 == EXPECTED_SHA256.lower()
    assert manifest.checkpoint_path.as_posix().endswith("artifacts/frozen/public-data-v2/ppo/final_model.zip")
    assert (manifest.horizon, manifest.scenario_id) == (8, "REF_UNIFORM_SUPPORTED")


def test_manifest_with_reordered_actions_is_rejected(tmp_path):
    reordered = list(ANTIBIOTICS)
    reordered[0], reordered[1] = reordered[1], reordered[0]

    with pytest.raises(ContractMismatchError):
        load_manifest(write_manifest(tmp_path, **{"simulator.action_names": reordered}))


def test_manifest_with_tampered_observation_layout_is_rejected(tmp_path):
    with pytest.raises(ContractMismatchError):
        load_manifest(write_manifest(tmp_path, **{"observation.layout": {"treatment_step": [0, 1]}}))


@pytest.mark.parametrize(
    "override",
    [
        {"simulator.interaction_data_sha256": "0" * 64},
        {"simulator.scenario_id": "SENSITIVITY_Q_050"},
        {"simulator.horizon": 9},
        {"simulator.interaction_data_path": "data/versions/interactions-v1/empirical_interactions.csv"},
    ],
)
def test_loader_rejects_manifest_that_disagrees_with_live_simulator_or_training_config(tmp_path, override):
    if not load_manifest().checkpoint_path.is_file():
        pytest.skip("Frozen seed 12000 checkpoint is not present.")

    with pytest.raises(ContractMismatchError):
        load_frozen_engine(write_manifest(tmp_path, **override))


def test_manifest_missing_a_section_is_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest_version": 1}), encoding="utf-8")

    with pytest.raises(ContractMismatchError):
        load_manifest(path)


def test_hash_verification_accepts_matching_file_case_insensitively(tmp_path):
    import hashlib

    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"frozen-checkpoint-bytes")
    digest = hashlib.sha256(b"frozen-checkpoint-bytes").hexdigest()

    assert verify_checkpoint_sha256(checkpoint, digest.upper()) == digest


def test_hash_mismatch_reports_both_values_and_missing_file_fails(tmp_path):
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"tampered")

    with pytest.raises(CheckpointIntegrityError, match=EXPECTED_SHA256.lower()):
        verify_checkpoint_sha256(checkpoint, EXPECTED_SHA256)
    with pytest.raises(CheckpointIntegrityError, match="not found"):
        verify_checkpoint_sha256(tmp_path / "missing.zip", EXPECTED_SHA256)


def test_loader_rejects_wrong_hash_before_loading_the_model(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"not the frozen checkpoint")
    manifest = write_manifest(tmp_path, **{"checkpoint": {"path": str(checkpoint), "sha256": EXPECTED_SHA256}})

    def forbidden(*args, **kwargs):
        raise AssertionError("The model must not be loaded after a hash mismatch.")

    monkeypatch.setattr(inference, "_load_model_from_bytes", forbidden)

    with pytest.raises(CheckpointIntegrityError):
        load_frozen_engine(manifest)


def test_loader_wires_verified_model_into_engine(tmp_path, monkeypatch):
    import hashlib

    payload = b"stand-in checkpoint"
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = write_manifest(tmp_path, **{"checkpoint": {"path": str(checkpoint), "sha256": digest}})
    reference = AntibioticEnvironment()
    model = FakeMaskableModel()
    model.action_space, model.observation_space = reference.action_space, reference.observation_space
    loaded = []
    monkeypatch.setattr(
        inference, "_load_model_from_bytes", lambda data, device: loaded.append((data, device)) or model
    )

    engine = load_frozen_engine(manifest)

    assert loaded == [(payload, "cpu")]  # the verified bytes, never a path that could be swapped
    assert engine.checkpoint_sha256 == digest and engine.horizon == 8
    assert engine.recommend(initial_context()).action_id == 6

    model.observation_space = Discrete(3)
    with pytest.raises(ContractMismatchError):
        load_frozen_engine(manifest)


def test_engine_is_loaded_once_per_process(monkeypatch):
    loads = []
    monkeypatch.setattr(inference, "load_frozen_engine", lambda path: loads.append(path) or object())
    inference._load_cached.cache_clear()
    try:
        first, second = inference.get_frozen_engine(), inference.get_frozen_engine()
    finally:
        inference._load_cached.cache_clear()

    assert first is second and len(loads) == 1


# --- the real frozen checkpoint (small; skipped if the artifact is absent) --------------------------------


@pytest.fixture(scope="module")
def real_engine():
    if not load_manifest().checkpoint_path.is_file():
        pytest.skip("Frozen seed 12000 checkpoint is not present.")
    return load_frozen_engine()


def test_real_checkpoint_matches_pinned_hash_and_audited_first_action(real_engine):
    result = real_engine.recommend(initial_context())

    assert real_engine.checkpoint_sha256 == EXPECTED_SHA256.lower()
    assert (result.action_id, result.antibiotic) == (2, "FOSFOMYCIN")
    assert result.transition_status == NO_CANDIDATE_STATUS


def test_byte_loaded_checkpoint_matches_path_loaded_checkpoint(real_engine):
    path_policy = MaskablePPOObservationPolicy(
        Discrete(7), load_ppo_model(load_manifest().checkpoint_path, device="cpu")
    )
    for profile in ALL_PROFILES:
        if all(profile):
            continue
        for context in (
            initial_context(profile),
            InferenceContext(profile, last_action=2, treatment_step=3),
        ):
            assert real_engine.recommend(context).action_id == path_policy.select_action(
                context.to_observation()
            )


@pytest.mark.parametrize("profile", [(0,) * 7, (1, 0, 0, 1, 0, 0, 1)])
def test_real_checkpoint_is_deterministic_feasible_and_context_preserving(real_engine, profile):
    environment = make_training_environment(PPOConfig(interaction_data_path=load_manifest().interaction_data_path))
    observation, _ = environment.reset(seed=100001, options={"initial_resistance_state": profile})
    terminated, steps = False, 0
    while not terminated:
        context = InferenceContext.from_observation(observation)
        result = real_engine.recommend(context)

        assert result == real_engine.recommend(context)
        assert result.observation == tuple(float(v) for v in observation)
        assert environment.action_masks()[result.action_id]
        observation, _, terminated, _, info = environment.step(result.action_id)
        assert (info["transition_status"] != NO_CANDIDATE_STATUS) == result.has_candidate_transition
        steps += 1
    assert steps == 8 and InferenceContext.from_observation(observation).treatment_step == 8
    with pytest.raises(TerminalStateError):
        real_engine.recommend(InferenceContext.from_observation(observation))
