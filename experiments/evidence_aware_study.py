"""Audit, pilot and confirm evidence-restricted PPO/DQN locally; never promote models."""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from functools import cache
from importlib.metadata import version
import json
from pathlib import Path
from statistics import mean
import time

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.utils import set_random_seed

from experiments.evidence_environment import DATA, PROFILES, ROOT, VARIANTS, EvidenceDQN, EvidenceEnvironment, EvidenceKernel, EvidenceSpec
from ml.src.confidence_intervals import t_confidence_interval
from ml.src.dqn_benchmark import DQNSettings, file_hash, write_json
from ml.src.ppo_training import InitialResistanceProfileWrapper, PPOConfig, validation_initial_profiles
from simulation.observation import Observation, encode_observation
from simulation.resistance_state import ANTIBIOTICS


STAGES = {
    "smoke": {"seeds": (90000,), "timesteps": 512, "evaluation_seed_bases": (910001,)},
    "pilot": {"seeds": (30000, 31000, 32000), "timesteps": 16384, "evaluation_seed_bases": (610001, 710001)},
    "full": {"seeds": tuple(range(1000, 20001, 1000)), "timesteps": 100096,
             "evaluation_seed_bases": (1110001, 1210001, 1310001, 1410001, 1510001)},
}
COMPARATORS = ("random_allowed", "myopic", "exact_optimum")
LEARNED = ("ppo", "dqn")
METRICS = ("pessimistic_score", "completion_rate", "full_burden_complete_only", "observed_burden",
           "unobserved_steps", "unsupported_steps", "actions", "repeated_selections", "distinct_actions")


def observation(profile, previous, step) -> np.ndarray:
    return np.asarray(encode_observation(Observation(tuple(profile), tuple(int(i == previous) for i in range(7)), step)), dtype=np.float32)


def model_chooser(model, kernel):
    @cache
    def choose(profile, previous, step):
        obs = observation(profile, previous, step)
        if isinstance(model, MaskablePPO):
            action, _ = model.predict(obs, deterministic=True, action_masks=kernel.mask(profile))
        else:
            action, _ = model.predict(obs, deterministic=True)
        return int(action)
    return choose


def evaluate(kernel: EvidenceKernel, choose, seed_bases) -> list[dict]:
    records = []
    env = EvidenceEnvironment(kernel)
    try:
        for block, seed_base in enumerate(seed_bases):
            for index, initial in enumerate(PROFILES):
                seed = seed_base + index
                policy_seed = 4_000_000 + block * 128 + index
                rng = np.random.default_rng(policy_seed)
                env.reset(seed=seed, options={"initial_resistance_state": initial})
                profile, previous, score, known_burden = initial, None, 0.0, 0.0
                steps = []
                if all(initial):
                    score = known_burden = float(kernel.spec.horizon)
                elif kernel.boundary(initial):
                    score = kernel.spec.boundary_cost(kernel.spec.horizon)
                else:
                    while not env.finished:
                        action = choose(profile, previous, len(steps), rng)
                        before = profile
                        _, reward, _, _, info = env.step(action)
                        profile = env.episode.resistance_state.resistance
                        score -= float(reward)
                        known_burden += info["observed_burden"]
                        if all(profile):
                            known_burden += kernel.spec.horizon - len(steps) - 1
                        steps.append({"step": len(steps) + 1, "action": action, "antibiotic": ANTIBIOTICS[action],
                                      "before": list(before), "after": list(profile),
                                      **{key: info[key] for key in (
                                          "transition_status", "source_ids", "transition_seed", "repeated_action",
                                          "evidence_boundary", "uncertainty_continuation_cost", "repetition_cost")}})
                        previous = action
                boundary = kernel.boundary(profile) and len(steps) < kernel.spec.horizon
                complete = not boundary
                records.append({
                    "profile": "".join(map(str, initial)), "environment_seed": seed,
                    "baseline_policy_seed": policy_seed, "complete": complete,
                    "end_reason": "evidence_boundary" if boundary else "all_resistant" if all(profile) else "horizon",
                    "pessimistic_score": score, "observed_burden": known_burden,
                    "full_horizon_burden": known_burden if complete else None,
                    "unobserved_steps": kernel.spec.horizon - len(steps) if boundary else 0,
                    "last_observed_options": 7 - sum(profile),
                    "final_options": 7 - sum(profile) if complete else None,
                    "unsupported_steps": sum(s["transition_status"] == "unsupported_no_candidate" for s in steps),
                    "actions": len(steps), "repeated_selections": sum(s["repeated_action"] for s in steps),
                    "distinct_actions": len({s["action"] for s in steps}), "steps": steps,
                })
    finally:
        env.close()
    return records


