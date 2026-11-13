from dataclasses import replace

import numpy as np
import pytest
import torch

from experiments.evidence_environment import PROFILES, VARIANTS, EvidenceDQN, EvidenceEnvironment, EvidenceKernel
from experiments.evidence_aware_study import common_complete, evaluate, observation, summarize, train_study
from ml.src.masked_dqn import masked_bootstrap


@pytest.fixture(scope="module")
def kernel():
    return EvidenceKernel(VARIANTS["supported"])


def test_masks_match_generator_for_every_state_action_and_retain_neutral(kernel):
    for profile in PROFILES:
        for action, bit in enumerate(profile):
            expected = not bit and bool(kernel.candidates.get((profile, action)))
            assert kernel.mask(profile)[action] == expected
    assert sum(not profile[a] and not kernel.mask(profile)[a] for profile in PROFILES for a in range(7)) == 64
    assert [p for p in PROFILES if kernel.boundary(p)] == [(1, 1, 1, 1, 1, 1, 0)]
    assert len(kernel.manifest()["training_profiles"]) == 126
    env = EvidenceEnvironment(kernel)
    env.reset(options={"initial_resistance_state": (0, 0, 0, 1, 0, 1, 1)})
    for _ in range(8):
        _, _, _, _, info = env.step(0)
        assert info["transition_status"] == "neutral"
        assert not info["evidence_boundary"]
    with pytest.raises(RuntimeError):
        env.step(0)


def test_fallback_loop_is_rejected_but_applicable_fosfomycin_is_allowed(kernel):
    env = EvidenceEnvironment(kernel)
    env.reset()
    with pytest.raises(ValueError, match="no applicable"):
        env.step(2)
    env.reset(options={"initial_resistance_state": (0, 0, 0, 1, 0, 0, 0)})
    _, reward, _, _, info = env.step(2)
    assert info["transition_status"] == "collateral_sensitivity"
    assert reward == 0
    assert env.episode.resistance_state.resistance == (0,) * 7
    assert not env.action_masks()[2]


def test_boundary_is_pessimistic_not_an_invented_resistance_transition(kernel):
    env = EvidenceEnvironment(kernel)
    env.reset(options={"initial_resistance_state": (0, 1, 1, 1, 1, 1, 0)})
    _, reward, terminated, truncated, info = env.step(6)
    assert terminated and not truncated
    assert env.episode.resistance_state.resistance == (1, 1, 1, 1, 1, 1, 0)
    assert not env.action_masks().any()
    assert info["uncertainty_continuation_cost"] == 7
    assert info["observed_burden"] == pytest.approx(6 / 7)
    assert reward == pytest.approx(-6 / 7 - 7)
    assert info["unobserved_steps"] == 7
    penalized = EvidenceKernel(replace(kernel.spec, repetition_penalty=0.1))
    assert penalized.spec.boundary_cost(7) == pytest.approx(7.7)


def test_exact_solver_has_correct_one_step_value_and_conservative_bound(kernel):
    one_step = EvidenceKernel(replace(kernel.spec, horizon=1))
    # TMP has two unique neutral outcomes and one XR outcome at the susceptible state.
    assert one_step.optimal((0,) * 7, None, 1) == pytest.approx(1 / 21)
    assert one_step.select_optimal((0,) * 7, None, 1) == 3
    for profile in PROFILES:
        assert 0 <= kernel.optimal(profile, None, 8) <= kernel.spec.boundary_cost(8) + 1e-10
    assert kernel.optimal((1,) * 7, None, 8) == 8
    assert kernel.optimal((1, 1, 1, 1, 1, 1, 0), None, 8) == 8


def test_repetition_cost_does_not_change_recorded_burden_or_transitions(kernel):
    penalized = EvidenceKernel(replace(kernel.spec, repetition_penalty=0.1))
    normal, changed = EvidenceEnvironment(kernel), EvidenceEnvironment(penalized)
    profile = (0, 0, 0, 1, 0, 1, 1)
    for env in (normal, changed):
        env.reset(seed=1, options={"initial_resistance_state": profile})
    for step in range(2):
        _, base_reward, _, _, base_info = normal.step(0)
        _, penalized_reward, _, _, altered_info = changed.step(0)
        assert normal.episode.resistance_state == changed.episode.resistance_state
        assert base_info["observed_burden"] == altered_info["observed_burden"]
        assert penalized_reward == pytest.approx(base_reward - (0.1 if step else 0))


