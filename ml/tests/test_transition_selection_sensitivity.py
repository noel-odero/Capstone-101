from copy import deepcopy

import numpy as np
import pytest

from ml.src.metrics import calculate_episode_metrics
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import PPOConfig
from ml.src.transition_selection_sensitivity import (
    CONDITIONS,
    DETERMINISTIC_SCENARIO_ID,
    UNIFORM_SCENARIO_ID,
    _paired_condition_rows,
    _rollout,
    _aggregate,
    _transition_sensitivity,
    _paired_policy_rows,
    _unsupported_audit,
    _environment_for_condition,
    inspect_transition_compatibility,
)
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.transition_sampler import TransitionSampler
from ml.src.ppo_visualizations import generate_transition_sensitivity_plots


class FirstFeasiblePolicy:
    def __init__(self, action_space, seed=None):
        self.action_space = action_space

    def select_action(self, observation):
        return int(np.flatnonzero(np.asarray(observation[:7]) == 0)[0])


def test_only_existing_candidate_selection_modes_are_included():
    assert CONDITIONS == (UNIFORM_SCENARIO_ID, DETERMINISTIC_SCENARIO_ID)
    assert TransitionSampler(UNIFORM_SCENARIO_ID).scenario_id == "REF_UNIFORM_SUPPORTED"
    assert DETERMINISTIC_REFERENCE_SCENARIO_ID == "REF_DETERMINISTIC_FIRST_SUPPORTED"


def test_transition_conditions_share_reward_mask_horizon_and_state_contracts():
    compatibility = inspect_transition_compatibility(PPOConfig())
    assert all(compatibility["contract_checks"].values())
    assert compatibility["contract_details"][UNIFORM_SCENARIO_ID]["horizon"] == 8
    assert compatibility["contract_details"][DETERMINISTIC_SCENARIO_ID]["reward_specification"] == {
        "objective": "normalized_resistance_burden",
        "normalization": 7,
        "terminal_convention": "all_resistant_state_persists_to_horizon",
    }
    assert "not applicable" in compatibility["conditions"][DETERMINISTIC_SCENARIO_ID]["transition_randomness"]


def test_deterministic_rollout_is_reproducible_and_does_not_mutate_config():
    config = PPOConfig()
    config_before = deepcopy(config.to_dict())
    profile = ResistanceState((0, 0, 1, 0, 0, 0, 0))
    environment_a = _environment_for_condition(DETERMINISTIC_SCENARIO_ID, config)
    environment_b = _environment_for_condition(DETERMINISTIC_SCENARIO_ID, config)
    try:
        episode_a = _rollout(environment_a, DETERMINISTIC_SCENARIO_ID, FirstFeasiblePolicy(environment_a.action_space), profile, 0, 1234, 5678, "test")
        episode_b = _rollout(environment_b, DETERMINISTIC_SCENARIO_ID, FirstFeasiblePolicy(environment_b.action_space), profile, 0, 1234, 5678, "test")
        assert episode_a == episode_b
        assert all("transition_seed" not in step.info for step in episode_a.steps)
        assert all(step.info["scenario_id"] == DETERMINISTIC_SCENARIO_ID for step in episode_a.steps)
        assert -episode_a.cumulative_reward == sum(sum(step.next_observation[:7]) / 7 for step in episode_a.steps)
        assert config.to_dict() == config_before
    finally:
        environment_a.close()
        environment_b.close()


def test_uniform_rollout_records_transition_seeds_and_metrics_match_episode():
    config = PPOConfig()
    environment = _environment_for_condition(UNIFORM_SCENARIO_ID, config)
    try:
        episode = _rollout(
            environment, UNIFORM_SCENARIO_ID, FirstFeasiblePolicy(environment.action_space),
            ResistanceState((0,) * 7), 0, 1234, 5678, "test",
        )
        metrics = calculate_episode_metrics(episode, scenario_id=UNIFORM_SCENARIO_ID)
        assert len(episode.steps) == 8
        assert all("transition_seed" in step.info for step in episode.steps)
        assert -episode.cumulative_reward == sum(sum(step.next_observation[:7]) / 7 for step in episode.steps)
        assert metrics.cumulative_reward == episode.cumulative_reward
        assert metrics.treatment_steps == 8
    finally:
        environment.close()


def test_all_128_initial_profiles_are_unique_and_include_terminal_profile():
    profiles = canonical_initial_profiles()
    assert len(profiles) == 128
    assert len({profile.resistance for profile in profiles}) == 128
    assert profiles[-1].resistance == (1,) * len(ANTIBIOTICS)


def test_cross_condition_pairing_requires_same_profile_and_policy_seed():
    common = {
        "training_seed": 1000, "evaluation_seed_base": 2000, "profile_index": 3,
        "policy": "ppo", "case_id": "1000:2000:profile_003", "initial_profile": "SSSRSSS",
        "evaluation_seed": 2003, "policy_seed": 900003,
        "cumulative_resistance_burden": 1.0,
    }
    rows = [
        {**common, "condition": UNIFORM_SCENARIO_ID},
        {**common, "condition": DETERMINISTIC_SCENARIO_ID, "cumulative_resistance_burden": 2.0},
    ]
    pair = _paired_condition_rows(rows)[0]
    assert pair["transition_effect_deterministic_minus_uniform"] == 1.0
    bad = [rows[0], {**rows[1], "evaluation_seed": 9003}]
    try:
        _paired_condition_rows(bad)
    except ValueError as error:
        assert "not paired" in str(error)
    else:
        raise AssertionError("Misaligned condition seeds must be rejected.")


