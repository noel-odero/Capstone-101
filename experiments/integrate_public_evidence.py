"""Rebuild the training evidence tables from archived v1 and verified public extracts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/versions/interactions-v1"
PUBLIC = ROOT / "data/research/transition-data-2026-10-23"
PROCESSED = ROOT / "data/processed"
RELATIONSHIPS = {"CS": "CS", "XR": "CR", "Neutral": "neutral"}
TRANSITIONS = {"CS": "collateral_sensitivity", "CR": "cross_resistance", "neutral": "neutral"}
ABSTRACTION = (
    "Qualitative research abstraction: relative susceptibility effects define candidate binary "
    "state changes, not demonstrated clinical breakpoint crossings. Endpoint frequencies are "
    "not per-exposure probabilities; REF_UNIFORM_SUPPORTED samples unique applicable outcomes uniformly."
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames), list(reader)


def csv_text(fields: list[str], rows: list[dict[str, str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    return stream.getvalue()


def public_records() -> list[dict[str, str]]:
    def record(source_id, source, year, origin, target, relationship, count, context, observation, notes):
        return {
            "source_id": source_id, "source": source, "year": str(year),
            "evidence_type": "experimental_evolution", "organism": "E. coli",
            "clinical_context": context, "from_drug": origin, "to_drug": target,
            "relationship": relationship, "directionality": "A_to_B",
            "evidence_strength": "strong", "confidence": "moderate", "strain_count": str(count),
            "parameter": "transition_relationship", "parameter_value": relationship,
            "observation": observation,
            "transformation": "Preserve each measured outcome group as a separate candidate; normalize XR to CR. "
            "Map relative susceptibility effects to the simulator's binary state only under the stated research abstraction.",
            "assumption": ABSTRACTION, "notes": notes,
        }

    _, groups = read_csv(PUBLIC / "sakenova-directed-outcomes.csv")
    records = []
    for group in groups:
        count, total = map(int, group["lineage_frequency"].split("/"))
        records.append(record(
            "SAK2025_EXP", "Sakenova et al.", 2025, group["from_drug"], group["to_drug"],
            RELATIONSHIPS[group["observed_group"]], count,
            "BW25113 laboratory evolution; approximately 50 generations; lineage outcome group",
            f"{group['observed_group']} in {count}/{total} reported lineages; group mean log2 IC90 fold change "
            f"{group['group_mean_log2_ic90_fold_change']}.",
            f"DOI:10.1038/s41564-024-01857-w; Source Data Fig.3, sheet {group['source_sheet']}, "
            f"Excel row {group['source_excel_row']}; strain_count counts lineages in this outcome group, "
            "not independent clinical backgrounds. Preserve neutral and conflicting groups; do not weight candidates by frequency.",
        ))

    _, mic = read_csv(PUBLIC / "ibacache-gen-mic.csv")
    normal = [row for row in mic if row["background"] == "MG1655"]
    ancestor = next(row for row in normal if row["role"] == "ancestor")
    clones = [row for row in normal if row["role"] == "evolved_clone"]
    assert len(clones) == 22 and ancestor["fosfomycin_mic"] == "0.25"
    assert all(row["fosfomycin_mic"] == "\u22658" for row in clones)
    records.append(record(
        "IBACACHE2018", "Ibacache-Quiroga et al.", 2018, "gentamicin", "fosfomycin", "CR", len(clones),
        "MG1655 laboratory background; gentamicin-evolved sampled clones; hypermutator ancestor excluded",
        "Fosfomycin MIC >=8 ug/mL in 22 sampled MG1655-derived clones versus ancestor 0.25 ug/mL (>=32-fold increase).",
        "DOI:10.3389/fmicb.2018.00427; DataSheet1.docx, Supplementary Table S5. "
        "Censored MIC lower bounds retained. Clones are nested samples, not 22 independent evolution populations. "
        "Table S6 delta-dnaQ ancestor cohort excluded rather than pooled with the MG1655 ancestor cohort. "
        "GEN-to-CIP and GEN-to-TMP clone heterogeneity is retained in the raw extract, not extrapolated into additional rules.",
    ))

    _, mic = read_csv(PUBLIC / "phillips-caz-cip-mic.csv")
    ancestor = next(row for row in mic if row["selection_arm"] == "ancestor")
    baseline = mean(float(ancestor[f"ciprofloxacin_mic_rep{i}"]) for i in (1, 2))
    valid = [row for row in mic if row["selection_arm"] == "CEF" and row["ciprofloxacin_mic_rep1"] != "no o/n"]
    population_effects = [mean(
        mean(float(row[f"ciprofloxacin_mic_rep{i}"]) for i in (1, 2)) / baseline
        for row in valid if row["evolution_population"] == population
    ) for population in ("1", "2", "3")]
    assert len(valid) == 8 and abs(mean(population_effects) - 4.222222222222222) < 1e-12
    records.append(record(
        "PHILLIPS2026", "Phillips et al.", 2026, "ceftazidime", "ciprofloxacin", "CR", len(valid),
        "MG1655 laboratory evolution; ceftazidime-only CEF arm; three evolution populations",
        "Ciprofloxacin MIC increased; population mean fold changes 4, 6.6666666667 and 2; mean 4.2222222222.",
        "DOI:10.1093/g3journal/jkag046; Figshare:10.25387/g3.29630732; CEFBOR_MIC_pub.xlsx, "
        "raw_MIC rows 9 and 12-22, CIP columns I-J; MIC_compiled row 14. Eight valid clones nested in three populations; "
        "CEF 1C missing (no o/n); technical duplicates and sibling clones are not independent trials. "
        "Combination-selection arms excluded. Relative increased MIC is not a calibrated clinical resistance event.",
    ))
    return records


def build_tables() -> dict[str, str]:
    def training_rows(rows):
        return [row for row in rows if row["directionality"] == "A_to_B"]

    additions = public_records()
    fields, empirical = read_csv(ARCHIVE / "empirical_interactions.csv")
    registry_fields, registry = read_csv(ARCHIVE / "evidence_registry.csv")
    for rows in (empirical, registry):
        for row in rows:
            if row["source_id"] == "JAMES2024":
                row["notes"] += "; public raw MICs: data/research/transition-data-2026-10-23/james-mic.csv; three clinical backgrounds, ten resistant derivatives, three measurements per drug/strain."
                if row["to_drug"] == "nitrofurantoin":
                    row["notes"] += " Reported MIC increases remained below the clinical resistance breakpoint. Binary flip retained only as an explicit research assumption."
                    row["assumption"] = ABSTRACTION
    empirical.extend(additions)
    registry.extend(additions)
    outputs = {
        "empirical_interactions.csv": csv_text(fields, training_rows(empirical)),
        "evidence_registry.csv": csv_text(registry_fields, registry),
    }
    for name in ("transition_parameters.csv", "transition_uncertainty.csv"):
        fields, rows = read_csv(ARCHIVE / name)
        for row in rows:
            if row["source_id"] == "JAMES2024" and row["to_drug"] == "nitrofurantoin":
                if name == "transition_parameters.csv":
                    row["assumption"] = ABSTRACTION
                else:
                    row["uncertainty_type"] = "model_abstraction"
                    row["notes"] = "Observed relative MIC increase below the clinical resistance breakpoint; binary flip is a research assumption, not an established clinical resistance event."
        for new in additions:
            derived = dict(new)
            derived.update(
                transition_type=TRANSITIONS[new["relationship"]], probability="", probability_source="",
                derivation_method="Measured directional endpoint outcome; binary research abstraction; no fitted transition probability.",
                uncertainty_type="heterogeneous_observation" if new["source_id"] == "SAK2025_EXP" else "model_abstraction",
                probability_status="unresolved",
            )
            rows.append(derived)
        outputs[name] = csv_text(fields, training_rows(rows))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check deterministic outputs without writing.")
    args = parser.parse_args()
    outputs = build_tables()
    for name, content in outputs.items():
        path = PROCESSED / name
        current = path.read_text(encoding="utf-8-sig")
        if args.check:
            if current != content:
                raise SystemExit(f"Evidence table differs from its public-data derivation: {name}")
        elif current not in (content, (ARCHIVE / name).read_text(encoding="utf-8-sig")):
            raise SystemExit(f"Refusing to overwrite independently changed evidence table: {name}")
    if not args.check:
        for name, content in outputs.items():
            path = PROCESSED / name
            path.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(outputs["empirical_interactions.csv"].encode()).hexdigest()
    record_count = len(list(csv.DictReader(io.StringIO(outputs["empirical_interactions.csv"]))))
    print(f"{'Verified' if args.check else 'Integrated'} 20 public evidence rows; {record_count} training records; CSV SHA256 {digest}")


if __name__ == "__main__":
    main()
