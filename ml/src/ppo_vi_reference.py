from collections import defaultdict

import numpy as np

from simulation.decoder import decode_observation
from simulation.episode import EpisodeState
from simulation.observation import Observation
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def reference_observation(state: EpisodeState, last_action: int | None) -> np.ndarray:
    if last_action is not None and (isinstance(last_action, bool) or last_action not in range(7)):
        raise ValueError("Last action must be a canonical action ID or None.")
    observation = Observation(
        state.resistance_state.resistance,
        tuple(int(action == last_action) for action in range(7)),
        state.treatment_step,
    )
    return np.asarray(observation.to_vector(), dtype=np.float32)


def planning_state_from_observation(observation) -> EpisodeState:
    decoded = decode_observation(tuple(observation))
    return EpisodeState(
        ResistanceState(tuple(int(value) for value in decoded.susceptibility)),
        int(decoded.treatment_step),
    )


def reference_predecessor_histories(environment) -> dict[tuple[int, ...], tuple[int, ...]]:
    histories = defaultdict(set)
    if environment.max_steps < 2:
        return {}
    for state in environment.states():
        if state.treatment_step != 0 or environment.is_terminal(state):
            continue
        for action in environment.feasible_actions(state):
            next_state, _, terminal, _ = environment.transition(state, action)
            if not terminal:
                histories[next_state.resistance_state.resistance].add(action)
    return {profile: tuple(sorted(actions)) for profile, actions in histories.items()}


def compare_reference_action(environment, solution, state, ppo_action) -> dict:
    if environment.is_terminal(state):
        raise ValueError("Terminal states do not select actions.")
    feasible = environment.feasible_actions(state)
    if ppo_action not in feasible:
        raise ValueError("PPO action is infeasible in the reference state.")
    q_values = solution.action_values[state]
    optimal_value = solution.state_values[state]
    optimal_actions = tuple(action for action in feasible if q_values[action] == optimal_value)
    vi_action = solution.policy[state]
    next_state, reward, terminal, info = environment.transition(state, ppo_action)
    _, vi_reward, _, _ = environment.transition(state, vi_action)
    gap = optimal_value - q_values[ppo_action]
    if gap < 0:
        raise ValueError("Exact action gap cannot be negative.")
    if gap == 0:
        category = "exact_action_agreement" if ppo_action == vi_action else "different_action_exact_optimal_tie"
    elif gap <= 1e-12:
        category = "positive_gap_within_numerical_tolerance_not_exact_tie"
    else:
        category = "positive_reference_gap"
    return {
        "feasible_action_ids": list(feasible),
        "feasible_actions": [ANTIBIOTICS[action] for action in feasible],
        "vi_optimal_action": vi_action,
        "vi_optimal_antibiotic": ANTIBIOTICS[vi_action],
        "vi_exact_optimal_action_ids": list(optimal_actions),
        "vi_optimal_state_value": optimal_value,
        "vi_optimal_q_value": q_values[vi_action],
        "vi_feasible_q_values": {ANTIBIOTICS[action]: q_values[action] for action in feasible},
        "ppo_action": ppo_action,
        "ppo_antibiotic": ANTIBIOTICS[ppo_action],
        "ppo_immediate_reference_reward": reward,
        "vi_immediate_reference_reward": vi_reward,
        "vi_q_value_of_ppo_action": q_values[ppo_action],
        "reference_action_value_gap": gap,
        "selects_exact_optimal_action": ppo_action in optimal_actions,
        "agreement_category": category,
        "decision_value_interpretation": (
            "immediate_disadvantage_but_exact_optimal" if reward < vi_reward and gap == 0
            else "immediate_disadvantage_and_positive_reference_gap" if reward < vi_reward
            else "positive_reference_gap_without_immediate_disadvantage" if gap > 0
            else "exact_optimal_action"
        ),
        "immediate_disadvantage_vs_vi_action": reward < vi_reward,
        "ppo_next_reference_state": list(next_state.resistance_state.resistance),
        "ppo_reference_transition_type": info["transition_status"],
        "ppo_reference_transition_info": info,
        "ppo_reference_terminal": terminal,
    }