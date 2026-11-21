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