def test_dqn_masks_exploration_warmup_bootstrap_and_checkpoint(tmp_path, kernel):
    torch.set_num_threads(1)
    env = EvidenceEnvironment(kernel)
    model = EvidenceDQN("MlpPolicy", env, evidence_mask_table=kernel.mask_table, gamma=1, seed=23)
    with torch.no_grad():
        for parameter in model.q_net.parameters():
            parameter.zero_()
        model.q_net.q_net[-1].bias[2] = 10000  # Unsupported FOS must never win.
    obs = observation((0,) * 7, None, 0)
    assert int(model.predict(obs, deterministic=True)[0]) != 2
    model.exploration_rate = 1.0
    model._last_obs = np.stack([obs])
    for _ in range(30):
        assert int(model.predict(obs)[0]) != 2
        assert model._sample_action(learning_starts=100)[0][0] != 2
    states = torch.tensor(np.stack([obs, observation((1, 1, 1, 1, 1, 1, 0), 6, 1)]))
    q = torch.zeros((2, 7))
    q[0, 2] = 10000
    masks = model._action_masks(states)
    torch.testing.assert_close(masked_bootstrap(q, states, torch.tensor([[0.], [1.]]), action_masks=masks), torch.zeros((2, 1)))
    with pytest.raises(ValueError, match="nonterminal replay"):
        masked_bootstrap(q, states, torch.zeros((2, 1)), action_masks=masks)
    model.save(tmp_path / "model.zip")
    restored = EvidenceDQN.load(tmp_path / "model.zip", device="cpu")
    np.testing.assert_array_equal(restored.evidence_mask_table, kernel.mask_table)
    assert int(restored.predict(obs, deterministic=True)[0]) != 2
    env.close()


def test_partial_evaluations_have_no_full_horizon_burden_and_no_favorable_score(kernel):
    def choose(profile, previous, step, rng):
        return 6 if profile == (0, 1, 1, 1, 1, 1, 0) else kernel.select_optimal(profile, previous, 8 - step)
    records = evaluate(kernel, choose, (600001,))
    initial_boundary = next(r for r in records if r["profile"] == "1111110")
    assert initial_boundary["actions"] == 0
    assert initial_boundary["pessimistic_score"] == 8
    assert initial_boundary["observed_burden"] == 0
    assert initial_boundary["full_horizon_burden"] is None
    reached_boundary = next(r for r in records if r["profile"] == "0111110")
    assert reached_boundary["actions"] == 1
    assert reached_boundary["full_horizon_burden"] is None
    assert reached_boundary["final_options"] is None
    assert reached_boundary["observed_burden"] == pytest.approx(6 / 7)
    assert reached_boundary["pessimistic_score"] == pytest.approx(6 / 7 + 7)
    assert all(r["unsupported_steps"] == 0 for r in records)
    assert summarize(records)["completion_rate"] < 1
    paired = common_complete({"first": records, "second": records})
    assert paired["episodes"] < paired["total_episodes"] == 128
    assert paired["burden"]["first"] == paired["burden"]["second"]


def test_full_study_requires_completed_pilot_before_creating_outputs(tmp_path):
    with pytest.raises(ValueError, match="requires --pilot-dir"):
        train_study("full", "supported", tmp_path / "full")
    assert not (tmp_path / "full").exists()


def test_legacy_variant_preserves_the_original_fallback():
    kernel = EvidenceKernel(VARIANTS["legacy"])
    env = EvidenceEnvironment(kernel)
    env.reset()
    for _ in range(8):
        _, reward, _, _, info = env.step(2)
        assert reward == 0 and info["transition_status"] == "unsupported_no_candidate"
