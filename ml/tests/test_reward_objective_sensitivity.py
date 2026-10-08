from copy import deepcopy

import pytest

from ml.src.reward_objective_sensitivity import (
    OBJECTIVES,
    _profile_means,
    _examples,
    _winner,
    score_episode_objectives,
)
from simulation.resistance_state import ResistanceState
from simulation.reward import RewardFunction
from simulation.transition_sampler import REFERENCE_SCENARIO_ID


def make_episode(profiles, *, horizon=8, terminal_reward_adjustment=0.0):
    steps = []
    for index, (before, after) in enumerate(zip(profiles, profiles[1:])):
        before = tuple(before)
        after = tuple(after)
        action = next(action for action, resistant in enumerate(before) if not resistant)
        info = {
            "scenario_id": REFERENCE_SCENARIO_ID,
            "effective": True,
            "antibiotic": ("CIPROFLOXACIN", "NITROFURANTOIN", "FOSFOMYCIN", "TRIMETHOPRIM", "GENTAMICIN", "MECILLINAM", "CEFTAZIDIME")[action],
            "transition_status": "unsupported_no_candidate",
        }
        remaining = horizon - index - 1
        reward = -sum(after) / 7
        if sum(after) == 7:
            reward -= remaining
        steps.append({
            "observation": [*before, *([0] * 7), index],
            "action": action,
            "next_observation": [*after, *(int(action == selected) for selected in range(7)), index + 1],
            "reward": reward,
            "terminated": index == len(profiles) - 2,
            "truncated": False,
            "info": info,
        })
    return {
        "initial_resistance_profile": list(profiles[0]),
        "final_resistance_profile": list(profiles[-1]),
        "steps": steps,
        "terminal_reward_adjustment": terminal_reward_adjustment,
    }


def test_four_objective_formulas_and_reward_scale_equivalence():
    episode = make_episode([
        (0, 0, 0, 0, 0, 0, 0),
        (1, 0, 0, 0, 0, 0, 0),
        (1, 1, 0, 0, 0, 0, 0),
        (1, 0, 0, 0, 0, 0, 0),
    ])
    original = deepcopy(episode)
    scores = score_episode_objectives(episode)
    assert tuple(name for name in scores if name in OBJECTIVES) == OBJECTIVES
    assert scores["A_normalized_burden"] == pytest.approx(-(1 + 2 + 1) / 7)
    assert scores["B_unnormalized_burden"] == pytest.approx(7 * scores["A_normalized_burden"])
    assert scores["C_emergence_only"] == -2.0
    assert scores["D_terminal_resistance"] == pytest.approx(-1 / 7)
    assert scores["D_reward_sequence"] == [0.0, 0.0, -1 / 7]
    assert episode == original


def test_canonical_baseline_uses_the_existing_reward_and_terminal_tail():
    initial = (1, 1, 1, 1, 1, 1, 0)
    episode = make_episode([initial, (1,) * 7])
    scores = score_episode_objectives(episode)
    assert scores["A_normalized_burden"] == RewardFunction().calculate(
        ResistanceState((1,) * 7), remaining_horizon_steps=7,
    )
    assert scores["A_normalized_burden"] == -8.0
    assert scores["B_unnormalized_burden"] == -56.0
    assert scores["C_emergence_only"] == -1.0
    assert scores["D_terminal_resistance"] == -1.0
    assert scores["D_reward_sequence"] == [-1.0]


def test_initial_all_resistant_zero_action_terminal_scores_are_explicit():
    episode = make_episode([(1,) * 7], terminal_reward_adjustment=-8.0)
    scores = score_episode_objectives(episode)
    assert scores["A_normalized_burden"] == -8.0
    assert scores["B_unnormalized_burden"] == -56.0
    assert scores["C_emergence_only"] == 0.0
    assert scores["D_terminal_resistance"] == -1.0
    assert scores["D_reward_sequence"] == []
    assert scores["D_terminal_reward_adjustment"] == -1.0
    assert scores["transition_count"] == 0


