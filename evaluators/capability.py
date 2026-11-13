from numbers import Real
from typing import Any


def flatten_fields(data: dict, prefix: str = "") -> dict:
    result = {}

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)

        if isinstance(value, dict):
            result.update(flatten_fields(value, path))
        else:
            result[path] = value

    return result


def values_match(expected: Any, actual: Any, tolerance) -> bool:
    if (
        isinstance(expected, Real)
        and not isinstance(expected, bool)
        and isinstance(actual, Real)
        and not isinstance(actual, bool)
    ):
        if tolerance.mode == "numeric_tolerance":
            difference = abs(expected - actual)
            allowed = max(
                tolerance.absolute,
                tolerance.relative * abs(expected),
            )
            return difference <= allowed

    return type(expected) is type(actual) and expected == actual


def evaluate_capability(
    expected_output: dict,
    actual_output: dict,
    tolerance=None,
) -> dict:
    from schemas.test_case import ToleranceRule

    if not isinstance(expected_output, dict):
        raise TypeError("Expected output must be a dictionary.")

    if not isinstance(actual_output, dict):
        raise TypeError("Actual output must be a dictionary.")

    if tolerance is None:
        tolerance = ToleranceRule()

    expected = flatten_fields(expected_output)
    actual = flatten_fields(actual_output)

    correct = []
    incorrect = []
    missing = []
    unexpected = []

    for field, expected_value in expected.items():
        if field not in actual:
            missing.append({
                "field": field,
                "expected": expected_value,
            })
            continue

        actual_value = actual[field]

        if values_match(expected_value, actual_value, tolerance):
            correct.append({
                "field": field,
                "expected": expected_value,
                "actual": actual_value,
            })
        else:
            incorrect.append({
                "field": field,
                "expected": expected_value,
                "actual": actual_value,
            })

    for field, actual_value in actual.items():
        if field not in expected:
            unexpected.append({
                "field": field,
                "actual": actual_value,
            })

    total_expected = len(expected)
    accuracy = (
        len(correct) / total_expected * 100
        if total_expected
        else 0.0
    )

    return {
        "accuracy": round(accuracy, 2),
        "total_expected_fields": total_expected,
        "correct_count": len(correct),
        "incorrect_count": len(incorrect),
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "correct_fields": correct,
        "incorrect_fields": incorrect,
        "missing_fields": missing,
        "unexpected_fields": unexpected,
    }