def test_ppo_greedy_pairing_rejects_policy_seed_mismatch():
    rows = []
    for policy, policy_seed in (("ppo", 900003), ("greedy", 900004)):
        rows.append({
            "condition": UNIFORM_SCENARIO_ID, "training_seed": 1000,
            "evaluation_seed_base": 2000, "profile_index": 3,
            "policy": policy, "initial_profile": "SSSRSSS",
            "evaluation_seed": 2003, "policy_seed": policy_seed,
        })
    with pytest.raises(ValueError, match="not aligned"):
        _paired_policy_rows(rows, UNIFORM_SCENARIO_ID)


def test_initially_all_resistant_burden_uses_existing_terminal_convention():
    environment = DeterministicReferenceEnvironment(max_steps=8)
    try:
        episode = _rollout(
            environment, DETERMINISTIC_SCENARIO_ID, FirstFeasiblePolicy(environment.action_space),
            ResistanceState((1,) * 7), 127, 42, 24, "test",
        )
        assert episode.steps == ()
        assert episode.cumulative_reward == -8.0
        assert -episode.cumulative_reward == 8.0
    finally:
        environment.close()


def test_condition_aggregates_use_paired_burden_and_keep_hierarchy():
    rows = []
    for condition, shift in ((UNIFORM_SCENARIO_ID, 0.0), (DETERMINISTIC_SCENARIO_ID, .5)):
        for policy, burden in (("ppo", 2.0 + shift), ("greedy", 3.0 + shift)):
            rows.append({
                "condition": condition, "training_seed": 1000,
                "evaluation_seed_base": 2000, "profile_index": 0,
                "policy": policy, "case_id": "1000:2000:profile_000",
                "initial_profile": "SSSSSSS", "evaluation_seed": 2000,
                "policy_seed": 900001, "cumulative_resistance_burden": burden,
                "final_resistant_count": 1, "resistance_emergence_rate": .1,
                "effectiveness_rate": 1.0, "cumulative_reward": -burden,
                "transition_count": 8,
            })
    summary = _aggregate(rows)
    assert summary[f"{UNIFORM_SCENARIO_ID}:paired_ppo_vs_greedy"]["mean_greedy_minus_ppo_burden"] == 1.0
    assert summary[f"{DETERMINISTIC_SCENARIO_ID}:paired_ppo_vs_greedy"]["profile_direction_counts"]["ppo_better_profiles"] == 1
    assert summary["per_training_seed_schedule"]["1000"][UNIFORM_SCENARIO_ID]["2000"]["matched_case_count"] == 1
    sensitivity = _transition_sensitivity(rows, _paired_condition_rows(rows))
    assert sensitivity["ppo"]["mean_deterministic_minus_uniform_burden"] == .5
    assert sensitivity["greedy"]["mean_deterministic_minus_uniform_burden"] == .5
    assert sensitivity["ppo_vs_greedy_ranking"]["ranking_preserved"]
    assert _paired_policy_rows(rows, UNIFORM_SCENARIO_ID)[0][1]["policy"] == "greedy"


def test_transition_sensitivity_plots_render_with_matched_policy_pairs(tmp_path):
    rows = []
    for condition, status, burden_shift in (
        (UNIFORM_SCENARIO_ID, "unsupported_no_candidate", 0.0),
        (DETERMINISTIC_SCENARIO_ID, "cross_resistance", 0.5),
    ):
        for policy, burden in (("ppo", 1.0 + burden_shift), ("greedy", 2.0 + burden_shift)):
            rows.append({
                "condition": condition, "training_seed": 1000,
                "evaluation_seed_base": 2000, "profile_index": 0,
                "policy": policy, "cumulative_resistance_burden": burden,
                "initial_profile": "SSSSSSS", "evaluation_seed": 2000,
                "policy_seed": 900001, "unsupported_no_candidate_count": int(status == "unsupported_no_candidate"),
                "resistance_changing_outcome_count": int(status == "cross_resistance"),
                "unchanged_state_outcome_count": int(status == "unsupported_no_candidate"),
                "case_id": f"1000:2000:profile_000:{policy}",
                "trajectory": {"steps": [{
                    "observation": [0] * 15, "next_observation": [1] + [0] * 14,
                    "action": 0, "info": {"antibiotic": ANTIBIOTICS[0], "transition_status": status},
                }]},
                "transition_count": 1,
            })
    paired = _paired_condition_rows(rows)
    audit = _unsupported_audit(rows)
    saved = generate_transition_sensitivity_plots(rows, paired, audit, tmp_path)
    assert len(saved) == 4
    assert all((tmp_path / name.rsplit("/", 1)[-1]).exists() for name in saved)


DETERMINISTIC_REFERENCE_SCENARIO_ID = "REF_DETERMINISTIC_FIRST_SUPPORTED"