def test_emergence_objective_does_not_penalize_existing_resistance_or_reductions():
    episode = make_episode([
        (1, 1, 0, 0, 0, 0, 0),
        (1, 0, 0, 0, 0, 0, 0),
        (1, 0, 0, 0, 0, 0, 0),
    ])
    scores = score_episode_objectives(episode)
    assert scores["C_emergence_only"] == 0.0
    assert scores["A_normalized_burden"] < 0


@pytest.mark.parametrize("invalid", [
    {"initial_resistance_profile": [0] * 7, "final_resistance_profile": [0] * 7, "steps": [{"observation": [0.5] + [0] * 14, "next_observation": [0] * 15, "action": 0, "reward": 0, "info": {"scenario_id": REFERENCE_SCENARIO_ID, "effective": True, "antibiotic": "CIPROFLOXACIN"}}]},
    {"initial_resistance_profile": [0] * 7, "final_resistance_profile": [0] * 7, "steps": [{"observation": [0] * 15, "next_observation": [0] * 15, "action": 0, "reward": 0, "info": {"scenario_id": "SENSITIVITY_Q_050", "effective": True, "antibiotic": "CIPROFLOXACIN"}}]},
])
def test_invalid_state_or_unsupported_transition_condition_is_rejected(invalid):
    with pytest.raises(ValueError):
        score_episode_objectives(invalid)


def test_infeasible_action_discontinuous_trajectory_and_short_horizon_are_rejected():
    infeasible = make_episode([(1, 0, 0, 0, 0, 0, 0), (1, 0, 0, 0, 0, 0, 0)])
    infeasible["steps"][0]["action"] = 0
    with pytest.raises(ValueError, match="infeasible"):
        score_episode_objectives(infeasible)
    discontinuous = make_episode([(0,) * 7, (0, 0, 1, 0, 0, 0, 0)])
    discontinuous["final_resistance_profile"] = [0] * 7
    with pytest.raises(ValueError, match="final profile"):
        score_episode_objectives(discontinuous)
    valid = make_episode([(0,) * 7, (0,) * 7])
    with pytest.raises(ValueError, match="[Hh]orizon"):
        score_episode_objectives(valid, horizon=0)


def test_profile_pairing_uses_one_profile_mean_and_correct_return_sign():
    cases = []
    for profile_index in range(128):
        for seed in range(25):
            row = {
                "profile_index": profile_index,
                    "initial_profile": f"profile-{profile_index:03d}",
                "ppo_cumulative_resistance_burden": 1.0,
                "greedy_cumulative_resistance_burden": 1.0,
                "greedy_minus_ppo_burden": 0.0,
                "ppo_final_resistant_antibiotics": 2.0,
                "greedy_final_resistant_antibiotics": 2.0,
                "ppo_resistance_emergence_rate": 0.0,
                "greedy_resistance_emergence_rate": 0.0,
            }
            for objective in OBJECTIVES:
                row[f"ppo_{objective}_return"] = 0.0
                row[f"greedy_{objective}_return"] = 1.0 if profile_index == 0 else -1.0 if profile_index == 1 else 0.0
            cases.append(row)
    profiles = _profile_means(cases)
    baseline = [row for row in profiles if row["objective"] == OBJECTIVES[0]]
    assert len(baseline) == 128
    assert baseline[0]["return_winner"] == "Greedy"
    assert baseline[1]["return_winner"] == "PPO"
    assert _winner(0.0) == "tied"


def test_actual_trajectory_example_selection_preserves_stored_profile_schema():
    episode = make_episode([
        (0, 0, 0, 0, 0, 0, 0),
        (1, 0, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 0, 0),
    ])
    record = {
        "training_seed": 1000, "evaluation_seed_base": 100001,
        "profile_index": 0, "case_id": "seed_100001_profile_000",
        "initial_profile": "SSSSSSS",
        "objective_scores": {"ppo": {"A_normalized_burden": -1 / 7}, "greedy": {"A_normalized_burden": 0}},
        "source_trajectories": {
            "initial_state": "SSSSSSS", "ppo": episode,
            "greedy": {**make_episode([(0,) * 7]), "steps": []},
        },
    }
    examples = _examples([record])
    transient = examples["transient_increase_then_decrease"]
    assert transient["initial_profile"] == "SSSSSSS"
    assert transient["resistant_count_path"] == [0, 1, 0]
