"""Offline, matched DQN/PPO/random-susceptible benchmark. No application promotion."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import platform
from statistics import mean
import time
import uuid

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.utils import set_random_seed

from ml.src.greedy_policy import GreedyPolicy
from ml.src.artifact_checksums import checksum_of, parse_sums, verify_checksums
from ml.src.masked_dqn import MaskedDQN
from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.multi_seed_evaluation import MultiSeedResult, run_multi_seed_evaluation
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_training import (
    EpisodeMetricsWrapper, InitialResistanceProfileWrapper, PPOConfig, config_for_seed,
    environment_manifest, make_training_environment, train_ppo,
    training_initial_profiles, validation_initial_profiles,
)
from ml.src.statistical_comparison import match_run_pairs
from simulation.resistance_state import ANTIBIOTICS

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ("dqn", "ppo", "random_susceptible_baseline")
METRICS = (
    "resistance_burden", "resistance_emergence_events", "remaining_susceptible_options",
    "antibiotic_exposure", "unsupported_steps", "susceptible_action_rate",
)


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class DQNSettings:
    learning_rate: float = 0.001
    buffer_size: int = 100000
    learning_starts: int = 256
    batch_size: int = 64
    train_freq: int = 4
    gradient_steps: int = 1
    target_update_interval: int = 256
    exploration_fraction: float = 0.3
    exploration_initial_eps: float = 1.0
    exploration_final_eps: float = 0.05
    max_grad_norm: float = 10.0

    def __post_init__(self):
        for name in (
            "buffer_size", "learning_starts", "batch_size", "train_freq",
            "gradient_steps", "target_update_interval",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if self.batch_size > self.buffer_size:
            raise ValueError("DQN batch_size cannot exceed buffer_size.")
        for name in ("learning_rate", "max_grad_norm"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")
        for name in ("exploration_fraction", "exploration_initial_eps", "exploration_final_eps"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be within [0,1].")
        if self.exploration_fraction == 0 or self.exploration_final_eps > self.exploration_initial_eps:
            raise ValueError("DQN exploration must have a positive duration and nonincreasing epsilon.")


@dataclass(frozen=True)
class BenchmarkProtocol:
    study_id: str
    stage: str
    training_timesteps: int
    training_seeds: tuple[int, ...]
    evaluation_seed_bases: tuple[int, ...]
    baseline_policy_seed_start: int
    ppo_config: str
    dqn: DQNSettings
    ppo_checkpoint_root: str | None = None
    expected_interaction_data_sha256: str | None = None

    @classmethod
    def from_dict(cls, values: dict) -> BenchmarkProtocol:
        values = dict(values)
        values["training_seeds"] = tuple(values["training_seeds"])
        values["evaluation_seed_bases"] = tuple(values["evaluation_seed_bases"])
        values["dqn"] = DQNSettings(**values["dqn"])
        return cls(**values)

    def __post_init__(self):
        if not self.study_id.strip() or self.stage not in {"pilot", "full"}:
            raise ValueError("A study ID and pilot/full stage are required.")
        digest = self.expected_interaction_data_sha256
        if digest is not None and (
            not isinstance(digest, str) or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("Expected interaction-data hash must be a lowercase SHA256.")
        if not self.training_seeds or len(set(self.training_seeds)) != len(self.training_seeds):
            raise ValueError("Training seeds must be nonempty and unique.")
        training_streams = set()
        for seed in self.training_seeds:
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 3:
                raise ValueError("Invalid training seed.")
            streams = {seed, seed + 1, seed + 2}
            if training_streams & streams:
                raise ValueError("Training/validation seed streams overlap across replicates.")
            training_streams.update(streams)
        if isinstance(self.training_timesteps, bool) or not isinstance(self.training_timesteps, int):
            raise ValueError("Training timesteps must be an integer.")
        if self.training_timesteps <= self.dqn.learning_starts or self.training_timesteps % self.dqn.train_freq:
            raise ValueError("Budget must exceed DQN warm-up and divide evenly by train_freq.")
        if not self.evaluation_seed_bases:
            raise ValueError("At least one evaluation seed block is required.")
        evaluation_seeds = set()
        for seed in self.evaluation_seed_bases:
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 128:
                raise ValueError("Invalid evaluation seed block.")
            block = set(range(seed, seed + 128))
            if evaluation_seeds & block or training_streams & block:
                raise ValueError("Evaluation seed blocks overlap each other or training/validation.")
            evaluation_seeds.update(block)
        start = self.baseline_policy_seed_start
        if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start <= 2**32 - 128 * len(self.evaluation_seed_bases):
            raise ValueError("Invalid baseline policy seed schedule.")
        policy_seeds = set(range(start, start + 128 * len(self.evaluation_seed_bases)))
        if policy_seeds & (training_streams | evaluation_seeds):
            raise ValueError("Baseline policy RNG seeds must be separate from environment/training seeds.")

    def shared_config(self, seed: int) -> PPOConfig:
        config = PPOConfig.from_json(REPO_ROOT / self.ppo_config)
        config = PPOConfig.from_dict({
            **config.to_dict(), "total_timesteps": self.training_timesteps,
            "matched_evaluation_seed_bases": self.evaluation_seed_bases,
            "matched_policy_seed_start": self.baseline_policy_seed_start,
            "device": "cpu",
        })
        config = config_for_seed(config, seed)
        if self.training_timesteps % config.n_steps:
            raise ValueError("Budget must divide evenly by PPO rollout length to match actual steps.")
        return config


class DQNEpisodes(BaseCallback):
    def __init__(self):
        super().__init__()
        self.episodes = []

    def _on_step(self) -> bool:
        for done, info in zip(self.locals["dones"], self.locals["infos"]):
            if done:
                self.episodes.append({**info["ppo_episode_metrics"], "timesteps": self.num_timesteps})
        if self.num_timesteps % 25000 == 0:
            print(f"DQN {self.num_timesteps}/{self.model._total_timesteps} steps", flush=True)
        return True


def train_dqn(config: PPOConfig, settings: DQNSettings, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Training directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "config.json", {"shared": config.to_dict(), "dqn": asdict(settings)})
    write_json(output / "environment_manifest.json", environment_manifest(config))

    def wrapped(profiles, shuffle):
        return InitialResistanceProfileWrapper(
            EpisodeMetricsWrapper(make_training_environment(config)), profiles, shuffle_cycles=shuffle,
        )

    set_random_seed(config.ppo_seed)
    training = make_vec_env(
        lambda: wrapped(training_initial_profiles(config), True), seed=config.environment_seed,
    )
    validation = make_vec_env(
        lambda: wrapped(validation_initial_profiles(config.evaluation_episodes), False),
        seed=config.evaluation_seed,
    )
    episodes = DQNEpisodes()
    evaluate = EvalCallback(
        validation, eval_freq=config.evaluation_frequency, n_eval_episodes=config.evaluation_episodes,
        deterministic=True, best_model_save_path=str(output / "checkpoints"),
        log_path=str(output / "logs"), verbose=0,
    )
    model = MaskedDQN(
        "MlpPolicy", training, **asdict(settings), gamma=config.gamma,
        policy_kwargs={"net_arch": list(config.policy_architecture)}, device=config.device,
        # Seed the network above; let the vector environments retain their distinct seeds.
        seed=None, verbose=0,
    )
    try:
        model.learn(config.total_timesteps, callback=CallbackList([episodes, evaluate]))
        model.save(output / "final_model.zip")
        summary = {
            "algorithm": "MaskedDQN", "total_timesteps": model.num_timesteps,
            "gradient_updates": model._n_updates, "training_episodes": len(episodes.episodes),
            "masking": ["warm_up", "exploration", "inference", "bellman_target"],
            "checkpoint_sha256": file_hash(output / "final_model.zip"),
        }
        write_json(output / "training_episodes.json", episodes.episodes)
        write_json(output / "training_summary.json", summary)
        return summary
    finally:
        training.close()
        validation.close()


class DQNObservationPolicy:
    def __init__(self, action_space, model: MaskedDQN, seed=None):
        if action_space.n != len(ANTIBIOTICS) or action_space.start != 0:
            raise ValueError("DQN requires the canonical seven actions.")
        self.model = model

    def select_action(self, observation) -> int:
        action, _ = self.model.predict(observation, deterministic=True)
        return int(action)


def summarize(result: MultiSeedResult) -> dict:
    episodes = [episode for run in result.runs for episode in run.evaluation.episodes]
    metrics = [metric for run in result.runs for metric in run.metrics.episodes]
    steps = [step for episode in episodes for step in episode.steps]
    if any(step.observation[step.action] != 0 for step in steps):
        raise ValueError("Evaluation selected an infeasible antibiotic.")
    return {
        "episodes": len(episodes),
        "resistance_burden": mean(-episode.cumulative_reward for episode in episodes),
        "resistance_emergence_events": mean(metric.resistance_emergence_events for metric in metrics),
        "remaining_susceptible_options": mean(metric.future_effective_antibiotics for metric in metrics),
        "antibiotic_exposure": mean(metric.cumulative_antibiotic_exposure for metric in metrics),
        "unsupported_steps": mean(sum(step.info["transition_status"] == "unsupported_no_candidate" for step in episode.steps) for episode in episodes),
        "susceptible_action_rate": sum(step.info["effective"] for step in steps) / len(steps) if steps else None,
    }


def render_report(report: dict) -> str:
    lines = [
        f"# {report['protocol']['study_id']}", "",
        f"Stage: **{report['protocol']['stage']}**. Offline research benchmark; no app model has changed.", "",
        "Equal environment-interaction budgets; algorithm-specific update schedules and compute differ.", "",
        "| Strategy | Burden (lower) | Emergence (lower) | Options (higher) | Exposure | Unsupported steps | Susceptible actions |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy in STRATEGIES:
        values = report["summary"][strategy]
        cells = ["n/a" if values[key] is None else f"{values[key]:.4f}" for key in METRICS]
        lines.append("| " + " | ".join([strategy, *cells]) + " |")
    lines += [
        "", "Means average profiles and evaluation seed blocks within each training replicate, then training replicates.",
        "Exposure is contextual; fewer actions can reflect loss of all susceptible options.",
        "Unsupported steps indicate missing transition data, not successful treatment.",
        "", "## Paired differences (DQN minus PPO)", "",
    ]
    for run in report["replicates"]:
        lines.append(f"- Training seed {run['training_seed']}: burden {run['dqn_minus_ppo']['resistance_burden']:+.6f}.")
    lines += [
        "", "No automatic winner, significance test or promotion decision is assigned.",
        "Both models train on all 127 nonterminal profiles; evaluation uses all 128 profiles with separate RNG seeds.",
        "Evaluation holds out stochastic draws, not resistance profiles. Identical environment seeds do not ensure identical transitions after different actions.",
        "The same baseline draws are reused across training replicates and are not independent extra baseline samples.",
        "Pilot results establish pipeline behavior only. Full-study settings are a starting protocol, not a tuned or clinically validated model.",
    ]
    return "\n".join(lines) + "\n"


def archive_inputs(config: PPOConfig, root: Path) -> dict[str, bytes]:
    """Validate the exact archived bytes before using a previously trained PPO."""
    directory = root / f"ppo_seed_{config.ppo_seed}"
    sums = dict((path, digest) for digest, path in parse_sums(
        (root / "SHA256SUMS.txt").read_text(encoding="utf-8-sig")
    ))
    inputs = {}
    for name in ("final_model.zip", "config.json", "environment_manifest.json", "training_summary.json"):
        data = (directory / name).read_bytes()
        relative = f"ppo_seed_{config.ppo_seed}/{name}"
        if sums.get(relative) != checksum_of(name, data):
            raise ValueError(f"Archived PPO checksum mismatch: {relative}")
        inputs[name] = data
    archived_config = PPOConfig.from_dict(json.loads(inputs["config.json"]))
    expected = config.to_dict()
    actual = archived_config.to_dict()
    differences = [key for key in expected if key != "total_timesteps" and expected[key] != actual[key]]
    if differences:
        raise ValueError(f"Archived PPO training configuration differs: {differences}")
    summary = json.loads(inputs["training_summary.json"])
    if summary["algorithm"] != "MaskablePPO" or summary["total_timesteps"] != config.total_timesteps:
        raise ValueError("Archived PPO actual training budget or algorithm differs.")
    if json.loads(inputs["environment_manifest.json"]) != environment_manifest(config):
        raise ValueError("Archived PPO simulator or transition-data manifest differs.")
    for package, key in (
        ("torch", "torch"), ("stable-baselines3", "stable_baselines3"),
        ("sb3-contrib", "sb3_contrib"), ("gymnasium", "gymnasium"),
    ):
        if summary["software_versions"][key] != version(package):
            raise ValueError(f"Archived PPO package version differs: {package}")
    return inputs


def evaluate_policy(config: PPOConfig, protocol: BenchmarkProtocol, factory) -> MultiSeedResult:
    profiles = canonical_initial_profiles()
    seed_pairs = tuple(
        (seed, protocol.baseline_policy_seed_start + index * len(profiles))
        for index, seed in enumerate(protocol.evaluation_seed_bases)
    )
    return run_multi_seed_evaluation(
        lambda: make_training_environment(config), factory, seed_pairs, initial_states=profiles,
    )


def run_replicate(config: PPOConfig, protocol: BenchmarkProtocol, output: Path, baseline: MultiSeedResult) -> dict:
    torch.set_num_threads(1)
    seed = config.ppo_seed
    directory = output / f"seed_{seed}"
    if directory.exists():
        # Preserve partial work when explicitly resuming, within this study's output tree.
        backup = output / "interrupted" / f"seed_{seed}_{uuid.uuid4().hex[:8]}"
        directory.resolve().relative_to(output.resolve())
        backup.resolve().relative_to(output.resolve())
        backup.parent.mkdir(parents=True, exist_ok=True)
        directory.rename(backup)
    print(f"Benchmark seed {seed}: {config.total_timesteps} steps per model", flush=True)
    timings = {}
    before = time.perf_counter()
    if protocol.ppo_checkpoint_root:
        inputs = archive_inputs(config, REPO_ROOT / protocol.ppo_checkpoint_root)
        ppo_directory = directory / "ppo"
        ppo_directory.mkdir(parents=True)
        for name, data in inputs.items():
            (ppo_directory / name).write_bytes(data)
        ppo_training = json.loads(inputs["training_summary.json"])
        write_json(ppo_directory / "source.json", {
            "kind": "verified_archive", "root": protocol.ppo_checkpoint_root, "training_seed": seed,
        })
        timings["ppo_archive_load_seconds"] = time.perf_counter() - before
    else:
        ppo_training = train_ppo(config, directory / "ppo")
        timings["ppo_seconds"] = time.perf_counter() - before
    before = time.perf_counter()
    dqn_training = train_dqn(config, protocol.dqn, directory / "dqn")
    timings["dqn_seconds"] = time.perf_counter() - before
    if ppo_training["total_timesteps"] != dqn_training["total_timesteps"] or dqn_training["total_timesteps"] != protocol.training_timesteps:
        raise ValueError("Actual PPO/DQN training budgets differ; refusing comparison.")
    ppo_path = directory / "ppo" / "final_model.zip"
    dqn_path = directory / "dqn" / "final_model.zip"
    ppo_bytes, dqn_bytes = ppo_path.read_bytes(), dqn_path.read_bytes()
    checkpoint_hashes = {
        "ppo": hashlib.sha256(ppo_bytes).hexdigest(),
        "dqn": hashlib.sha256(dqn_bytes).hexdigest(),
    }
    if checkpoint_hashes["dqn"] != dqn_training["checkpoint_sha256"]:
        raise ValueError("DQN checkpoint changed after training.")
    ppo_model = MaskablePPO.load(io.BytesIO(ppo_bytes), device="cpu")
    dqn_model = MaskedDQN.load(io.BytesIO(dqn_bytes), device="cpu")
    results = {
        "ppo": evaluate_policy(config, protocol, lambda space, seed: MaskablePPOObservationPolicy(space, ppo_model, seed)),
        "dqn": evaluate_policy(config, protocol, lambda space, seed: DQNObservationPolicy(space, dqn_model, seed)),
    }
    summaries = {"random_susceptible_baseline": summarize(baseline)}
    for strategy, result in results.items():
        match_run_pairs(result, baseline)
        summaries[strategy] = summarize(result)
        write_json(directory / strategy / "evaluation.json", result.to_dict())
    match_run_pairs(results["dqn"], results["ppo"])
    replicate = {
        "training_seed": seed, "actual_timesteps_per_model": config.total_timesteps,
        "ppo_source": "verified_archive" if protocol.ppo_checkpoint_root else "fresh_training",
        "checkpoints": checkpoint_hashes,
        "metadata_sha256": {
            str(path.relative_to(directory)): file_hash(path)
            for strategy in ("dqn", "ppo")
            for path in sorted((directory / strategy).glob("*.json"))
        },
        "training_times": timings, "metrics": summaries,
        "dqn_minus_ppo": {
            key: summaries["dqn"][key] - summaries["ppo"][key]
            if summaries["dqn"][key] is not None and summaries["ppo"][key] is not None else None
            for key in METRICS
        },
    }
    write_json(directory / "replicate.json", replicate)
    print(f"Completed seed {seed}: DQN-PPO burden {replicate['dqn_minus_ppo']['resistance_burden']:+.6f}", flush=True)
    return replicate


def verified_replicate(config: PPOConfig, directory: Path) -> dict | None:
    path = directory / "replicate.json"
    if not path.exists():
        return None
    replicate = json.loads(path.read_text(encoding="utf-8"))
    if replicate["training_seed"] != config.ppo_seed or replicate["actual_timesteps_per_model"] != config.total_timesteps:
        raise ValueError(f"Completed replicate identity or budget differs: {directory}")
    for strategy, digest in replicate["checkpoints"].items():
        if file_hash(directory / strategy / "final_model.zip") != digest:
            raise ValueError(f"Completed replicate checkpoint changed: {directory}")
    for relative, digest in replicate["metadata_sha256"].items():
        if file_hash(directory / relative) != digest:
            raise ValueError(f"Completed replicate metadata changed: {relative}")
    return replicate


def run_benchmark(protocol: BenchmarkProtocol, output: Path, *, workers: int = 1, resume: bool = False) -> dict:
    configs = [protocol.shared_config(seed) for seed in protocol.training_seeds]
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer.")
    live_environment = environment_manifest(configs[0])
    if protocol.expected_interaction_data_sha256 is not None and (
        live_environment["interaction_data_sha256"] != protocol.expected_interaction_data_sha256
    ):
        raise ValueError("Training interactions differ from the dataset pinned by this study configuration.")
    interaction_path = REPO_ROOT / "data/processed/empirical_interactions.csv"
    interaction_bytes = interaction_path.read_bytes()
    if protocol.ppo_checkpoint_root:
        root = REPO_ROOT / protocol.ppo_checkpoint_root
        failures = [item.path for item in verify_checksums(root / "SHA256SUMS.txt") if item.status != "ok"]
        if failures:
            raise ValueError(f"PPO archive checksum verification failed: {failures}")
        for config in configs:
            archive_inputs(config, root)
    source_hashes = {
        str(path.relative_to(REPO_ROOT)): file_hash(path)
        for folder in ("ml/src", "simulation")
        for path in sorted((REPO_ROOT / folder).glob("*.py"))
    }
    manifest = {
        "protocol": asdict(protocol), "source_sha256": source_hashes,
        "environment": live_environment,
        "interaction_csv_sha256": hashlib.sha256(interaction_bytes).hexdigest(),
        "ppo_base_config_sha256": file_hash(REPO_ROOT / protocol.ppo_config),
        "packages": {name: version(name) for name in ("torch", "numpy", "stable-baselines3", "sb3-contrib", "gymnasium")},
    }
    manifest = json.loads(json.dumps(manifest))
    if output.exists() and any(output.iterdir()):
        if not resume:
            raise FileExistsError(f"Benchmark directory is not empty: {output}")
        if json.loads((output / "run_manifest.json").read_text(encoding="utf-8")) != manifest:
            raise ValueError("Cannot resume: dataset, protocol, source, packages or base config changed.")
        if file_hash(output / "empirical_interactions.csv") != manifest["interaction_csv_sha256"]:
            raise ValueError("Cannot resume: archived training interactions changed.")
    else:
        output.mkdir(parents=True, exist_ok=True)
        (output / "empirical_interactions.csv").write_bytes(interaction_bytes)
        write_json(output / "run_manifest.json", manifest)
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    started = time.perf_counter()
    replicates = []

    def progress():
        write_json(output / "status.json", {
            "status": "running", "completed_seeds": sorted(run["training_seed"] for run in replicates),
            "total_seeds": len(configs), "workers": workers,
            "seconds_this_session": time.perf_counter() - started,
        })

    progress()
    try:
        baseline = evaluate_policy(configs[0], protocol, GreedyPolicy)
        write_json(output / "baseline_evaluation.json", baseline.to_dict())
        pending = []
        for config in configs:
            existing = verified_replicate(config, output / f"seed_{config.ppo_seed}") if resume else None
            if existing:
                replicates.append(existing)
            else:
                pending.append(config)
        progress()
        if workers == 1:
            for config in pending:
                replicates.append(run_replicate(config, protocol, output, baseline))
                progress()
        else:
            with ProcessPoolExecutor(max_workers=min(workers, max(1, len(pending)))) as pool:
                futures = [pool.submit(run_replicate, config, protocol, output, baseline) for config in pending]
                for future in as_completed(futures):
                    replicates.append(future.result())
                    progress()
        replicates.sort(key=lambda run: protocol.training_seeds.index(run["training_seed"]))
        if any(file_hash(REPO_ROOT / path) != digest for path, digest in source_hashes.items()):
            raise ValueError("Benchmark source changed while the study was running.")
        if file_hash(interaction_path) != manifest["interaction_csv_sha256"] or (
            file_hash(REPO_ROOT / protocol.ppo_config) != manifest["ppo_base_config_sha256"]
        ):
            raise ValueError("Training data or base configuration changed while the study was running.")
        report = {
            **manifest, "environment": environment_manifest(configs[0]),
            "checkpoint_selection": "final checkpoint, not best validation checkpoint",
            "evaluation_seed_pairs": baseline.seed_pairs,
            "evaluation_profile_count": len(canonical_initial_profiles()),
            "torch_threads_per_worker": 1, "workers": workers,
            "python_version": platform.python_version(), "replicates": replicates,
            "summary": {strategy: {
                key: mean(run["metrics"][strategy][key] for run in replicates)
                if all(run["metrics"][strategy][key] is not None for run in replicates) else None
                for key in METRICS
            } for strategy in STRATEGIES},
        }
        write_json(output / "report.json", report)
        (output / "report.md").write_text(render_report(report), encoding="utf-8")
        write_json(output / "status.json", {
            "status": "completed", "completed_seeds": list(protocol.training_seeds),
            "seconds_this_session": time.perf_counter() - started,
        })
        return report
    except BaseException as error:
        write_json(output / "status.json", {
            "status": "interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            "error": str(error), "completed_seeds": sorted(run["training_seed"] for run in replicates),
        })
        raise
    finally:
        torch.set_num_threads(old_threads)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/dqn_pilot_config.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    protocol = BenchmarkProtocol.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8-sig")))
    report = run_benchmark(protocol, Path(args.output_dir), workers=args.workers, resume=args.resume)
    print(render_report(report), flush=True)


if __name__ == "__main__":
    main()
