import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = ROOT / "data" / "processed" / "transition_sampling_config.csv"
EMPIRICAL_FILE = ROOT / "data" / "processed" / "empirical_interactions.csv"


REQUIRED_COLUMNS = {
    "source_id",
    "from_drug",
    "to_drug",
    "relationship",
    "sampling_method",
    "outcome",
    "probability",
    "probability_source",
    "configuration_assumption",
}

ALLOWED_SAMPLING_METHODS = {
    "deterministic",
    "categorical",
    "unresolved",
}

ALLOWED_OUTCOMES = {
    "no_change",
    "cross_resistance",
    "collateral_sensitivity",
    "neutral",
}

ALLOWED_PROBABILITY_SOURCES = {
    "empirical",
    "calibrated",
    "model_assumption",
    "reference_scenario",
    "unresolved",
}


def load_csv(path):
    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def normalize_drug(value):
    return value.strip().upper()


def test_required_columns_exist():
    with CONFIG_FILE.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        assert REQUIRED_COLUMNS.issubset(set(reader.fieldnames))


def test_configuration_is_empty_until_sampling_rules_are_calibrated():
    rows = load_csv(CONFIG_FILE)

    assert rows == []


def test_sampling_methods_are_valid():
    rows = load_csv(CONFIG_FILE)

    assert all(
        row["sampling_method"] in ALLOWED_SAMPLING_METHODS
        for row in rows
    )


def test_outcomes_are_valid():
    rows = load_csv(CONFIG_FILE)

    assert all(
        row["outcome"] in ALLOWED_OUTCOMES
        for row in rows
    )


def test_probability_sources_are_valid():
    rows = load_csv(CONFIG_FILE)

    assert all(
        row["probability_source"] in ALLOWED_PROBABILITY_SOURCES
        for row in rows
    )


def test_probabilities_are_between_zero_and_one():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["probability"].strip():
            probability = float(row["probability"])
            assert 0.0 <= probability <= 1.0


def test_unresolved_sampling_has_no_probability():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["sampling_method"] == "unresolved":
            assert row["probability"].strip() == ""


def test_unresolved_probability_source_has_no_probability():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["probability_source"] == "unresolved":
            assert row["probability"].strip() == ""


def test_configured_probability_requires_source():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["probability"].strip():
            assert row["probability_source"].strip()
            assert row["configuration_assumption"].strip()


def test_deterministic_sampling_requires_probability_one():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["sampling_method"] == "deterministic":
            assert row["probability"].strip()
            assert float(row["probability"]) == 1.0


def test_model_assumptions_are_documented():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["probability_source"] == "model_assumption":
            assert row["configuration_assumption"].strip()


def test_every_configured_source_exists_in_empirical_data():
    rows = load_csv(CONFIG_FILE)
    empirical = load_csv(EMPIRICAL_FILE)

    source_ids = {
        row["source_id"]
        for row in empirical
    }

    assert all(
        row["source_id"] in source_ids
        for row in rows
    )


def test_configured_relationship_matches_empirical_evidence():
    rows = load_csv(CONFIG_FILE)
    empirical = load_csv(EMPIRICAL_FILE)

    empirical_keys = {
        (
            row["source_id"],
            normalize_drug(row["from_drug"]),
            normalize_drug(row["to_drug"]),
            row["relationship"],
        )
        for row in empirical
    }

    for row in rows:
        key = (
            row["source_id"],
            normalize_drug(row["from_drug"]),
            normalize_drug(row["to_drug"]),
            row["relationship"],
        )

        assert key in empirical_keys


def test_configuration_assumptions_are_traceable():
    rows = load_csv(CONFIG_FILE)

    for row in rows:
        if row["probability"].strip():
            assert row["configuration_assumption"].strip()
