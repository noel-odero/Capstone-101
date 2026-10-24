"""Select final checkpoints on fresh validation draws, confirm, and freeze both policies."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import csv
import hashlib
import io
import json
from pathlib import Path

import torch
from sb3_contrib import MaskablePPO

from experiments.analyze_dqn_study import audit_study
from ml.src.artifact_checksums import checksum_of
from ml.src.dqn_benchmark import (
    BenchmarkProtocol, DQNObservationPolicy, evaluate_policy, file_hash, summarize, write_json,
)
from ml.src.greedy_policy import GreedyPolicy
from ml.src.masked_dqn import MaskedDQN
from ml.src.matched_policy_evaluation import MaskablePPOObservationPolicy
from ml.src.ppo_evaluation import canonical_initial_profiles
from ml.src.ppo_inference import InferenceContext, load_frozen_engine
from ml.src.ppo_training import environment_manifest


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SEEDS = (1100001, 1200001, 1300001, 1400001, 1500001)
CONFIRMATION_SEEDS = (2100001, 2200001, 2300001, 2400001, 2500001)
VALIDATION_POLICY_SEED = 1900001
CONFIRMATION_POLICY_SEED = 2900001
RANKING = "Lowest validation mean cumulative resistance burden; exact ties: fewer emergence events, more susceptible options, lower training seed."


def ranking(row: dict) -> tuple:
    metrics = row["validation"]
    return (metrics["resistance_burden"], metrics["resistance_emergence_events"],
            -metrics["remaining_susceptible_options"], row["training_seed"])


def evaluation_protocol(protocol: BenchmarkProtocol, *, confirmation: bool = False) -> BenchmarkProtocol:
    return replace(
        protocol,
        evaluation_seed_bases=CONFIRMATION_SEEDS if confirmation else VALIDATION_SEEDS,
        baseline_policy_seed_start=CONFIRMATION_POLICY_SEED if confirmation else VALIDATION_POLICY_SEED,
    )


def evaluate_checkpoint(task: tuple) -> dict:
    study, protocol, seed, strategy, confirmation = task
    torch.set_num_threads(1)
    protocol = evaluation_protocol(protocol, confirmation=confirmation)
    config = protocol.shared_config(seed)
    path = Path(study) / f"seed_{seed}" / strategy / "final_model.zip"
    data = path.read_bytes()
    if strategy == "ppo":
        model = MaskablePPO.load(io.BytesIO(data), device="cpu")
        factory = lambda space, seed: MaskablePPOObservationPolicy(space, model, seed)
    else:
        model = MaskedDQN.load(io.BytesIO(data), device="cpu")
        factory = lambda space, seed: DQNObservationPolicy(space, model, seed)
    result = summarize(evaluate_policy(config, protocol, factory))
    print(f"{'Confirm' if confirmation else 'Validate'} {strategy} seed {seed}: burden {result['resistance_burden']:.6f}", flush=True)
    return {"strategy": strategy, "training_seed": seed,
            "checkpoint_sha256": hashlib.sha256(data).hexdigest(), "validation": result}


def verify_frozen(destination: Path) -> int:
    selection = json.loads((destination / "selection.json").read_text(encoding="utf-8"))
    for strategy, selected in selection["selected"].items():
        manifest = json.loads((destination / strategy / "manifest.json").read_text(encoding="utf-8"))
        checkpoint = destination / strategy / "final_model.zip"
        if file_hash(checkpoint) != selected["checkpoint_sha256"] or manifest["checkpoint"]["sha256"] != selected["checkpoint_sha256"]:
            raise ValueError("Frozen checkpoint differs from the selected study.")
        simulator = manifest["simulator"]
        if (simulator["interaction_data_sha256"] != selection["interaction_data_sha256"]
                or (ROOT / simulator["interaction_data_path"]).resolve() != (destination / "empirical_interactions.csv").resolve()):
            raise ValueError("Frozen transition data differs from the selected study.")
    torch.set_num_threads(1)
    engine = load_frozen_engine(destination / "ppo/manifest.json")
    dqn = MaskedDQN.load(destination / "dqn/final_model.zip", device="cpu")
    checked = 0
    for state in canonical_initial_profiles():
        profile = state.resistance
        if all(profile):
            continue
        context = InferenceContext(profile, None, 0)
        if profile[engine.recommend(context).action_id] or profile[int(dqn.predict(context.to_observation(), deterministic=True)[0])]:
            raise ValueError("Frozen policy selected a resistant drug.")
        checked += 2
    return checked


def freeze(study: Path, destination: Path, *, workers: int = 3) -> dict:
    destination = destination.resolve()
    destination.relative_to(ROOT.resolve())
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("Frozen-model destination must be empty.")
    if workers < 1:
        raise ValueError("Workers must be positive.")
    report, audit = audit_study(study)
    protocol = BenchmarkProtocol.from_dict(report["protocol"])
    current = environment_manifest(protocol.shared_config(protocol.training_seeds[0]))
    if current != report["environment"]:
        raise ValueError("Current training environment differs from the audited study.")
    for held_out in (evaluation_protocol(protocol), evaluation_protocol(protocol, confirmation=True)):
        held_out.shared_config(protocol.training_seeds[0])
    used = set(protocol.training_seeds)
    for seed in protocol.training_seeds:
        used.update((seed + 1, seed + 2))
    for base in (*protocol.evaluation_seed_bases, protocol.baseline_policy_seed_start):
        used.update(range(base, base + 128 * len(protocol.evaluation_seed_bases)))
    fresh = set()
    for base in (*VALIDATION_SEEDS, *CONFIRMATION_SEEDS, VALIDATION_POLICY_SEED, CONFIRMATION_POLICY_SEED):
        block = set(range(base, base + (640 if base in (VALIDATION_POLICY_SEED, CONFIRMATION_POLICY_SEED) else 128)))
        if used & block or fresh & block:
            raise ValueError("Selection seed schedules overlap prior draws or each other.")
        fresh.update(block)
    tasks = [(study, protocol, seed, strategy, False)
             for strategy in ("ppo", "dqn") for seed in protocol.training_seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        candidates = list(pool.map(evaluate_checkpoint, tasks))
    for candidate in candidates:
        original = next(run for run in report["replicates"] if run["training_seed"] == candidate["training_seed"])
        if candidate["checkpoint_sha256"] != original["checkpoints"][candidate["strategy"]]:
            raise ValueError("A candidate changed after the study audit.")
    selected = {strategy: min((row for row in candidates if row["strategy"] == strategy), key=ranking)
                for strategy in ("ppo", "dqn")}
    confirmation = {strategy: evaluate_checkpoint((study, protocol, row["training_seed"], strategy, True))["validation"]
                    for strategy, row in selected.items()}
    torch.set_num_threads(1)
    confirmation_protocol = evaluation_protocol(protocol, confirmation=True)
    config = confirmation_protocol.shared_config(protocol.training_seeds[0])
    confirmation["random_susceptible_baseline"] = summarize(evaluate_policy(config, confirmation_protocol, GreedyPolicy))
    snapshot = (study / "empirical_interactions.csv").read_bytes()
    if hashlib.sha256(snapshot).hexdigest() != report["interaction_csv_sha256"]:
        raise ValueError("Audited study data snapshot changed.")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "empirical_interactions.csv").write_bytes(snapshot)
    with (destination / "selection.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["strategy", "training_seed", "checkpoint_sha256", "resistance_burden", "resistance_emergence_events", "remaining_susceptible_options"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in sorted(candidates, key=lambda row: (row["strategy"], ranking(row))):
            writer.writerow({field: row.get(field, row["validation"].get(field)) for field in fields})
    selection = {
        "study_id": protocol.study_id, "study_report_sha256": file_hash(study / "report.json"),
        "selection_rule": RANKING, "checkpoint_set": "final fully trained checkpoint from every training replicate",
        "validation_seed_bases": VALIDATION_SEEDS, "validation_policy_seed_start": VALIDATION_POLICY_SEED,
        "confirmation_seed_bases": CONFIRMATION_SEEDS, "confirmation_policy_seed_start": CONFIRMATION_POLICY_SEED,
        "interaction_data_sha256": current["interaction_data_sha256"], "training_steps": protocol.training_timesteps,
        "selected": selected, "confirmation": confirmation, "audited_actions": audit["checked_actions"],
        "scope": "Best measured validation score among available final checkpoints; confirmation is not used for reselection. Profiles are known; stochastic draws are held out. No clinical or general superiority claim.",
        "baseline": "Random susceptible-action code and recorded RNG seeds; no learned checkpoint.",
    }
    write_json(destination / "selection.json", selection)
    template = json.loads((ROOT / "ml/frozen_ppo_manifest.json").read_text(encoding="utf-8"))
    for strategy, row in selected.items():
        folder = destination / strategy
        folder.mkdir()
        source = study / f"seed_{row['training_seed']}" / strategy
        for name in ("final_model.zip", "config.json", "environment_manifest.json", "training_summary.json"):
            data = (source / name).read_bytes()
            if name == "final_model.zip" and hashlib.sha256(data).hexdigest() != row["checkpoint_sha256"]:
                raise ValueError("Selected checkpoint changed before freezing.")
            (folder / name).write_bytes(data)
        manifest = json.loads(json.dumps(template))
        manifest.update(model_id=f"{strategy}_public_v2_seed_{row['training_seed']}",
                        algorithm="MaskablePPO" if strategy == "ppo" else "MaskedDQN")
        manifest["checkpoint"] = {"path": str((folder / "final_model.zip").relative_to(ROOT)).replace("\\", "/"),
                                  "sha256": row["checkpoint_sha256"]}
        manifest["provenance"] = {key: str(path.relative_to(ROOT)).replace("\\", "/") for key, path in {
            "config": folder / "config.json", "environment_manifest": folder / "environment_manifest.json",
            "training_summary": folder / "training_summary.json", "checkpoint_manifest": destination / "selection.json",
        }.items()}
        manifest["simulator"]["interaction_data_path"] = str((destination / "empirical_interactions.csv").relative_to(ROOT)).replace("\\", "/")
        manifest["simulator"]["interaction_data_sha256"] = current["interaction_data_sha256"]
        write_json(folder / "manifest.json", manifest)
    verify_frozen(destination)
    sums = [f"{checksum_of(path, path.read_bytes())}  {path.relative_to(destination).as_posix()}"
            for path in sorted(destination.rglob("*")) if path.is_file()]
    (destination / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return selection


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/frozen/public-data-v2")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    result = freeze(args.study_dir, args.output_dir, workers=args.workers)
    print(json.dumps({"selected": result["selected"], "confirmation": result["confirmation"]}, indent=2))
