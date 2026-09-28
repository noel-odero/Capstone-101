import csv
from pathlib import Path


INTERACTIONS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "empirical_interactions.csv"
)

REQUIRED_COLUMNS = {
    "source_id",
    "source",
    "year",
    "evidence_type",
    "from_drug",
    "to_drug",
    "relationship",
    "directionality",
    "evidence_strength",
    "confidence",
    "parameter",
    "parameter_value",
    "observation",
    "transformation",
    "assumption",
    "notes",
}

MVP_DRUGS = {
    "ciprofloxacin",
    "nitrofurantoin",
    "fosfomycin",
    "trimethoprim",
    "gentamicin",
    "mecillinam",
    "ceftazidime",
}


def load_interactions():
    with INTERACTIONS.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def test_required_columns_exist():
    with INTERACTIONS.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)
        assert REQUIRED_COLUMNS.issubset(reader.fieldnames)


def test_only_mvp_drugs_are_included():
    rows = load_interactions()

    for row in rows:
        assert row["from_drug"].lower() in MVP_DRUGS
        assert row["to_drug"].lower() in MVP_DRUGS


def test_observations_are_preserved():
    rows = load_interactions()

    assert all(row["observation"].strip() for row in rows)


def test_transformations_are_explicit():
    rows = load_interactions()

    assert all(row["transformation"].strip() for row in rows)


def test_assumptions_are_documented():
    rows = load_interactions()

    assert all(row["assumption"].strip() for row in rows)


def test_every_interaction_references_a_source():
    rows = load_interactions()

    assert all(row["source_id"].strip() for row in rows)


def test_no_probability_is_stored_in_empirical_layer():
    rows = load_interactions()

    probability_columns = {
        "probability",
        "transition_probability",
        "probability_value",
    }

    with INTERACTIONS.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        columns = set(csv.DictReader(file).fieldnames)

    assert not columns.intersection(probability_columns)