def summarize(records) -> dict:
    completed = [record["full_horizon_burden"] for record in records if record["complete"]]
    return {
        "episodes": len(records), "completion_rate": mean(record["complete"] for record in records),
        "full_burden_complete_only": mean(completed) if completed else None,
        **{key: mean(record[key] for record in records) for key in METRICS
           if key not in {"completion_rate", "full_burden_complete_only"}},
    }


def comparator_records(kernel, seed_bases):
    choices = {
        "random_allowed": lambda profile, previous, step, rng: int(rng.choice(kernel.actions(profile))),
        "myopic": lambda profile, previous, step, rng: kernel.select_myopic(profile, previous),
        "exact_optimum": lambda profile, previous, step, rng: kernel.select_optimal(profile, previous, kernel.spec.horizon - step),
    }
    return {name: evaluate(kernel, choose, seed_bases) for name, choose in choices.items()}


def common_complete(records_by_policy) -> dict:
    identities = [{(r["profile"], r["environment_seed"]) for r in records} for records in records_by_policy.values()]
    if any(keys != identities[0] for keys in identities):
        raise ValueError("Policy evaluations have different starting profiles or seed schedules.")
    common = set.intersection(*(
        {(r["profile"], r["environment_seed"]) for r in records if r["complete"]}
        for records in records_by_policy.values()
    ))
    return {"episodes": len(common), "total_episodes": len(identities[0]),
            "burden": {name: mean(r["full_horizon_burden"] for r in records if (r["profile"], r["environment_seed"]) in common)
                       if common else None for name, records in records_by_policy.items()},
            "interpretation": "Same completed subset for every policy; conditioning on completion can still introduce selection bias."}


class Progress(BaseCallback):
    def __init__(self, algorithm, seed):
        super().__init__()
        self.algorithm, self.seed = algorithm, seed
        self.episodes = []

    def _on_step(self):
        for done, info in zip(self.locals["dones"], self.locals["infos"]):
            if done:
                self.episodes.append({"timesteps": self.num_timesteps, **info["episode"],
                                      "evidence_boundary": info["evidence_boundary"]})
        if self.num_timesteps % 4096 == 0:
            print(f"{self.algorithm} seed {self.seed}: {self.num_timesteps}/{self.model._total_timesteps}", flush=True)
        return True


def train_model(algorithm, kernel, seed, timesteps, output, base):
    output.mkdir(parents=True, exist_ok=False)
    set_random_seed(seed)
    profiles = tuple(p for p in PROFILES if kernel.actions(p))
    validation_profiles = tuple(p for p in validation_initial_profiles(16) if kernel.actions(p))

    def create(profiles, shuffle):
        return InitialResistanceProfileWrapper(EvidenceEnvironment(kernel), profiles, shuffle_cycles=shuffle)

    training = make_vec_env(lambda: create(profiles, True), seed=seed + 1)
    validation = make_vec_env(lambda: create(validation_profiles, False), seed=seed + 2)
    progress = Progress(algorithm, seed)
    shared = {"gamma": 1.0, "policy_kwargs": {"net_arch": list(base.policy_architecture)}, "device": "cpu", "seed": None, "verbose": 0}
    if algorithm == "ppo":
        kwargs = {key: getattr(base, key) for key in ("learning_rate", "n_steps", "batch_size", "n_epochs", "gae_lambda", "ent_coef", "clip_range")}
        model = MaskablePPO("MlpPolicy", training, **shared, **kwargs)
        callback_class = MaskableEvalCallback
    else:
        kwargs = asdict(DQNSettings())
        model = EvidenceDQN("MlpPolicy", training, evidence_mask_table=kernel.mask_table, **shared, **kwargs)
        callback_class = EvalCallback
    callbacks = [progress]
    if timesteps >= base.evaluation_frequency:
        callbacks.append(callback_class(validation, eval_freq=base.evaluation_frequency,
                                        n_eval_episodes=len(validation_profiles), deterministic=True,
                                        log_path=str(output / "validation"), verbose=0))
    write_json(output / "config.json", {"algorithm": algorithm, "seed": seed, "environment_seed": seed + 1,
                                       "validation_seed": seed + 2, "validation_profiles": validation_profiles,
                                       "training_timesteps": timesteps, "parameters": kwargs,
                                       "shared": {**shared, "device": "cpu"}, "environment": kernel.manifest()})
    try:
        model.learn(timesteps, callback=callbacks)
        if model.num_timesteps != timesteps:
            raise ValueError("Actual training budget differs from the protocol.")
        model.save(output / "final_model.zip")
        write_json(output / "training_episodes.json", progress.episodes)
    finally:
        training.close()
        validation.close()
    # Exercise checkpoint serialization, including DQN's archived mask.
    return (MaskablePPO if algorithm == "ppo" else EvidenceDQN).load(output / "final_model.zip", device="cpu")


