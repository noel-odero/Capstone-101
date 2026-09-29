import pytest

from simulation.randomness import Randomness


def test_same_seed_produces_same_sequence():
    first = Randomness(seed=42)
    second = Randomness(seed=42)

    values = ("A", "B", "C", "D")

    first_results = [
        first.choice(values)
        for _ in range(10)
    ]

    second_results = [
        second.choice(values)
        for _ in range(10)
    ]

    assert first_results == second_results


def test_different_seeds_can_produce_different_sequences():
    first = Randomness(seed=42)
    second = Randomness(seed=99)

    values = ("A", "B", "C", "D")

    first_results = [
        first.choice(values)
        for _ in range(10)
    ]

    second_results = [
        second.choice(values)
        for _ in range(10)
    ]

    assert first_results != second_results


def test_unseeded_randomness_is_allowed():
    randomness = Randomness()

    values = ("A", "B", "C")

    result = randomness.choice(values)

    assert result in values


def test_empty_sequence_is_rejected():
    randomness = Randomness(seed=42)

    with pytest.raises(ValueError):
        randomness.choice(())