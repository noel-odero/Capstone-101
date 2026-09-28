import csv
from pathlib import Path


REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "evidence_registry.csv"
)

REQUIRED_COLUMNS = {
    "source_id",
    "source",
    "year",
    "evidence_type",
    "organism",
    "clinical_context",
    "from_drug",
    "to_drug",
    "relationship",
    "directionality",
    "evidence_strength",
    "strain_count",
    "observation",
    "notes",
}


def load_registry():
    with REGISTRY.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_required_columns():
    with REGISTRY.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        assert REQUIRED_COLUMNS.issubset(reader.fieldnames)


def test_no_duplicate_relationships():
    rows = load_registry()

    keys = [
        (
            row["source_id"],
            row["from_drug"],
            row["to_drug"],
            row["relationship"],
        )
        for row in rows
    ]

    assert len(keys) == len(set(keys))


def test_no_self_relationships():
    rows = load_registry()

    assert all(
        row["from_drug"] != row["to_drug"]
        for row in rows
    )


def test_valid_relationship_types():
    rows = load_registry()

    assert all(row["relationship"] in {"CS", "CR", "neutral", "mixed", "unknown"} for row in rows)


def test_valid_directionality():
    rows = load_registry()

    assert all(
        row["directionality"] in {"A_to_B", "B_to_A", "bidirectional"}
        for row in rows
    )


def test_strain_counts_are_valid():
    rows = load_registry()

    for row in rows:
        if row["strain_count"]:
            count = int(row["strain_count"])
            assert count >= 1
            assert count <= 10