def run_seed(seed, spec_document, timesteps, seed_bases, output, baselines, base_document):
    torch.set_num_threads(1)
    output = Path(output)
    kernel = EvidenceKernel(EvidenceSpec(**spec_document), output / "empirical_interactions.csv")
    base = PPOConfig.from_dict(base_document)
    directory = output / f"seed_{seed}"
    if directory.exists():
        backup = output / "interrupted" / f"seed_{seed}_{time.time_ns()}"
        backup.parent.mkdir(exist_ok=True)
        directory.rename(backup)
    records = dict(baselines)
    exact = {}
    for algorithm in LEARNED:
        print(f"Training {algorithm} seed {seed}", flush=True)
        model = train_model(algorithm, kernel, seed, timesteps, directory / algorithm, base)
        choose = model_chooser(model, kernel)
        records[algorithm] = evaluate(kernel, lambda p, a, t, rng: choose(p, a, t), seed_bases)
        write_json(directory / algorithm / "evaluation.json", records[algorithm])
        expected = [kernel.expected_score(choose, profile) for profile in PROFILES]
        optima = [kernel.optimal(profile, None, kernel.spec.horizon) for profile in PROFILES]
        gaps = [actual - optimal for actual, optimal in zip(expected, optima)]
        if min(gaps) < -1e-8:
            raise ValueError("Policy expectation is below the exact optimum.")
        exact[algorithm] = {"expected_score": mean(expected), "gap_to_optimal": mean(gaps)}
        write_json(directory / algorithm / "exact_audit.json", [
            {"profile": "".join(map(str, p)), "expected_score": value, "optimal_score": optimum}
            for p, value, optimum in zip(PROFILES, expected, optima)
        ])
    if kernel.spec.supported_only and any(record["unsupported_steps"] for group in records.values() for record in group):
        raise ValueError("Restricted evaluation executed an unsupported action.")
    result = {"training_seed": seed, "metrics": {name: summarize(group) for name, group in records.items()},
              "common_complete": common_complete(records), "exact": exact,
              "exact_optimal_mean_score": mean(kernel.optimal(p, None, kernel.spec.horizon) for p in PROFILES)}
    result["checksums"] = {str(path.relative_to(directory)): file_hash(path)
                           for path in sorted(directory.rglob("*")) if path.is_file()}
    write_json(directory / "replicate.json", result)
    return result


