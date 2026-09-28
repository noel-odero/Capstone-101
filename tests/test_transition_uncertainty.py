import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

UNCERTAINTY_FILE = ROOT / "data" / "processed" / "transition_uncertainty.csv"
EMPIRICAL_FILE = ROOT / "data" / "processed" / "empirical_interactions.csv"


REQUIRED_COLUMNS = {
    "source_id",
    "from_drug",
    "to_drug",
    "relationship",
    "evidence_strength",
    "confidence",
    "directionality",
    "uncertainty_type",
    "probability_status",
    "notes",
}

ALLOWED_EVIDENCE_STRENGTHS = {
    "strong",
    "moderate",
    "weak",
}

ALLOWED_CONFIDENCE = {
    "high",
    "medium",
    "low",
}

ALLOWED_DIRECTIONALITY = {
    "A_to_B",
    "B_to_A",
    "bidirectional",
    "unknown",
}

ALLOWED_UNCERTAINTY_TYPES = {
    "probability_unresolved",
    "directionality_unknown",
    "context_dependent",
    "heterogeneous_observation",
    "model_abstraction",
}

ALLOWED_PROBABILITY_STATUS = {
    "unresolved",
    "calibrated",
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
    with UNCERTAINTY_FILE.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        assert REQUIRED_COLUMNS.issubset(set(reader.fieldnames))


def test_uncertainty_layer_has_same_number_of_records():
    uncertainty = load_csv(UNCERTAINTY_FILE)
    empirical = load_csv(EMPIRICAL_FILE)

    assert len(uncertainty) == len(empirical)


def test_every_uncertainty_record_references_empirical_observation():
    uncertainty = load_csv(UNCERTAINTY_FILE)
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

    for row in uncertainty:
        key = (
            row["source_id"],
            normalize_drug(row["from_drug"]),
            normalize_drug(row["to_drug"]),
            row["relationship"],
        )

        assert key in empirical_keys


def test_empirical_relationships_are_preserved():
    uncertainty = load_csv(UNCERTAINTY_FILE)
    empirical = load_csv(EMPIRICAL_FILE)

    empirical_relationships = {
        (
            row["source_id"],
            normalize_drug(row["from_drug"]),
            normalize_drug(row["to_drug"]),
        ): row["relationship"]
        for row in empirical
    }

    for row in uncertainty:
        key = (
            row["source_id"],
            normalize_drug(row["from_drug"]),
            normalize_drug(row["to_drug"]),
        )

        assert row["relationship"] == empirical_relationships[key]


def test_evidence_strength_values_are_valid():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(
        row["evidence_strength"] in ALLOWED_EVIDENCE_STRENGTHS
        for row in rows
    )


def test_confidence_values_are_valid():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(
        row["confidence"] in ALLOWED_CONFIDENCE
        for row in rows
    )


def test_directionality_values_are_valid():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(
        row["directionality"] in ALLOWED_DIRECTIONALITY
        for row in rows
    )


def test_uncertainty_types_are_valid():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(
        row["uncertainty_type"] in ALLOWED_UNCERTAINTY_TYPES
        for row in rows
    )


def test_probability_status_values_are_valid():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(
        row["probability_status"] in ALLOWED_PROBABILITY_STATUS
        for row in rows
    )


def test_unresolved_probability_has_no_calibrated_value():
    rows = load_csv(UNCERTAINTY_FILE)

    for row in rows:
        if row["probability_status"] == "unresolved":
            assert row["probability_status"] != "calibrated"


def test_uncertainty_does_not_contain_probability_values():
    rows = load_csv(UNCERTAINTY_FILE)

    fieldnames = set(rows[0].keys())

    assert "probability" not in fieldnames
    assert "transition_probability" not in fieldnames


def test_directionality_unknown_is_explicit():
    rows = load_csv(UNCERTAINTY_FILE)

    for row in rows:
        if row["uncertainty_type"] == "directionality_unknown":
            assert row["directionality"] == "unknown"


def test_every_record_has_documented_notes():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(row["notes"].strip() for row in rows)


def test_source_ids_are_not_empty():
    rows = load_csv(UNCERTAINTY_FILE)

    assert all(row["source_id"].strip() for row in rows)
