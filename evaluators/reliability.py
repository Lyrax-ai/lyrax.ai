import json


def normalize(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def evaluate_reliability(input_runs: list[dict]) -> dict:
    if not input_runs:
        raise ValueError("At least one input group is required.")

    total_runs = 0
    consistent_runs = 0
    random_failures = []
    input_specific_failures = []
    evidence = []

    for group in input_runs:
        input_id = group.get("input_id")
        expected = group.get("expected_output")
        outputs = group.get("outputs")

        if not input_id or not isinstance(outputs, list) or not outputs:
            raise ValueError(
                "Each group requires an input_id and non-empty outputs."
            )

        total_runs += len(outputs)

        normalized = [normalize(output) for output in outputs]
        is_consistent = len(set(normalized)) == 1

        if is_consistent:
            consistent_runs += len(outputs)
        else:
            random_failures.append(input_id)

        matches_expected = all(
            output == expected for output in outputs
        )

        if is_consistent and not matches_expected:
            input_specific_failures.append(input_id)

        evidence.append({
            "input_id": input_id,
            "expected_output": expected,
            "outputs": outputs,
            "consistent": is_consistent,
            "matches_expected": matches_expected,
        })

    consistency = consistent_runs / total_runs * 100

    return {
        "consistency": round(consistency, 2),
        "total_runs": total_runs,
        "consistent_runs": consistent_runs,
        "random_failures": random_failures,
        "input_specific_failures": input_specific_failures,
        "evidence": evidence,
    }
