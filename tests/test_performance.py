import pytest

from evaluators.performance import evaluate_performance


def test_performance_metrics():
    result = evaluate_performance([
        {"success": True, "latency_ms": 100, "correct": True},
        {"success": True, "latency_ms": 200, "correct": False},
        {"success": False},
        {"success": True, "latency_ms": 300, "correct": True},
    ])

    assert result["total_calls"] == 4
    assert result["successful_calls"] == 3
    assert result["failed_calls"] == 1
    assert result["median_latency_ms"] == 200
    assert result["p95_latency_ms"] == 300
    assert result["call_failure_rate"] == 25.0
    assert result["wrong_answer_rate"] == pytest.approx(33.33, abs=0.01)


def test_all_calls_fail():
    result = evaluate_performance([
        {"success": False},
        {"success": False},
    ])

    assert result["call_failure_rate"] == 100.0
    assert result["median_latency_ms"] is None
    assert result["wrong_answer_rate"] is None


def test_empty_observations_rejected():
    with pytest.raises(ValueError):
        evaluate_performance([])


def test_negative_latency_rejected():
    with pytest.raises(ValueError):
        evaluate_performance([
            {"success": True, "latency_ms": -10, "correct": True}
        ])


def test_missing_correctness_rejected():
    with pytest.raises(ValueError):
        evaluate_performance([
            {"success": True, "latency_ms": 100}
        ])
