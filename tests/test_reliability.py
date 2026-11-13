import pytest

from evaluators.reliability import evaluate_reliability


def test_consistent_outputs():
    result = evaluate_reliability([
        {
            "input_id": "input-1",
            "expected_output": {"answer": "yes"},
            "outputs": [
                {"answer": "yes"},
                {"answer": "yes"},
                {"answer": "yes"},
            ],
        }
    ])

    assert result["consistency"] == 100.0
    assert result["consistent_runs"] == 3
    assert result["random_failures"] == []
    assert result["input_specific_failures"] == []


def test_inconsistent_outputs():
    result = evaluate_reliability([
        {
            "input_id": "input-1",
            "expected_output": {"answer": "yes"},
            "outputs": [
                {"answer": "yes"},
                {"answer": "no"},
                {"answer": "yes"},
            ],
        }
    ])

    assert result["consistency"] == 0.0
    assert result["random_failures"] == ["input-1"]


def test_consistently_wrong_output():
    result = evaluate_reliability([
        {
            "input_id": "input-1",
            "expected_output": {"answer": "yes"},
            "outputs": [
                {"answer": "no"},
                {"answer": "no"},
            ],
        }
    ])

    assert result["consistency"] == 100.0
    assert result["input_specific_failures"] == ["input-1"]


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        evaluate_reliability([])
