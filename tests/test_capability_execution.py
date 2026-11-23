import pytest

from schemas.test_case import TestCase as EvaluationTestCase
from evaluators import capability_execution as execution


def make_case():
    return EvaluationTestCase(
        id="a2a-001",
        name="Extract answer",
        capability="structured_data_extraction",
        input={"question": "What is the answer?"},
        expected_output={"answer": 42},
    )


@pytest.mark.asyncio
async def test_a2a_polls_until_task_completes(monkeypatch):
    async def fake_send_message(*args, **kwargs):
        return {
            "status": "PASS",
            "response": {
                "result": {
                    "task": {
                        "id": "task-1",
                        "status": {"state": "TASK_STATE_SUBMITTED"},
                    }
                }
            },
        }

    async def fake_get_task(*args, **kwargs):
        return {
            "status": "PASS",
            "task_state": "TASK_STATE_COMPLETED",
            "task": {
                "id": "task-1",
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [
                    {"parts": [{"data": {"answer": 42}}]}
                ],
            },
        }

    async def fake_sleep(*args):
        pass

    monkeypatch.setattr(execution, "send_message", fake_send_message)
    monkeypatch.setattr(execution, "get_task", fake_get_task)
    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    result = await execution.execute_a2a_test_cases(
        None, "https://example.com", [make_case()]
    )

    assert result["status"] == "PASS"
    assert result["passed"] == 1
    assert result["test_cases"][0]["accuracy"] == 100


@pytest.mark.asyncio
async def test_a2a_polling_timeout_returns_not_run(monkeypatch):
    async def fake_send_message(*args, **kwargs):
        return {
            "status": "PASS",
            "response": {
                "result": {
                    "task": {
                        "id": "task-1",
                        "status": {"state": "TASK_STATE_WORKING"},
                    }
                }
            },
        }

    async def fake_get_task(*args, **kwargs):
        return {
            "status": "PASS",
            "task_state": "TASK_STATE_WORKING",
            "task": {
                "id": "task-1",
                "status": {"state": "TASK_STATE_WORKING"},
            },
        }

    async def fake_sleep(*args):
        pass

    monkeypatch.setattr(execution, "send_message", fake_send_message)
    monkeypatch.setattr(execution, "get_task", fake_get_task)
    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    result = await execution.execute_a2a_test_cases(
        None, "https://example.com", [make_case()]
    )

    assert result["status"] == "NOT_RUN"
    assert result["not_run"] == 1
    assert "timed out" in result["test_cases"][0]["reason"]


@pytest.mark.asyncio
async def test_a2a_input_required_returns_not_run(monkeypatch):
    async def fake_send_message(*args, **kwargs):
        return {
            "status": "PASS",
            "response": {
                "result": {
                    "task": {
                        "id": "task-1",
                        "status": {"state": "TASK_STATE_INPUT_REQUIRED"},
                    }
                }
            },
        }

    monkeypatch.setattr(execution, "send_message", fake_send_message)

    result = await execution.execute_a2a_test_cases(
        None, "https://example.com", [make_case()]
    )

    assert result["status"] == "NOT_RUN"
    assert "additional interaction" in result["test_cases"][0]["reason"]


def make_mcp_case():
    return EvaluationTestCase(
        id="mcp-001",
        name="Extract answer",
        capability="structured_data_extraction",
        input={"question": "What is the answer?"},
        expected_output={"answer": 42},
        tool_name="answer",
    )


class FakeMCPClient:
    def __init__(self, initial_task, polled_tasks):
        self.initial_task = initial_task
        self.polled_tasks = list(polled_tasks)
        self.poll_count = 0

    def call_tool(self, *args, **kwargs):
        task = self.initial_task
        return {
            "status": "PASS",
            "evidence": {
                "response": {
                    "result": {
                        "resultType": "task",
                        "task": task,
                    }
                },
                "task": task,
            },
        }

    def get_task(self, task_id):
        self.poll_count += 1
        task = (
            self.polled_tasks.pop(0)
            if self.polled_tasks
            else {
                "taskId": task_id,
                "status": "working",
                "pollIntervalMs": 100,
            }
        )
        return {
            "status": "PASS",
            "evidence": {"task": task},
        }


def test_mcp_task_completes_successfully(monkeypatch):
    monkeypatch.setattr(execution.time, "sleep", lambda *_: None)

    client = FakeMCPClient(
        {
            "taskId": "task-1",
            "status": "working",
            "pollIntervalMs": 100,
        },
        [
            {
                "taskId": "task-1",
                "status": "completed",
                "result": {
                    "structuredContent": {"answer": 42},
                },
            }
        ],
    )

    result = execution.execute_mcp_test_cases(
        client, [make_mcp_case()]
    )

    assert result["status"] == "PASS"
    assert result["passed"] == 1
    assert result["test_cases"][0]["accuracy"] == 100
    assert client.poll_count == 1


def test_mcp_task_failure_returns_not_run(monkeypatch):
    monkeypatch.setattr(execution.time, "sleep", lambda *_: None)

    client = FakeMCPClient(
        {
            "taskId": "task-2",
            "status": "working",
        },
        [
            {
                "taskId": "task-2",
                "status": "failed",
            }
        ],
    )

    result = execution.execute_mcp_test_cases(
        client, [make_mcp_case()]
    )

    assert result["status"] == "NOT_RUN"
    assert "unsuccessfully" in result["test_cases"][0]["reason"]


def test_mcp_task_timeout_returns_not_run(monkeypatch):
    monkeypatch.setattr(execution.time, "sleep", lambda *_: None)

    client = FakeMCPClient(
        {
            "taskId": "task-3",
            "status": "working",
            "pollIntervalMs": 100,
        },
        [],
    )

    result = execution.execute_mcp_test_cases(
        client, [make_mcp_case()]
    )

    assert result["status"] == "NOT_RUN"
    assert "timed out" in result["test_cases"][0]["reason"]
    assert client.poll_count == execution.MAX_MCP_TASK_POLLS - 1


def test_mcp_task_input_required_returns_not_run(monkeypatch):
    monkeypatch.setattr(execution.time, "sleep", lambda *_: None)

    client = FakeMCPClient(
        {
            "taskId": "task-4",
            "status": "working",
        },
        [
            {
                "taskId": "task-4",
                "status": "input_required",
            }
        ],
    )

    result = execution.execute_mcp_test_cases(
        client, [make_mcp_case()]
    )

    assert result["status"] == "NOT_RUN"
    assert "additional input" in result["test_cases"][0]["reason"]
