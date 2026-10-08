from copy import deepcopy
from typing import Any, Sequence

import numpy as np

from simulation.decoder import decode_observation
from simulation.episode import EpisodeState
from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def build_decision_trace(
    episode: dict,
    step_index: int,
    probabilities: Sequence[float],
    environment,
    *,
    case_id: str,
    training_seed: int,
    checkpoint_identifier: str,
    initial_treatment_step: int = 0,
) -> dict[str, Any]:
    """Validate a saved decision by pure seeded replay, without advancing an episode."""
    step = episode["steps"][step_index]
    observation = np.asarray(step["observation"], dtype=np.float32)
    next_observation = np.asarray(step["next_observation"], dtype=np.float32)
    for values in (observation, next_observation):
        if not np.isfinite(values).all() or not environment.observation_space.contains(values):
            raise ValueError("Trace observation is nonfinite or outside the environment space.")
    decoded = decode_observation(tuple(observation))
    state = ResistanceState(tuple(int(value) for value in decoded.susceptibility))
    next_state = ResistanceState(tuple(int(value) for value in next_observation[:7]))
    treatment_step = int(decoded.treatment_step)
    if treatment_step != step_index + initial_treatment_step or int(next_observation[-1]) != treatment_step + 1:
        raise ValueError("Trace time indices are inconsistent.")
    mask = np.asarray([state.is_susceptible(name) for name in ANTIBIOTICS], dtype=bool)
    probability_values = np.asarray(probabilities, dtype=float)
    if (
        probability_values.shape != mask.shape
        or not np.isfinite(probability_values).all()
        or np.any(probability_values < 0)
        or np.any(probability_values > 1)
        or not np.isclose(probability_values.sum(), 1.0, atol=1e-6, rtol=0)
        or np.any(np.abs(probability_values[~mask]) > 1e-8)
    ):
        raise ValueError("Policy probabilities must be normalized over feasible actions.")
    action = step["action"]
    if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < 7 or not mask[action]:
        raise ValueError("Selected trace action is infeasible.")
    if probability_values[action] < probability_values.max() - 1e-6:
        raise ValueError("Saved deterministic action is inconsistent with checkpoint probabilities.")
    expected_last_action = tuple(int(index == action) for index in range(7))
    if tuple(int(value) for value in next_observation[7:14]) != expected_last_action:
        raise ValueError("Next observation has an inconsistent last-action encoding.")
    if isinstance(environment, DeterministicReferenceEnvironment):
        replay_episode, expected_reward, _, replay_info = environment.transition(
            EpisodeState(state, treatment_step), action,
        )
        replay_state = replay_episode.resistance_state
        replay_status = replay_info["transition_status"]
    else:
        replay_state, sampled = environment.episode_progression.episode_step.transition_model.step(
            state, action, seed=step["info"]["transition_seed"],
        )
        expected_reward = environment.episode_progression.episode_step.reward_function.calculate(
            replay_state,
            remaining_horizon_steps=environment.episode_termination.max_steps - treatment_step - 1,
        )
        replay_status = sampled.status
    if replay_state != next_state or replay_status != step["info"]["transition_status"]:
        raise ValueError("Recorded next state or outcome differs from seeded transition replay.")
    if not np.isclose(expected_reward, step["reward"], atol=1e-10, rtol=0):
        raise ValueError("Recorded reward differs from the environment reward.")
    feasible_ids = np.flatnonzero(mask).tolist()
    next_feasible_ids = [index for index, value in enumerate(next_state.resistance) if value == 0]
    return {
        "case_id": case_id,
        "episode_id": episode["episode_id"],
        "initial_profile": list(episode["initial_resistance_profile"]),
        "initial_treatment_step": initial_treatment_step,
        "evaluation_seed": episode["environment_seed"],
        "training_seed": training_seed,
        "checkpoint_identifier": checkpoint_identifier,
        "step": treatment_step,
        "observation": observation.tolist(),
        "current_state": list(state.resistance),
        "current_resistance_count": sum(state.resistance),
        "feasible_actions": [ANTIBIOTICS[index] for index in feasible_ids],
        "action_mask": mask.tolist(),
        "policy_action_probabilities": probability_values.tolist(),
        "selected_action": action,
        "selected_antibiotic_name": ANTIBIOTICS[action],
        "reward": float(step["reward"]),
        "next_state": list(next_state.resistance),
        "next_observation": next_observation.tolist(),
        "next_resistance_count": sum(next_state.resistance),
        "remaining_feasible_actions": [ANTIBIOTICS[index] for index in next_feasible_ids],
        "transition_type": replay_status,
        "transition_info": deepcopy(step["info"]),
        "cumulative_reward": sum(item["reward"] for item in episode["steps"][:step_index + 1]),
    }