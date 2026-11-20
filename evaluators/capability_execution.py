import json
from typing import Any

from evaluators.a2a_client import send_message
from evaluators.capability import evaluate_capability
from evaluators.mcp import validate_tool_call_response


def _parse_structured_output(value: Any):
    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None

    return None


def _extract_parts(parts):
    if not isinstance(parts, list):
        return None

    for part in parts:
        if not isinstance(part, dict):
            continue

        if isinstance(part.get("data"), (dict, list)):
            return part["data"]

        parsed = _parse_structured_output(part.get("text"))
        if parsed is not None:
            return parsed

    return None


def extract_a2a_output(validation):
    if validation.get("status") != "PASS":
        return None, "A2A response validation failed."

    response = validation.get("response")
    if not isinstance(response, dict):
        return None, "A2A response was missing."

    result = response.get("result")
    if not isinstance(result, dict):
        return None, "A2A result was missing."

    message = result.get("message")
    if isinstance(message, dict):
        output = _extract_parts(message.get("parts"))
        if output is not None:
            return output, None

    task = result.get("task")
    if isinstance(task, dict):
        state = (task.get("status") or {}).get("state")

        if state != "TASK_STATE_COMPLETED":
            return None, f"A2A task did not complete. State: {state}"

        for artifact in task.get("artifacts", []):
            if isinstance(artifact, dict):
                output = _extract_parts(artifact.get("parts"))
                if output is not None:
                    return output, None

        status_message = (task.get("status") or {}).get("message")
        if isinstance(status_message, dict):
            output = _extract_parts(status_message.get("parts"))
            if output is not None:
                return output, None

    return None, "No structured output could be extracted from the A2A response."


def extract_mcp_output(validation):
    if validation.get("status") != "PASS":
        return None, "MCP tool-call validation did not pass."

    evidence = validation.get("evidence") or {}
    response = evidence.get("response")

    if not isinstance(response, dict):
        return None, "MCP response evidence was missing."

    result = response.get("result", response)

    if not isinstance(result, dict):
        return None, "MCP tool result was invalid."

    if result.get("isError") is True:
        return None, "MCP tool reported an execution error."

    if result.get("resultType") == "input_required":
        return None, "MCP tool requires additional input."

    structured = result.get("structuredContent")
    if isinstance(structured, (dict, list)):
        return structured, None

    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue

            if item.get("type") == "text":
                parsed = _parse_structured_output(item.get("text"))
                if parsed is not None:
                    return parsed, None

    return None, "MCP returned no machine-readable structured output."


def _score_case(test_case, actual_output):
    result = evaluate_capability(
        expected_output=test_case.expected_output,
        actual_output=actual_output,
        tolerance=test_case.tolerance,
    )

    return {
        "test_case_id": test_case.id,
        "name": test_case.name,
        "capability": test_case.capability,
        "status": "PASS" if result.get("accuracy", 0) == 100 else "FAIL",
        **result,
    }


def _not_run(test_case, reason):
    return {
        "test_case_id": test_case.id,
        "name": test_case.name,
        "capability": test_case.capability,
        "status": "NOT_RUN",
        "reason": reason,
    }


async def execute_a2a_test_cases(client, endpoint, test_cases):
    results = []

    for test_case in test_cases:
        try:
            message_text = json.dumps(
                test_case.input,
                ensure_ascii=False,
                default=str,
            )

            validation = await send_message(
                client,
                endpoint,
                message_text,
                allow_private_network=False,
            )

            actual, error = extract_a2a_output(validation)

            if error:
                results.append(_not_run(test_case, error))
                continue

            results.append(_score_case(test_case, actual))

        except Exception as error:
            results.append(
                _not_run(test_case, f"Execution error: {error}")
            )

    return _summarize(results)


def execute_mcp_test_cases(client, test_cases, tool_definitions=None):
    results = []
    tool_definitions = tool_definitions or {}

    for test_case in test_cases:
        if not test_case.tool_name:
            results.append(
                _not_run(
                    test_case,
                    "MCP test case must declare tool_name.",
                )
            )
            continue

        if not isinstance(test_case.input, dict):
            results.append(
                _not_run(
                    test_case,
                    "MCP tool arguments must be a JSON object.",
                )
            )
            continue

        try:
            validation = client.call_tool(
                test_case.tool_name,
                arguments=test_case.input,
                tool_definition=tool_definitions.get(test_case.tool_name),
            )

            actual, error = extract_mcp_output(validation)

            if error:
                results.append(_not_run(test_case, error))
                continue

            results.append(_score_case(test_case, actual))

        except Exception as error:
            results.append(
                _not_run(test_case, f"Execution error: {error}")
            )

    return _summarize(results)


def _summarize(results):
    executed = [
        item for item in results
        if item.get("status") in {"PASS", "FAIL"}
    ]

    passed = sum(
        item["status"] == "PASS"
        for item in executed
    )

    failed = sum(
        item["status"] == "FAIL"
        for item in executed
    )

    not_run = len(results) - len(executed)

    if failed:
        status = "FAIL"
    elif not_run:
        status = "NOT_RUN"
    elif executed:
        status = "PASS"
    else:
        status = "NOT_RUN"

    return {
        "status": status,
        "total": len(results),
        "executed": len(executed),
        "passed": passed,
        "failed": failed,
        "not_run": not_run,
        "accuracy": round(
            passed / len(executed) * 100, 2
        ) if executed else None,
        "test_cases": results,
    }
