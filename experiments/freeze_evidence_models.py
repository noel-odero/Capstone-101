"""Select evidence-aware final checkpoints on new draws, then confirm without reselection."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path

import torch
from sb3_contrib import MaskablePPO

from experiments.evidence_environment import ROOT, MASK_RULE, EvidenceDQN, EvidenceKernel, EvidenceSpec
from experiments.evidence_aware_study import evaluate, model_chooser, summarize
from ml.src.artifact_checksums import checksum_of
from ml.src.dqn_benchmark import file_hash, write_json


VALIDATION = (6100001, 6200001, 6300001, 6400001, 6500001)
CONFIRMATION = (7100001, 7200001, 7300001, 7400001, 7500001)
RANKING = "Lowest validation pessimistic score; exact ties: higher completion, fewer repeated selections, lower training seed. Confirmation never reselects."


def verify_study(study: Path) -> tuple[dict, dict]:
    report = json.loads((study / "report.json").read_text())
    manifest = json.loads((study / "run_manifest.json").read_text())
    status = json.loads((study / "status.json").read_text())
    if manifest["stage"] != "full" or status["status"] != "completed" or len(report["replicates"]) != 20:
        raise ValueError("Selection requires a completed twenty-seed full study.")
    if manifest["environment"]["specification"] != {"variant": "supported", "horizon": 8,
            "scenario_id": "REF_UNIFORM_SUPPORTED", "supported_only": True, "repetition_penalty": 0.0}:
        raise ValueError("This release requires the prespecified supported-only, unpenalized objective.")
    if report["run_manifest_sha256"] != file_hash(study / "run_manifest.json"):
        raise ValueError("Study report/manifest mismatch.")
    if file_hash(study / "empirical_interactions.csv") != manifest["environment"]["csv_sha256"]:
        raise ValueError("Study dataset changed.")
    if sorted(r["training_seed"] for r in report["replicates"]) != sorted(manifest["protocol"]["seeds"]):
        raise ValueError("Training-seed set changed.")
    for replicate in report["replicates"]:
        seed = replicate["training_seed"]
        directory = study / f"seed_{seed}"
        if file_hash(directory / "replicate.json") != status["replicate_sha256"][str(seed)]:
            raise ValueError("Replicate summary changed.")
        for name, digest in replicate["checksums"].items():
            if file_hash(directory / name) != digest:
                raise ValueError(f"Study input changed: {directory / name}")
    used = set()
    for seed in manifest["protocol"]["seeds"]:
        used.update((seed, seed + 1, seed + 2))
    for base in (*manifest["protocol"]["evaluation_seed_bases"], 610001, 710001, 910001):
        used.update(range(base, base + 128))
    for base in (*VALIDATION, *CONFIRMATION):
        values = set(range(base, base + 128))
        if used & values:
            raise ValueError("Selection seed schedules overlap prior draws.")
        used.update(values)
    return report, manifest


def evaluate_checkpoint(task):
    study, strategy, seed, seed_bases = task
    torch.set_num_threads(1)
    kernel = EvidenceKernel(EvidenceSpec(), Path(study) / "empirical_interactions.csv")
    checkpoint = Path(study) / f"seed_{seed}" / strategy / "final_model.zip"
    model = (MaskablePPO if strategy == "ppo" else EvidenceDQN).load(checkpoint, device="cpu")
    if strategy == "dqn" and not (model.evidence_mask_table == kernel.mask_table).all():
        raise ValueError("Checkpoint mask differs from the study's evidence mask.")
    choose = model_chooser(model, kernel)
    rows = evaluate(kernel, lambda p, previous, step, rng: choose(p, previous, step), seed_bases)
    summary = summarize(rows)
    if summary["unsupported_steps"] != 0:
        raise ValueError("Unsupported action during selection.")
    print(f"Evaluated {strategy} seed {seed}: score {summary['pessimistic_score']:.6f}", flush=True)
    return {"strategy": strategy, "training_seed": seed, "checkpoint_sha256": file_hash(checkpoint), "validation": summary}


def freeze(study: Path, output: Path, workers: int):
    output = output.resolve()
    output.relative_to(ROOT.resolve())
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Frozen destination must be empty.")
    if workers < 1:
        raise ValueError("Workers must be positive.")
    report, manifest = verify_study(study)
    tasks = [(str(study), strategy, r["training_seed"], VALIDATION)
             for strategy in ("ppo", "dqn") for r in report["replicates"]]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        candidates = list(pool.map(evaluate_checkpoint, tasks))
    def rank(row):
        values = row["validation"]
        return (values["pessimistic_score"], -values["completion_rate"], values["repeated_selections"], row["training_seed"])
    selected = {strategy: min((r for r in candidates if r["strategy"] == strategy), key=rank) for strategy in ("ppo", "dqn")}
    confirmation = {strategy: evaluate_checkpoint((str(study), strategy, r["training_seed"], CONFIRMATION))["validation"]
                    for strategy, r in selected.items()}
    verify_study(study)
    output.mkdir(parents=True, exist_ok=True)
    (output / "empirical_interactions.csv").write_bytes((study / "empirical_interactions.csv").read_bytes())
    selection = {"study_report_sha256": file_hash(study / "report.json"), "study_manifest": manifest,
                 "selection_rule": RANKING, "validation_seed_bases": VALIDATION,
                 "confirmation_seed_bases": CONFIRMATION, "candidates": candidates,
                 "selected": selected, "confirmation": confirmation,
                 "scope": "Known profiles; held-out stochastic draws. Best measured validation checkpoint per algorithm, not proof of algorithm superiority or biological validity."}
    write_json(output / "selection.json", selection)
    with (output / "selection.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("strategy", "seed", "validation_score", "completion", "repeated_selections"))
        for row in sorted(candidates, key=lambda r: (r["strategy"], rank(r))):
            writer.writerow((row["strategy"], row["training_seed"], row["validation"]["pessimistic_score"],
                             row["validation"]["completion_rate"], row["validation"]["repeated_selections"]))
    template = json.loads((ROOT / "artifacts/frozen/public-data-v2/ppo/manifest.json").read_text())
    for strategy, row in selected.items():
        folder = output / strategy
        folder.mkdir()
        original = study / f"seed_{row['training_seed']}" / strategy
        for name in ("final_model.zip", "config.json"):
            (folder / name).write_bytes((original / name).read_bytes())
        if file_hash(folder / "final_model.zip") != row["checkpoint_sha256"]:
            raise ValueError("Checkpoint changed during packaging.")
        write_json(folder / "environment_manifest.json", manifest["environment"])
        frozen = json.loads(json.dumps(template))
        relative = lambda path: path.relative_to(ROOT).as_posix()
        frozen.update(manifest_version=2, model_id=f"{strategy}_evidence_v3_seed_{row['training_seed']}",
                      algorithm="MaskablePPO" if strategy == "ppo" else "MaskedDQN")
        frozen["checkpoint"] = {"path": relative(folder / "final_model.zip"), "sha256": row["checkpoint_sha256"]}
        frozen["provenance"] = {"config": relative(folder / "config.json"),
                                "environment_manifest": relative(folder / "environment_manifest.json"),
                                "checkpoint_manifest": relative(output / "selection.json")}
        frozen["simulator"].update(interaction_data_path=relative(output / "empirical_interactions.csv"),
                                  interaction_data_sha256=manifest["environment"]["interaction_data_sha256"])
        frozen["action_masking"] = {"rule": MASK_RULE}
        frozen["evidence_environment"] = manifest["environment"]
        write_json(folder / "manifest.json", frozen)
    sums = [f"{checksum_of(p, p.read_bytes())}  {p.relative_to(output).as_posix()}" for p in sorted(output.rglob("*")) if p.is_file()]
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(freeze(args.study_dir, args.output_dir, args.workers), indent=2))
