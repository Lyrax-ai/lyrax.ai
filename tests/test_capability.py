import pytest

from evaluators.capability import evaluate_capability
from schemas.test_case import ToleranceRule


def test_perfect_capability_accuracy():
    expected = {
        "name": "Acme",
        "invoice": {
            "number": "1042",
            "total": 250.0,
        },
    }

    result = evaluate_capability(expected, expected)

    assert result["accuracy"] == 100.0
    assert result["correct_count"] == 3
    assert result["missing_count"] == 0
    assert result["incorrect_count"] == 0


def test_missing_field():
    expected = {
        "name": "Acme",
        "total": 250.0,
    }

    actual = {
        "name": "Acme",
    }

    result = evaluate_capability(expected, actual)

    assert result["accuracy"] == 50.0
    assert result["missing_count"] == 1
    assert result["missing_fields"][0]["field"] == "total"


def test_incorrect_field():
    expected = {"total": 250.0}
    actual = {"total": 300.0}

    result = evaluate_capability(expected, actual)

    assert result["accuracy"] == 0.0
    assert result["incorrect_count"] == 1


def test_unexpected_field():
    expected = {"name": "Acme"}
    actual = {
        "name": "Acme",
        "extra": "unexpected",
    }

    result = evaluate_capability(expected, actual)

    assert result["accuracy"] == 100.0
    assert result["unexpected_count"] == 1


def test_numeric_tolerance():
    expected = {"total": 250.0}
    actual = {"total": 250.5}

    tolerance = ToleranceRule(
        mode="numeric_tolerance",
        absolute=1.0,
    )

    result = evaluate_capability(
        expected,
        actual,
        tolerance,
    )

    assert result["accuracy"] == 100.0


def test_reject_non_dictionary_outputs():
    with pytest.raises(TypeError):
        evaluate_capability(
            {"total": 250},
            "not a dictionary",
        )
