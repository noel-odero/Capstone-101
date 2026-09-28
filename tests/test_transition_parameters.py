import csv
from pathlib import Path


PARAMETERS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "transition_parameters.csv"
)

INTERACTIONS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "empirical_interactions.csv"
)


REQUIRED_COLUMNS = {
    "source_id",
    "from_drug",
    "to_drug",
    "relationship",
    "directionality",
    "transition_type",
    "probability",
    "probability_source",
    "derivation_method",
    "assumption",
}


def load_csv(path):
    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def test_required_columns_exist():
    with PARAMETERS.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)
        assert REQUIRED_COLUMNS.issubset(reader.fieldnames)


def test_every_derived_value_references_source():
    parameters = load_csv(PARAMETERS)
    interactions = load_csv(INTERACTIONS)

    source_keys = {
        (
            row["source_id"],
            row["from_drug"],
            row["to_drug"],
            row["relationship"],
        )
        for row in interactions
    }

    for row in parameters:
        key = (
            row["source_id"],
            row["from_drug"],
            row["to_drug"],
            row["relationship"],
        )

        assert key in source_keys


def test_assumptions_are_documented():
    rows = load_csv(PARAMETERS)

    assert all(row["assumption"].strip() for row in rows)


def test_derivation_methods_are_documented():
    rows = load_csv(PARAMETERS)

    assert all(row["derivation_method"].strip() for row in rows)


def test_probabilities_are_not_invented():
    rows = load_csv(PARAMETERS)

    assert all(row["probability"].strip() == "" for row in rows)


def test_probability_sources_are_empty_when_probability_is_empty():
    rows = load_csv(PARAMETERS)

    for row in rows:
        if not row["probability"].strip():
            assert not row["probability_source"].strip()


def test_transition_types_are_valid():
    rows = load_csv(PARAMETERS)

    assert all(
        row["transition_type"]
        in {
            "cross_resistance",
            "collateral_sensitivity",
            "neutral",
        }
        for row in rows
    )


def test_parameter_count_matches_empirical_layer():
    parameters = load_csv(PARAMETERS)
    interactions = load_csv(INTERACTIONS)

    assert len(parameters) == len(interactions)