def sources() -> dict:
    paths = [*sorted((ROOT / "simulation").glob("*.py")), *sorted((ROOT / "ml/src").glob("*.py")),
             *sorted((ROOT / "experiments").glob("*.py"))]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def render_report(report):
    lines = [f"# Evidence-aware study: {report['stage']} / {report['variant']}", "",
             "Pessimistic score = modeled normalized burden + any repetition cost + uncertainty continuation cost.",
             "The uncertainty cost is not a predicted resistance outcome. Partial trajectories have no full-horizon burden.", "",
             "| Policy | Pessimistic score (lower) | Complete fraction (higher) | Complete-only burden | Unsupported actions | Repeated selections |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, summary in report["summary"].items():
        values = [summary[key] for key in ("pessimistic_score", "completion_rate", "full_burden_complete_only", "unsupported_steps", "repeated_selections")]
        lines.append("| " + " | ".join([name, *("n/a" if value is None else f"{value:.4f}" for value in values)]) + " |")
    lines += ["", "Compare complete trajectories on each replicate's common-complete subset, not separately selected subsets.",
              "Complete-only burden remains a selected-subset description; inspect completion rates and uncertainty costs alongside it.",
              "All 128 profiles are evaluated; training excludes initial states without a permitted action.",
              "Evaluation holds out random draws, not resistance profiles. Shared seeds do not guarantee identical outcomes after different actions.",
              "Comparator draws are reused across training replicates; they are not additional independent baseline samples.",
              "Confidence intervals summarize training-seed variation conditional on the fixed evaluation design and model assumptions.",
              "No automatic winner or promotion. Neutral loops and lack of selected-drug self-resistance remain explicit limitations."]
    return "\n".join(lines) + "\n"


def train_study(stage, variant, output: Path, *, workers=1, resume=False, pilot_dir=None):
    if isinstance(workers, bool) or workers < 1:
        raise ValueError("Workers must be positive.")
    protocol = STAGES[stage]
    spec = VARIANTS[variant]
    kernel = EvidenceKernel(spec)
    base = PPOConfig.from_json(ROOT / "experiments/ppo_baseline_config.json")
    if protocol["timesteps"] % base.n_steps or protocol["timesteps"] % DQNSettings().train_freq:
        raise ValueError("PPO and DQN budgets must be exactly divisible by their rollout schedules.")
    manifest = json.loads(json.dumps({
        "version": 1, "stage": stage, "variant": variant, "protocol": protocol,
        "environment": kernel.manifest(), "source_sha256": sources(), "base_config": base.to_dict(),
        "dqn_parameters": asdict(DQNSettings()),
        "random_policy_seed_base": 4_000_000,
        "myopic_rule": "minimum expected immediate normalized burden plus declared repetition cost; lowest action index breaks ties",
        "packages": {name: version(name) for name in ("torch", "numpy", "gymnasium", "stable-baselines3", "sb3-contrib", "scipy")},
    }))
    if stage == "full":
        if pilot_dir is None:
            raise ValueError("Full training requires --pilot-dir from a completed pilot of this variant.")
        pilot_manifest = json.loads((Path(pilot_dir) / "run_manifest.json").read_text())
        pilot_status = json.loads((Path(pilot_dir) / "status.json").read_text())
        if (pilot_manifest["stage"] != "pilot" or pilot_status["status"] != "completed"
                or pilot_status["completed_seeds"] != sorted(STAGES["pilot"]["seeds"])):
            raise ValueError("A completed three-seed pilot is required.")
        for key in ("variant", "environment", "source_sha256", "base_config", "dqn_parameters", "packages"):
            if manifest[key] != pilot_manifest[key]:
                raise ValueError(f"Pilot and full configuration differ: {key}")
        pilot_report = json.loads((Path(pilot_dir) / "report.json").read_text())
        if pilot_report["run_manifest_sha256"] != file_hash(Path(pilot_dir) / "run_manifest.json"):
            raise ValueError("Pilot report does not match its manifest.")
        if spec.supported_only and any(s["unsupported_steps"] for s in pilot_report["summary"].values()):
            raise ValueError("Pilot executed unsupported actions; resolve this before full training.")
        manifest["pilot_report_sha256"] = file_hash(Path(pilot_dir) / "report.json")
    previous_status = {}
    if output.exists() and any(output.iterdir()):
        if not resume:
            raise FileExistsError("Output is not empty; use --resume with unchanged code and settings.")
        if json.loads((output / "run_manifest.json").read_text()) != manifest:
            raise ValueError("Cannot resume: code, protocol, packages, data or pilot changed.")
        if file_hash(output / "empirical_interactions.csv") != manifest["environment"]["csv_sha256"]:
            raise ValueError("Archived interactions changed.")
        if (output / "status.json").exists():
            previous_status = json.loads((output / "status.json").read_text())
    else:
        output.mkdir(parents=True, exist_ok=True)
        (output / "empirical_interactions.csv").write_bytes(DATA.read_bytes())
        write_json(output / "run_manifest.json", manifest)
    torch.set_num_threads(1)
    started = time.perf_counter()
    baselines = comparator_records(kernel, protocol["evaluation_seed_bases"])
    write_json(output / "comparator_evaluation.json", baselines)
    replicates = []

    def status(state, error=None):
        write_json(output / "status.json", {"status": state, "completed_seeds": sorted(r["training_seed"] for r in replicates),
                                           "replicate_sha256": {**previous_status.get("replicate_sha256", {}), **{str(r["training_seed"]): file_hash(output / f"seed_{r['training_seed']}" / "replicate.json") for r in replicates}},
                                           "total_seeds": len(protocol["seeds"]), "seconds_this_session": time.perf_counter() - started,
                                           "error": error})
    status("running")
    try:
        pending = []
        for seed in protocol["seeds"]:
            directory = output / f"seed_{seed}"
            completed = directory / "replicate.json"
            if resume and completed.exists():
                digest = previous_status.get("replicate_sha256", {}).get(str(seed))
                if digest is not None and file_hash(completed) != digest:
                    raise ValueError("Completed replicate summary changed.")
                result = json.loads(completed.read_text())
                if result["training_seed"] != seed:
                    raise ValueError("Replicate seed changed.")
                for path, digest in result["checksums"].items():
                    if file_hash(directory / path) != digest:
                        raise ValueError(f"Completed replicate changed: {directory / path}")
                replicates.append(result)
            else:
                pending.append(seed)
        status("running")
        arguments = [(seed, asdict(spec), protocol["timesteps"], protocol["evaluation_seed_bases"],
                      str(output), baselines, base.to_dict()) for seed in pending]
        if workers == 1:
            for args in arguments:
                replicates.append(run_seed(*args))
                status("running")
        else:
            with ProcessPoolExecutor(max_workers=min(workers, max(1, len(pending)))) as pool:
                futures = [pool.submit(run_seed, *args) for args in arguments]
                for future in as_completed(futures):
                    replicates.append(future.result())
                    status("running")
        replicates.sort(key=lambda r: r["training_seed"])
        if sources() != manifest["source_sha256"] or file_hash(DATA) != manifest["environment"]["csv_sha256"]:
            raise ValueError("Experiment code or data changed while training.")
        summary = {name: {key: mean(r["metrics"][name][key] for r in replicates)
                          if all(r["metrics"][name][key] is not None for r in replicates) else None for key in METRICS}
                   for name in (*COMPARATORS, *LEARNED)}
        paired = {key: asdict(t_confidence_interval([
            r["metrics"]["dqn"][key] - r["metrics"]["ppo"][key] for r in replicates
        ])) for key in ("pessimistic_score", "completion_rate", "repeated_selections")}
        report = {"stage": stage, "variant": variant, "summary": summary, "replicates": replicates,
                  "dqn_minus_ppo_seed_intervals": paired, "run_manifest_sha256": file_hash(output / "run_manifest.json")}
        write_json(output / "report.json", report)
        (output / "report.md").write_text(render_report(report), encoding="utf-8")
        with (output / "replicate_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["training_seed", "policy", *METRICS, "exact_expected_score", "exact_gap_to_optimal"])
            writer.writeheader()
            for replicate in replicates:
                for name, values in replicate["metrics"].items():
                    exact = replicate["exact"].get(name, {})
                    writer.writerow({"training_seed": replicate["training_seed"], "policy": name,
                                     **{key: values[key] for key in METRICS},
                                     "exact_expected_score": exact.get("expected_score"),
                                     "exact_gap_to_optimal": exact.get("gap_to_optimal")})
        status("completed")
        return report
    except BaseException as error:
        status("interrupted" if isinstance(error, KeyboardInterrupt) else "failed", str(error))
        raise


def audit(output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Audit output must be empty.")
    output.mkdir(parents=True, exist_ok=True)
    from experiments.review_frozen_policies import review
    review(output / "frozen_original")
    kernel = EvidenceKernel(VARIANTS["supported"])
    coverage = {}
    for action, name in enumerate(ANTIBIOTICS):
        pairs = [p for p in PROFILES if not p[action]]
        coverage[name] = {"susceptible": len(pairs), "applicable": sum(bool(kernel.candidates[(p, action)]) for p in pairs),
                          "neutral_only": sum(bool(kernel.candidates[(p, action)]) and all(c.outcome == "neutral" for c in kernel.candidates[(p, action)]) for p in pairs)}
    report = {"environment": kernel.manifest(), "coverage": coverage,
              "boundary_profiles": ["".join(map(str, p)) for p in PROFILES if kernel.boundary(p)],
              "optimal_pessimistic_score": mean(kernel.optimal(p, None, kernel.spec.horizon) for p in PROFILES),
              "boundary_cost": kernel.spec.boundary_cost(kernel.spec.horizon),
              "interpretation": "Neutral-only loops remain. The restricted model closes fallback exploitation, not all biological limitations."}
    write_json(output / "restricted_audit.json", report)
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--output-dir", type=Path, required=True)
    train = commands.add_parser("train")
    train.add_argument("--stage", choices=STAGES, required=True)
    train.add_argument("--variant", choices=VARIANTS, default="supported")
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--pilot-dir", type=Path)
    train.add_argument("--workers", type=int, default=1)
    train.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "audit":
        audit(args.output_dir)
    else:
        report = train_study(args.stage, args.variant, args.output_dir, workers=args.workers, resume=args.resume, pilot_dir=args.pilot_dir)
        print(render_report(report))


if __name__ == "__main__":
    main()
