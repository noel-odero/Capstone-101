from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from itertools import product
import json
import platform
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

import numpy as np

from ml.src.ppo_training import PPOConfig, environment_manifest, load_ppo_model, make_training_environment
from ml.src.ppo_visualizations import generate_evaluation_plots
from simulation.resistance_state import ANTIBIOTICS, ResistanceState


def _state_label(profile: Sequence[int]) -> str:
    return "".join("R" if value else "S" for value in profile)


def _validate_observation(environment, observation: np.ndarray) -> None:
    if not np.isfinite(observation).all() or not environment.observation_space.contains(observation):
        raise ValueError("Evaluation observation is nonfinite or outside the declared observation space.")


def _package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not-installed"


def canonical_initial_profiles() -> tuple[ResistanceState, ...]:
    return tuple(ResistanceState(tuple(profile)) for profile in product((0, 1), repeat=len(ANTIBIOTICS)))


def _default_profiles() -> tuple[ResistanceState, ...]:
    return canonical_initial_profiles()


def _checkpoint_training_metadata(model_path: str | Path, config: PPOConfig) -> tuple[dict | None, dict | None]:
    checkpoint_path = Path(model_path)
    run_directory = checkpoint_path.parent.parent if checkpoint_path.parent.name == "checkpoints" else checkpoint_path.parent
    config_path = run_directory / "config.json"
    summary_path = run_directory / "training_summary.json"
    if not config_path.exists():
        return None, None
    with config_path.open(encoding="utf-8") as config_file:
        training_config = json.load(config_file)
    if training_config.get("scenario_id") != config.scenario_id:
        raise ValueError("Evaluation scenario must match the checkpoint's training scenario.")
    if training_config.get("horizon") != config.horizon:
        raise ValueError("Evaluation horizon must match the checkpoint's training horizon.")
    training_summary = None
    if summary_path.exists():
        with summary_path.open(encoding="utf-8") as summary_file:
            training_summary = json.load(summary_file)
    return training_config, training_summary


