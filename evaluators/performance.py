from statistics import median
from math import ceil


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)

    if not ordered:
        raise ValueError("At least one value is required.")

    if not 0 <= percentile_value <= 100:
        raise ValueError("Percentile must be between 0 and 100.")

    index = max(0, ceil(percentile_value / 100 * len(ordered)) - 1)
    return ordered[index]


def evaluate_performance(observations: list[dict]) -> dict:
    if not observations:
        raise ValueError("At least one observation is required.")

    failed_calls = 0
    valid_responses = 0
    incorrect_answers = 0
    successful_latencies = []

    for item in observations:
        if "success" not in item:
            raise ValueError("Each observation must define success.")

        if not isinstance(item["success"], bool):
            raise ValueError("The success field must be boolean.")

        if not item["success"]:
            failed_calls += 1
            continue

        latency = item.get("latency_ms")

        if (
            not isinstance(latency, (int, float))
            or isinstance(latency, bool)
            or latency < 0
        ):
            raise ValueError(
                "Successful calls require a non-negative latency_ms."
            )

        successful_latencies.append(float(latency))
        valid_responses += 1

        if "correct" not in item:
            raise ValueError(
                "Successful responses must define correct."
            )

        if not isinstance(item["correct"], bool):
            raise ValueError("The correct field must be boolean.")

        if not item["correct"]:
            incorrect_answers += 1

    total_calls = len(observations)

    return {
        "total_calls": total_calls,
        "successful_calls": valid_responses,
        "failed_calls": failed_calls,
        "median_latency_ms": (
            median(successful_latencies)
            if successful_latencies else None
        ),
        "p95_latency_ms": (
            percentile(successful_latencies, 95)
            if successful_latencies else None
        ),
        "call_failure_rate": round(
            failed_calls / total_calls * 100, 2
        ),
        "wrong_answer_rate": round(
            incorrect_answers / valid_responses * 100, 2
        ) if valid_responses else None,
    }
