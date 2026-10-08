from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from importlib.metadata import PackageNotFoundError, version
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
from typing import Any

import gymnasium as gym
import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.utils import set_random_seed

from simulation.episode_step import EpisodeStep
from simulation.environment import AntibioticEnvironment
from simulation.episode_progression import EpisodeProgression
from simulation.resistance_state import ANTIBIOTICS
from simulation.reward import RewardSpecification
from simulation.stochastic_transition_model import StochasticTransitionModel
from simulation.transition_sampler import REFERENCE_SCENARIO_ID, SENSITIVITY_SCENARIOS, TransitionSampler
from ml.src.ppo_visualizations import generate_training_plots


def _package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not-installed"


@dataclass(frozen=True)
class PPOConfig:
    ppo_seed: int = 2026
    environment_seed: int = 31001
    evaluation_seed: int = 42001
    scenario_id: str = REFERENCE_SCENARIO_ID
    horizon: int = 8
    total_timesteps: int = 4096
    learning_rate: float = 3e-4
    n_steps: int = 256
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 1.0
    gae_lambda: float = 0.95
    ent_coef: float = 0.0
    clip_range: float = 0.2
    policy_architecture: tuple[int, ...] = (64, 64)
    training_profile_design: str = "cycle_all_nonterminal_profiles"
    evaluation_frequency: int = 2048
    evaluation_episodes: int = 16
    matched_evaluation_profile_design: str = "all_binary"
    matched_evaluation_seed_bases: tuple[int, ...] = (
        100001, 200001, 300001, 400001, 500001,
    )
    matched_policy_seed_start: int = 900001
    matched_runs_independence_assumed: bool = True
    reward_configuration: dict[str, str | int] = field(default_factory=lambda: RewardSpecification().to_dict())
    action_mask_configuration: dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "rule": "susceptible_actions_only",
    })
    device: str = "cpu"

    def __post_init__(self) -> None:
        for name in (
            "ppo_seed", "environment_seed", "evaluation_seed", "horizon",
            "total_timesteps", "n_steps", "batch_size", "n_epochs",
            "evaluation_frequency", "evaluation_episodes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < (1 if name in {
                "horizon", "total_timesteps", "n_steps", "batch_size", "n_epochs",
                "evaluation_frequency", "evaluation_episodes",
            } else 0):
                raise ValueError(f"{name} has an invalid integer value.")
        if self.gamma != 1.0:
            raise ValueError("The resistance-burden objective requires gamma=1.0.")
        for name in ("learning_rate", "gae_lambda", "ent_coef", "clip_range"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                raise ValueError(f"{name} must be finite.")
        if self.learning_rate <= 0 or not 0 <= self.gae_lambda <= 1 or self.ent_coef < 0 or self.clip_range <= 0:
            raise ValueError("PPO hyperparameters are outside their valid ranges.")
        if self.batch_size > self.n_steps or self.n_steps % self.batch_size:
            raise ValueError("batch_size must divide n_steps and not exceed it.")
        if self.total_timesteps < self.n_steps:
            raise ValueError("total_timesteps must be at least one rollout length.")
        if not isinstance(self.policy_architecture, tuple) or not self.policy_architecture or any(
            isinstance(width, bool) or not isinstance(width, int) or width <= 0
            for width in self.policy_architecture
        ):
            raise ValueError("policy_architecture must be a tuple of positive layer widths.")
        supported_scenarios = {REFERENCE_SCENARIO_ID, *SENSITIVITY_SCENARIOS}
        if self.scenario_id not in supported_scenarios:
            raise ValueError(f"Unsupported stochastic scenario: {self.scenario_id}")
        if self.device not in {"cpu", "cuda", "auto"}:
            raise ValueError("device must be cpu, cuda, or auto.")
        if self.training_profile_design not in {
            "cycle_all_nonterminal_profiles",
            "fully_susceptible",
        }:
            raise ValueError("Unsupported training initial-profile design.")
        if self.matched_evaluation_profile_design != "all_binary":
            raise ValueError("Matched evaluation must preserve the canonical all-binary profile set.")
        if not self.matched_evaluation_seed_bases:
            raise ValueError("At least one matched evaluation seed base is required.")
        matched_environment_seeds: set[int] = set()
        for seed_base in self.matched_evaluation_seed_bases:
            if isinstance(seed_base, bool) or not isinstance(seed_base, int) or seed_base < 0:
                raise ValueError("Matched evaluation seed bases must be nonnegative integers.")
            expanded = set(range(seed_base, seed_base + 128))
            if matched_environment_seeds & expanded:
                raise ValueError("Matched evaluation seed schedules must not overlap.")
            matched_environment_seeds.update(expanded)
        if any(seed in matched_environment_seeds for seed in (
            self.ppo_seed, self.environment_seed, self.evaluation_seed,
        )):
            raise ValueError("Matched evaluation seeds must be separate from PPO training/validation seeds.")
        if (
            isinstance(self.matched_policy_seed_start, bool)
            or not isinstance(self.matched_policy_seed_start, int)
            or self.matched_policy_seed_start < 0
        ):
            raise ValueError("matched_policy_seed_start must be a nonnegative integer.")
        if not isinstance(self.matched_runs_independence_assumed, bool):
            raise TypeError("matched_runs_independence_assumed must be boolean.")
        if self.reward_configuration != RewardSpecification().to_dict():
            raise ValueError("PPO config reward must match the specified normalized resistance-burden objective.")
        if self.action_mask_configuration != {
            "enabled": True,
            "rule": "susceptible_actions_only",
        }:
            raise ValueError("PPO action masking must enforce susceptible actions only.")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> PPOConfig:
        values = dict(values)
        if "policy_architecture" in values:
            values["policy_architecture"] = tuple(values["policy_architecture"])
        if "matched_evaluation_seed_bases" in values:
            values["matched_evaluation_seed_bases"] = tuple(values["matched_evaluation_seed_bases"])
        return cls(**values)

    @classmethod
    def from_json(cls, path: str | Path) -> PPOConfig:
        with Path(path).open(encoding="utf-8") as config_file:
            return cls.from_dict(json.load(config_file))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_training_environment(config: PPOConfig) -> AntibioticEnvironment:
    transition_model = StochasticTransitionModel(sampler=TransitionSampler(config.scenario_id))
    episode_step = EpisodeStep(transition_model=transition_model)
    progression = EpisodeProgression(episode_step=episode_step)
    return AntibioticEnvironment(episode_progression=progression, max_steps=config.horizon)


def training_initial_profiles(config: PPOConfig) -> tuple[tuple[int, ...], ...]:
    if config.training_profile_design == "fully_susceptible":
        return ((0,) * len(ANTIBIOTICS),)
    return tuple(
        tuple(profile)
        for profile in product((0, 1), repeat=len(ANTIBIOTICS))
        if not all(profile)
    )


def validation_initial_profiles(count: int = 16) -> tuple[tuple[int, ...], ...]:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 127:
        raise ValueError("Validation profile count must be between 1 and 127.")
    by_resistant_count = {
        resistant_count: [
            tuple(profile)
            for profile in product((0, 1), repeat=len(ANTIBIOTICS))
            if sum(profile) == resistant_count
        ]
        for resistant_count in range(len(ANTIBIOTICS))
    }
    allocations = (1, 2, 2, 4, 3, 2, 2)
    selected = []
    for resistant_count, available in by_resistant_count.items():
        quota = max(1, round(count * allocations[resistant_count] / sum(allocations)))
        quota = min(quota, len(available), count - len(selected))
        if quota <= 0:
            break
        indices = np.linspace(0, len(available) - 1, num=quota, dtype=int)
        selected.extend(available[index] for index in indices)
    return tuple(selected[:count])


def environment_manifest(config: PPOConfig) -> dict[str, Any]:
    environment = make_training_environment(config)
    try:
        generator = environment.episode_progression.episode_step.transition_model.candidate_generator
        interaction_payload = json.dumps(
            generator.interactions,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return {
            "scenario_id": config.scenario_id,
            "horizon": config.horizon,
            "action_names": list(environment.action_space_config.actions),
            "action_count": int(environment.action_space.n),
            "observation_shape": list(environment.observation_space.shape),
            "observation_low": environment.observation_space.low.tolist(),
            "observation_high": environment.observation_space.high.tolist(),
            "observation_dtype": str(environment.observation_space.dtype),
            "interaction_data_sha256": hashlib.sha256(interaction_payload).hexdigest(),
            "reward_specification": environment.reward_function.specification.to_dict(),
            "action_masking": True,
            "training_profile_design": config.training_profile_design,
            "training_profile_count": len(training_initial_profiles(config)),
            "validation_initial_profiles": [
                "".join("R" if value else "S" for value in profile)
                for profile in validation_initial_profiles(config.evaluation_episodes)
            ],
        }
    finally:
        environment.close()


class EpisodeMetricsWrapper(gym.Wrapper):
    def __init__(self, env: AntibioticEnvironment):
        super().__init__(env)
        self._initial_resistance_count = 0
        self._initial_resistance_profile = (0,) * len(ANTIBIOTICS)
        self._resistance_burden = 0.0
        self._emergence_events = 0
        self._effective_steps = 0
        self._action_counts = [0] * len(ANTIBIOTICS)
        self._episode_return = 0.0
        self._previous_resistance_count = 0

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        observation, info = self.env.reset(seed=seed, options=options)
        self._validate_observation(observation)
        episode = self.unwrapped.episode
        if episode is None:
            raise RuntimeError("Environment reset did not initialize an episode.")
        self._initial_resistance_count = sum(episode.resistance_state.resistance)
        self._initial_resistance_profile = episode.resistance_state.resistance
        self._previous_resistance_count = self._initial_resistance_count
        self._resistance_burden = 0.0
        self._emergence_events = 0
        self._effective_steps = 0
        self._action_counts = [0] * len(ANTIBIOTICS)
        self._episode_return = 0.0
        return observation, info

    def step(self, action: int):
        valid_mask = self.unwrapped.action_masks()
        if not valid_mask.any():
            raise RuntimeError("A terminal all-resistant state cannot select an action.")
        if not 0 <= int(action) < len(valid_mask) or not valid_mask[int(action)]:
            raise ValueError("PPO attempted to select an infeasible antibiotic.")

        observation, reward, terminated, truncated, info = self.env.step(action)
        self._validate_observation(observation)
        next_state = self.unwrapped.episode
        if next_state is None:
            raise RuntimeError("Environment lost its episode state after a step.")
        next_resistance_count = sum(next_state.resistance_state.resistance)
        self._resistance_burden -= float(reward)
        self._emergence_events += int(next_resistance_count > self._previous_resistance_count)
        self._effective_steps += int(bool(info["effective"]))
        self._action_counts[int(action)] += 1
        self._episode_return += float(reward)
        self._previous_resistance_count = next_resistance_count

        if terminated or truncated:
            info = dict(info)
            info["ppo_episode_metrics"] = {
                "initial_resistant_count": self._initial_resistance_count,
                "initial_resistance_profile": list(self._initial_resistance_profile),
                "final_resistant_count": next_resistance_count,
                "cumulative_resistance_burden": self._resistance_burden,
                "resistance_emergence_events": self._emergence_events,
                "effective_steps": self._effective_steps,
                "treatment_steps": sum(self._action_counts),
                "cumulative_reward": self._episode_return,
                "action_counts": self._action_counts.copy(),
            }
        return observation, reward, terminated, truncated, info

    def _validate_observation(self, observation: np.ndarray) -> None:
        if not np.isfinite(observation).all() or not self.observation_space.contains(observation):
            raise ValueError("Environment emitted a nonfinite or out-of-space observation.")


class InitialResistanceProfileWrapper(gym.Wrapper):
    """Provide a reproducible profile schedule on vectorized episode resets."""

    def __init__(
        self,
        env: gym.Env,
        profiles: tuple[tuple[int, ...], ...],
        *,
        shuffle_cycles: bool,
    ):
        super().__init__(env)
        if not profiles:
            raise ValueError("Initial profile schedule cannot be empty.")
        self.profiles = profiles
        self.shuffle_cycles = shuffle_cycles
        self._rng = np.random.default_rng()
        self._order = np.arange(len(profiles))
        self._cursor = 0

    def _new_cycle(self) -> None:
        self._order = (
            self._rng.permutation(len(self.profiles))
            if self.shuffle_cycles
            else np.arange(len(self.profiles))
        )
        self._cursor = 0

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self._rng = np.random.default_rng(seed ^ 0x5EED5EED)
            self._new_cycle()
        reset_options = {} if options is None else dict(options)
        if "initial_resistance_state" not in reset_options:
            if self._cursor >= len(self._order):
                self._new_cycle()
            profile_index = int(self._order[self._cursor])
            self._cursor += 1
            reset_options["initial_resistance_state"] = self.profiles[profile_index]
        return self.env.reset(seed=seed, options=reset_options)


def _make_profiled_vector_environment(
    config: PPOConfig,
    *,
    seed: int,
    monitor_directory: Path,
    profiles: tuple[tuple[int, ...], ...],
    shuffle_cycles: bool,
):
    def create_wrapped_environment():
        environment = make_training_environment(config)
        metrics_environment = EpisodeMetricsWrapper(environment)
        return InitialResistanceProfileWrapper(
            metrics_environment,
            profiles,
            shuffle_cycles=shuffle_cycles,
        )

    return make_vec_env(
        create_wrapped_environment,
        n_envs=1,
        seed=seed,
        monitor_dir=str(monitor_directory),
    )


class TrainingMetricsCallback(BaseCallback):
    def __init__(self, output_path: Path, total_timesteps: int, report_frequency: int):
        super().__init__(verbose=0)
        self.output_path = output_path
        self.total_timesteps = total_timesteps
        self.report_frequency = max(1, report_frequency)
        self.next_report = self.report_frequency
        self.episodes: list[dict[str, Any]] = []

    def _on_training_start(self) -> None:
        print(f"Starting MaskablePPO training: {self.total_timesteps} timesteps", flush=True)

    def _on_step(self) -> bool:
        dones = self.locals.get("dones", ())
        infos = self.locals.get("infos", ())
        for done, info in zip(dones, infos):
            if not done or "ppo_episode_metrics" not in info:
                continue
            record = dict(info["ppo_episode_metrics"])
            record["timesteps"] = self.num_timesteps
            record["episode_id"] = len(self.episodes)
            self.episodes.append(record)
            self.logger.record("train/cumulative_resistance_burden", record["cumulative_resistance_burden"])
            self.logger.record("train/final_resistant_count", record["final_resistant_count"])
            self.logger.record("train/resistance_emergence_events", record["resistance_emergence_events"])
        if self.num_timesteps >= self.next_report:
            progress = min(1.0, self.num_timesteps / self.total_timesteps)
            width = 24
            filled = round(width * progress)
            bar = "=" * filled + "-" * (width - filled)
            latest = self.episodes[-1] if self.episodes else None
            latest_metrics = (
                f" | episode return {latest['cumulative_reward']:.3f}"
                f" | burden {latest['cumulative_resistance_burden']:.3f}"
                if latest is not None
                else " | no episode completed yet"
            )
            print(
                f"PPO [{bar}] {progress:6.1%} | {self.num_timesteps}/{self.total_timesteps} steps"
                f" | {len(self.episodes)} episodes{latest_metrics}",
                flush=True,
            )
            while self.next_report <= self.num_timesteps:
                self.next_report += self.report_frequency
        return True

    def _on_training_end(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as output_file:
            json.dump(self.episodes, output_file, indent=2, allow_nan=False)
        print(f"PPO training complete: {self.num_timesteps} timesteps, {len(self.episodes)} episodes", flush=True)


def train_ppo(config: PPOConfig, output_dir: str | Path) -> dict[str, Any]:
    config.__post_init__()
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Training output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "checkpoints").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    with (output_dir / "config.json").open("w", encoding="utf-8") as config_file:
        json.dump(config.to_dict(), config_file, indent=2, allow_nan=False)
    manifest = environment_manifest(config)
    with (output_dir / "environment_manifest.json").open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2, allow_nan=False)

    set_random_seed(config.ppo_seed)
    training_env = _make_profiled_vector_environment(
        config,
        seed=config.environment_seed,
        monitor_directory=output_dir / "logs" / "training",
        profiles=training_initial_profiles(config),
        shuffle_cycles=True,
    )
    evaluation_profiles = validation_initial_profiles(config.evaluation_episodes)
    evaluation_env = _make_profiled_vector_environment(
        config,
        seed=config.evaluation_seed,
        monitor_directory=output_dir / "logs" / "evaluation",
        profiles=evaluation_profiles,
        shuffle_cycles=False,
    )
    metrics_callback = TrainingMetricsCallback(
        output_dir / "training_episodes.json",
        config.total_timesteps,
        max(config.n_steps, config.total_timesteps // 20),
    )
    evaluation_callback = MaskableEvalCallback(
        evaluation_env,
        best_model_save_path=str(output_dir / "checkpoints"),
        log_path=str(output_dir / "logs"),
        eval_freq=config.evaluation_frequency,
        n_eval_episodes=config.evaluation_episodes,
        deterministic=True,
        use_masking=True,
        verbose=1,
    )
    model = MaskablePPO(
        "MlpPolicy",
        training_env,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        gamma=config.gamma,
        gae_lambda=config.gae_lambda,
        ent_coef=config.ent_coef,
        clip_range=config.clip_range,
        policy_kwargs={"net_arch": list(config.policy_architecture)},
        tensorboard_log=None,
        seed=None,
        device=config.device,
        verbose=0,
    )
    try:
        model.learn(
            total_timesteps=config.total_timesteps,
            callback=CallbackList([metrics_callback, evaluation_callback]),
            progress_bar=False,
        )
        model.save(str(output_dir / "final_model"))
    finally:
        training_env.close()
        evaluation_env.close()

    training_plots = generate_training_plots(
        output_dir / "training_episodes.json",
        output_dir / "plots",
    )
    summary = {
        "config": config.to_dict(),
        "environment_manifest": manifest,
        "total_timesteps": model.num_timesteps,
        "training_episodes": len(metrics_callback.episodes),
        "action_masking": True,
        "algorithm": "MaskablePPO",
        "final_model": "final_model.zip",
        "best_model": "checkpoints/best_model.zip",
        "training_metrics": "training_episodes.json",
        "evaluation_log": "logs/evaluations.npz",
        "training_plots": training_plots,
        "software_versions": {
            "python": platform.python_version(),
            "stable_baselines3": _package_version("stable-baselines3"),
            "sb3_contrib": _package_version("sb3-contrib"),
            "torch": _package_version("torch"),
            "gymnasium": _package_version("gymnasium"),
        },
    }
    with (output_dir / "training_summary.json").open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, allow_nan=False)
    return summary


def config_for_seed(config: PPOConfig, seed: int) -> PPOConfig:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer.")
    if not 0 <= seed <= 2**32 - 3:
        raise ValueError("seed must be between 0 and 2**32 - 3.")
    return PPOConfig.from_dict({
        **config.to_dict(),
        "ppo_seed": seed,
        "environment_seed": seed + 1,
        "evaluation_seed": seed + 2,
    })


def load_ppo_model(model_path: str | Path, *, env: Any = None, device: str = "cpu") -> MaskablePPO:
    return MaskablePPO.load(str(model_path), env=env, device=device)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train mask-aware PPO on the stochastic antibiotic environment.")
    parser.add_argument("--config", default="experiments/ppo_baseline_config.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--total-timesteps", type=int)
    parser.add_argument("--seed", type=int, help="Base seed; PPO/environment/evaluation use seed, seed+1, seed+2.")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    config = PPOConfig.from_json(args.config)
    if args.smoke_test:
        config = PPOConfig.from_dict({
            **config.to_dict(),
            "total_timesteps": 64,
            "n_steps": 16,
            "batch_size": 8,
            "n_epochs": 2,
            "evaluation_frequency": 16,
            "evaluation_episodes": 4,
        })
    if args.total_timesteps is not None:
        config = PPOConfig.from_dict({**config.to_dict(), "total_timesteps": args.total_timesteps})
    if args.seed is not None:
        config = config_for_seed(config, args.seed)
    summary = train_ppo(config, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