def evaluate_ppo(
    model_path: str | Path,
    config: PPOConfig,
    output_dir: str | Path,
    *,
    initial_states: Sequence[ResistanceState | Sequence[int]] | None = None,
) -> dict[str, Any]:
    config.__post_init__()
    profiles = _default_profiles() if initial_states is None else tuple(
        state if isinstance(state, ResistanceState) else ResistanceState(tuple(state))
        for state in initial_states
    )
    if not profiles:
        raise ValueError("Evaluation requires at least one initial resistance profile.")

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Evaluation output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    training_config, training_summary = _checkpoint_training_metadata(model_path, config)
    environment = make_training_environment(config)
    model = load_ppo_model(model_path, device=config.device)
    if model.action_space != environment.action_space:
        environment.close()
        raise ValueError("Checkpoint action space does not match the evaluation environment.")
    if model.observation_space != environment.observation_space:
        environment.close()
        raise ValueError("Checkpoint observation space does not match the evaluation environment.")

    traces = []
    try:
        for episode_id, initial_state in enumerate(profiles):
            environment_seed = config.evaluation_seed + episode_id
            observation, reset_info = environment.reset(
                seed=environment_seed,
                options={"initial_resistance_state": initial_state},
            )
            _validate_observation(environment, observation)
            current_episode = environment.episode
            if current_episode is None:
                raise RuntimeError("Reset did not create an episode state.")

            initial_profile = current_episode.resistance_state.resistance
            initially_terminal = environment.episode_termination.is_terminated(current_episode)
            terminal_reward_adjustment = (
                -float(config.horizon)
                if initially_terminal and all(initial_profile)
                else 0.0
            )
            cumulative_reward = terminal_reward_adjustment
            step_traces = []
            terminated = initially_terminal
            truncated = False

            while not (terminated or truncated):
                current_episode = environment.episode
                if current_episode is None:
                    raise RuntimeError("Environment lost its current episode state.")
                current_state = current_episode.resistance_state.resistance
                mask = environment.action_masks()
                if not mask.any():
                    raise RuntimeError("Nonterminal evaluation state has no feasible actions.")
                feasible_ids = tuple(int(action) for action in np.flatnonzero(mask))
                feasible_names = tuple(ANTIBIOTICS[action] for action in feasible_ids)
                _validate_observation(environment, observation)

                action_value, _ = model.predict(
                    observation,
                    deterministic=True,
                    action_masks=mask,
                )
                action = int(np.asarray(action_value).reshape(-1)[0])
                if action not in feasible_ids:
                    raise RuntimeError("MaskablePPO selected an infeasible action.")

                next_observation, reward, terminated, truncated, info = environment.step(action)
                _validate_observation(environment, next_observation)
                next_episode = environment.episode
                if next_episode is None:
                    raise RuntimeError("Environment lost its next episode state.")
                next_state = next_episode.resistance_state.resistance
                cumulative_reward += float(reward)
                step_traces.append({
                    "step": len(step_traces),
                    "current_state": _state_label(current_state),
                    "current_resistance_count": sum(current_state),
                    "feasible_actions": list(feasible_names),
                    "feasible_action_ids": list(feasible_ids),
                    "selected_action": action,
                    "selected_antibiotic_name": ANTIBIOTICS[action],
                    "was_action_effective": bool(info["effective"]),
                    "transition_type": info["transition_status"],
                    "transition_sources": info.get("source_ids", []),
                    "next_state": _state_label(next_state),
                    "next_resistance_count": sum(next_state),
                    "reward": float(reward),
                    "cumulative_reward": cumulative_reward,
                    "terminated": bool(terminated),
                    "truncated": bool(truncated),
                    "transition_seed": info.get("transition_seed"),
                    "transition_info": dict(info),
                })
                observation = next_observation
                if len(step_traces) > config.horizon:
                    raise RuntimeError("Evaluation exceeded the configured horizon.")

            final_profile = (
                environment.episode.resistance_state.resistance
                if environment.episode is not None
                else initial_profile
            )
            effective_steps = sum(trace["was_action_effective"] for trace in step_traces)
            emergence_events = sum(
                trace["next_resistance_count"] > trace["current_resistance_count"]
                for trace in step_traces
            )
            traces.append({
                "episode_id": episode_id,
                "environment_seed": environment_seed,
                "initial_state": _state_label(initial_profile),
                "initial_resistance_profile": list(initial_profile),
                "initially_terminal": initially_terminal,
                "reset_info": reset_info,
                "steps": step_traces,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "termination_reason": (
                    "no_effective_antibiotic"
                    if terminated and all(final_profile)
                    else "maximum_horizon"
                    if terminated and len(step_traces) == config.horizon
                    else "terminated"
                    if terminated
                    else "truncated"
                ),
                "terminal_reward_adjustment": terminal_reward_adjustment,
                "cumulative_reward": cumulative_reward,
                "cumulative_resistance_burden": -cumulative_reward,
                "treatment_steps": len(step_traces),
                "treatment_effectiveness_rate": (
                    effective_steps / len(step_traces) if step_traces else None
                ),
                "resistance_emergence_events": emergence_events,
                "resistance_emergence_rate": (
                    emergence_events / len(step_traces) if step_traces else None
                ),
                "final_resistance_profile": list(final_profile),
                "final_resistant_count": sum(final_profile),
                "action_counts": [
                    sum(trace["selected_action"] == action for trace in step_traces)
                    for action in range(len(ANTIBIOTICS))
                ],
            })
    finally:
        environment.close()

    action_counts = [
        sum(episode["action_counts"][action] for episode in traces)
        for action in range(len(ANTIBIOTICS))
    ]
    step_count = sum(episode["treatment_steps"] for episode in traces)
    effective_steps = sum(
        sum(step["was_action_effective"] for step in episode["steps"])
        for episode in traces
    )
    transition_count = sum(len(episode["steps"]) for episode in traces)
    emergence_events = sum(episode["resistance_emergence_events"] for episode in traces)
    result = {
        "algorithm": "MaskablePPO",
        "model_path": str(model_path),
        "training_config": training_config,
        "training_summary": training_summary,
        "evaluation_config": {
            "scenario_id": config.scenario_id,
            "horizon": config.horizon,
            "evaluation_seed": config.evaluation_seed,
            "initial_resistance_profiles": [list(profile.resistance) for profile in profiles],
            "deterministic_inference": True,
        },
        "environment_manifest": environment_manifest(config),
        "software_versions": {
            "python": platform.python_version(),
            "stable_baselines3": _package_version("stable-baselines3"),
            "sb3_contrib": _package_version("sb3-contrib"),
            "torch": _package_version("torch"),
            "gymnasium": _package_version("gymnasium"),
        },
        "reward_specification": {
            "objective": "normalized_resistance_burden",
            "normalization": len(ANTIBIOTICS),
            "terminal_convention": "all_resistant_state_persists_to_horizon",
        },
        "action_masking": True,
        "deterministic_inference": True,
        "scenario_id": config.scenario_id,
        "horizon": config.horizon,
        "evaluation_seed": config.evaluation_seed,
        "episode_count": len(traces),
        "summary": {
            "mean_return": mean(episode["cumulative_reward"] for episode in traces),
            "mean_cumulative_resistance_burden": mean(
                episode["cumulative_resistance_burden"] for episode in traces
            ),
            "treatment_effectiveness_rate": effective_steps / transition_count if transition_count else None,
            "resistance_emergence_events": emergence_events,
            "resistance_emergence_rate": emergence_events / transition_count if transition_count else None,
            "mean_final_resistant_count": mean(episode["final_resistant_count"] for episode in traces),
            "final_resistant_count_distribution": {
                str(count): sum(episode["final_resistant_count"] == count for episode in traces)
                for count in range(len(ANTIBIOTICS) + 1)
            },
            "action_counts": {
                antibiotic: action_counts[action]
                for action, antibiotic in enumerate(ANTIBIOTICS)
            },
            "treatment_steps": step_count,
        },
        "episodes": traces,
    }
    with (output_dir / "evaluation_results.json").open("w", encoding="utf-8") as result_file:
        json.dump(result, result_file, indent=2, allow_nan=False)
    with (output_dir / "decision_traces.json").open("w", encoding="utf-8") as trace_file:
        json.dump(traces, trace_file, indent=2, allow_nan=False)
    generate_evaluation_plots(result, output_dir / "plots")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a mask-aware PPO checkpoint.")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evaluation-seed", type=int)
    parser.add_argument("--initial-states-json")
    args = parser.parse_args()
    config = PPOConfig.from_json(args.config)
    if args.evaluation_seed is not None:
        config = PPOConfig.from_dict({**config.to_dict(), "evaluation_seed": args.evaluation_seed})
    initial_states = None
    if args.initial_states_json:
        with Path(args.initial_states_json).open(encoding="utf-8") as state_file:
            initial_states = json.load(state_file)
    result = evaluate_ppo(args.model_path, config, args.output_dir, initial_states=initial_states)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
