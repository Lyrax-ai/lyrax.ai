import asyncio
import json
import time
from typing import Any

from evaluators.a2a_client import send_message, get_task
from evaluators.capability import evaluate_capability


MAX_TASK_POLLS = 10
TASK_POLL_INTERVAL = 1.0

RUNNING_STATES = {
    "TASK_STATE_UNSPECIFIED",
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
}

UNSUPPORTED_STATES = {
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_AUTH_REQUIRED",
}


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


def _extract_completed_task(task):
    if not isinstance(task, dict):
        return None, "A2A task response was invalid."

    status = task.get("status")
    state = status.get("state") if isinstance(status, dict) else None

    if state != "TASK_STATE_COMPLETED":
        return None, f"A2A task did not complete. State: {state}"

    artifacts = task.get("artifacts", [])

    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                output = _extract_parts(artifact.get("parts"))
                if output is not None:
                    return output, None

    status_message = status.get("message") if isinstance(status, dict) else None

    if isinstance(status_message, dict):
        output = _extract_parts(status_message.get("parts"))
        if output is not None:
            return output, None

    return None, "Completed A2A task contained no structured output."


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

        return None, "A2A message contained no structured output."

    task = result.get("task")

    if isinstance(task, dict):
        return _extract_completed_task(task)

    return None, "A2A response contained neither a message nor a task."


async def _execute_a2a_case(
    client,
    endpoint,
    test_case,
    max_polls=MAX_TASK_POLLS,
    poll_interval=TASK_POLL_INTERVAL,
):
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

    if validation.get("status") != "PASS":
        return _not_run(test_case, "A2A SendMessage validation failed.")

    response = validation.get("response") or {}
    result = response.get("result") or {}

    if isinstance(result.get("message"), dict):
        actual, error = extract_a2a_output(validation)

        if error:
            return _not_run(test_case, error)

        return _score_case(test_case, actual)

    task = result.get("task")

    if not isinstance(task, dict):
        return _not_run(test_case, "A2A response did not contain a valid task.")

    task_id = task.get("id")
    status = task.get("status") or {}
    state = status.get("state")

    if not task_id:
        return _not_run(test_case, "A2A task did not provide an ID.")

    if state == "TASK_STATE_COMPLETED":
        actual, error = _extract_completed_task(task)

        if error:
            return _not_run(test_case, error)

        return _score_case(test_case, actual)

    if state in UNSUPPORTED_STATES:
        return _not_run(
            test_case,
            f"A2A task requires additional interaction. State: {state}",
        )

    if state not in RUNNING_STATES:
        return _not_run(
            test_case,
            f"A2A task cannot be evaluated. State: {state}",
        )

    for poll_number in range(1, max_polls + 1):
        await asyncio.sleep(poll_interval)

        task_validation = await get_task(
            client,
            endpoint,
            task_id,
            allow_private_network=False,
        )

        if task_validation.get("status") != "PASS":
            return _not_run(
                test_case,
                "A2A GetTask validation failed.",
            )

        updated_task = task_validation.get("task")
        updated_state = task_validation.get("task_state")

        if updated_state == "TASK_STATE_COMPLETED":
            actual, error = _extract_completed_task(updated_task)

            if error:
                return _not_run(test_case, error)

            return _score_case(test_case, actual)

        if updated_state in UNSUPPORTED_STATES:
            return _not_run(
                test_case,
                f"A2A task requires additional interaction. State: {updated_state}",
            )

        if updated_state not in RUNNING_STATES:
            return _not_run(
                test_case,
                f"A2A task ended without successful completion. State: {updated_state}",
            )

    return _not_run(
        test_case,
        f"A2A task timed out after {max_polls} polling attempts.",
    )


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
            result = await _execute_a2a_case(
                client,
                endpoint,
                test_case,
            )
            results.append(result)

        except Exception as error:
            results.append(
                _not_run(test_case, f"Execution error: {error}")
            )

    return _summarize(results)



MAX_MCP_TASK_POLLS = 10
DEFAULT_MCP_TASK_POLL_INTERVAL = 1.0


def _extract_mcp_result_payload(result):
    if not isinstance(result, dict):
        return None, "MCP task returned an invalid result."

    if result.get("isError") is True:
        return None, "MCP task completed with an execution error."

    structured = result.get("structuredContent")
    if isinstance(structured, (dict, list)):
        return structured, None

    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = _parse_structured_output(item.get("text"))
                if parsed is not None:
                    return parsed, None

    return None, "MCP returned no machine-readable structured output."


def _poll_mcp_task(client, task, tool_name):
    task_id = task.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        return None, "MCP task handle did not contain a valid task ID."

    for attempt in range(MAX_MCP_TASK_POLLS):
        status = task.get("status")

        if status == "completed":
            return _extract_mcp_result_payload(task.get("result"))

        if status in {"failed", "cancelled", "canceled", "rejected"}:
            return None, f"MCP task ended unsuccessfully. State: {status}"

        if status == "input_required":
            return None, "MCP task requires additional input."

        if status != "working":
            return None, f"MCP task returned an unsupported state: {status}"

        if attempt == MAX_MCP_TASK_POLLS - 1:
            break

        interval_ms = task.get("pollIntervalMs", 1000)
        if not isinstance(interval_ms, (int, float)) or isinstance(interval_ms, bool):
            interval_ms = 1000

        time.sleep(max(0.1, min(interval_ms / 1000, 5.0)))

        validation = client.get_task(task_id)
        if validation.get("status") != "PASS":
            return None, "MCP task polling response failed validation."

        evidence = validation.get("evidence") or {}
        task = evidence.get("task")

        if not isinstance(task, dict):
            return None, "MCP task polling response did not contain task data."

    return None, f"MCP task timed out after {MAX_MCP_TASK_POLLS} polling attempts."


def execute_mcp_test_cases(client, test_cases, tool_definitions=None):
    results = []
    tool_definitions = tool_definitions or {}

    for test_case in test_cases:
        if not test_case.tool_name:
            results.append(
                _not_run(test_case, "MCP test case must declare tool_name.")
            )
            continue

        if not isinstance(test_case.input, dict):
            results.append(
                _not_run(test_case, "MCP tool arguments must be a JSON object.")
            )
            continue

        try:
            validation = client.call_tool(
                test_case.tool_name,
                arguments=test_case.input,
                tool_definition=tool_definitions.get(test_case.tool_name),
            )

            if validation.get("status") != "PASS":
                results.append(
                    _not_run(test_case, "MCP tool-call validation did not pass.")
                )
                continue

            evidence = validation.get("evidence") or {}
            response = evidence.get("response")
            rpc_result = response.get("result", {}) if isinstance(response, dict) else {}

            if isinstance(rpc_result, dict) and rpc_result.get("resultType") == "task":
                task = evidence.get("task") or rpc_result.get("task") or rpc_result
                actual, error = _poll_mcp_task(
                    client,
                    task,
                    test_case.tool_name,
                )
            else:
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
