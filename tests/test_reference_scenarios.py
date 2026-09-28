import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCENARIOS_FILE = ROOT / "data" / "processed" / "reference_scenarios.csv"


EXPECTED_DRUGS = {
    "CIPROFLOXACIN",
    "NITROFURANTOIN",
    "FOSFOMYCIN",
    "TRIMETHOPRIM",
    "GENTAMICIN",
    "MECILLINAM",
    "CEFTAZIDIME",
}

EXPECTED_STATE_LENGTH = 7

REQUIRED_COLUMNS = {
    "scenario_id",
    "scenario_type",
    "description",
    "initial_state",
    "action",
    "expected_effective",
    "expected_outcome",
    "expected_next_state",
    "evidence_source",
    "scenario_purpose",
}

ALLOWED_EFFECTIVENESS = {"0", "1"}

ALLOWED_OUTCOMES = {
    "no_change",
    "cross_resistance",
    "collateral_sensitivity",
    "neutral",
    "terminal",
}


def load_csv():
    with SCENARIOS_FILE.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def test_required_columns_exist():
    with SCENARIOS_FILE.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        assert REQUIRED_COLUMNS.issubset(set(reader.fieldnames))


def test_scenario_ids_are_unique():
    rows = load_csv()

    ids = [row["scenario_id"] for row in rows]

    assert len(ids) == len(set(ids))


def test_initial_states_have_seven_values():
    rows = load_csv()

    for row in rows:
        state = row["initial_state"]

        assert len(state) == EXPECTED_STATE_LENGTH
        assert all(value in {"0", "1"} for value in state)


def test_expected_next_states_have_seven_values():
    rows = load_csv()

    for row in rows:
        state = row["expected_next_state"]

        assert len(state) == EXPECTED_STATE_LENGTH
        assert all(value in {"0", "1"} for value in state)


def test_actions_are_in_mvp_action_space():
    rows = load_csv()

    for row in rows:
        assert row["action"] in EXPECTED_DRUGS


def test_effectiveness_values_are_valid():
    rows = load_csv()

    assert all(
        row["expected_effective"] in ALLOWED_EFFECTIVENESS
        for row in rows
    )


def test_outcomes_are_valid():
    rows = load_csv()

    assert all(
        row["expected_outcome"] in ALLOWED_OUTCOMES
        for row in rows
    )


def test_scenarios_have_documented_purpose():
    rows = load_csv()

    assert all(
        row["scenario_purpose"].strip()
        for row in rows
    )


def test_scenarios_have_documented_description():
    rows = load_csv()

    assert all(
        row["description"].strip()
        for row in rows
    )


def test_effective_scenario_is_consistent():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF001"
    )

    # The actual canonical drug order is tested separately by the state
    # implementation. Here we only verify the fixture's declared behavior.
    assert scenario["expected_effective"] == "1"
    assert scenario["expected_outcome"] == "no_change"


def test_ineffective_scenario_is_consistent():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF002"
    )

    assert scenario["expected_effective"] == "0"
    assert scenario["expected_outcome"] == "no_change"


def test_cross_resistance_fixture_changes_only_target_resistance():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF003"
    )

    assert scenario["initial_state"] == "0000000"
    assert scenario["expected_next_state"] == "0000100"
    assert scenario["expected_outcome"] == "cross_resistance"


def test_collateral_sensitivity_fixture_changes_only_target_resistance():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF004"
    )

    assert scenario["initial_state"] == "0000100"
    assert scenario["expected_next_state"] == "0000000"
    assert scenario["expected_outcome"] == "collateral_sensitivity"


def test_neutral_fixture_does_not_change_state():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF005"
    )

    assert scenario["initial_state"] == scenario["expected_next_state"]
    assert scenario["expected_outcome"] == "neutral"


def test_terminal_fixture_has_no_effective_antibiotic():
    rows = load_csv()

    scenario = next(
        row for row in rows
        if row["scenario_id"] == "REF006"
    )

    assert scenario["initial_state"] == "1111111"
    assert scenario["expected_effective"] == "0"
    assert scenario["expected_outcome"] == "terminal"
