import json

import httpx
import pytest

from evaluators.a2a_client import (
    fetch_agent_card,
    send_message,
    get_task,
)

from evaluators.a2a import validate_send_message_response


def valid_card():
    return {
        "name": "Test Agent",
        "description": "An agent for testing",
        "supportedInterfaces": [
            {
                "url": "https://example.com/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "test",
                "name": "Test",
                "description": "Testing",
                "tags": ["test"],
            }
        ],
    }


def valid_agent_message():
    return {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "message": {
                "messageId": "message-1",
                "role": "ROLE_AGENT",
                "parts": [
                    {
                        "text": "Task completed successfully."
                    }
                ],
            }
        },
    }


@pytest.mark.asyncio
async def test_fetch_valid_agent_card():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=valid_card())
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_agent_card(
            client,
            "https://example.com/.well-known/agent-card.json",
        )

    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_fetch_invalid_agent_card():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"name": "Incomplete"})
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_agent_card(
            client,
            "https://example.com/.well-known/agent-card.json",
        )

    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_fetch_agent_card_http_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500)
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_agent_card(
            client,
            "https://example.com/.well-known/agent-card.json",
        )

    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_fetch_agent_card_invalid_json():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_agent_card(
            client,
            "https://example.com/.well-known/agent-card.json",
        )

    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_send_message_valid_task():
    response_data = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "task": {
                "id": "task-1",
                "status": {
                    "state": "TASK_STATE_COMPLETED"
                },
            }
        },
    }

    def handler(request):
        response_data["id"] = json.loads(request.content)["id"]
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await send_message(
            client,
            "https://example.com/a2a",
            "Hello",
        )

    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_send_message_invalid_response():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"invalid": True})
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await send_message(
            client,
            "https://example.com/a2a",
            "Hello",
        )

    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_get_task_completed():
    response_data = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "id": "task-1",
            "status": {
                "state": "TASK_STATE_COMPLETED"
            },
        },
    }

    def handler(request):
        response_data["id"] = json.loads(request.content)["id"]
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_task(
            client,
            "https://example.com/a2a",
            "task-1",
        )

    assert result["status"] == "PASS"
    assert result["is_terminal"] is True


@pytest.mark.asyncio
async def test_get_task_mismatched_id():
    response_data = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "id": "different-task",
            "status": {
                "state": "TASK_STATE_COMPLETED"
            },
        },
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response_data)
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_task(
            client,
            "https://example.com/a2a",
            "task-1",
        )

    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_get_task_unknown_state():
    response_data = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "id": "task-1",
            "status": {
                "state": "UNKNOWN_STATE"
            },
        },
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response_data)
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_task(
            client,
            "https://example.com/a2a",
            "task-1",
        )

    assert result["status"] == "FAIL"


def test_valid_agent_message():
    result = validate_send_message_response(
        valid_agent_message(),
        "request-1",
    )

    assert result["status"] == "PASS"


def test_agent_message_without_message_id():
    response = valid_agent_message()
    del response["result"]["message"]["messageId"]

    result = validate_send_message_response(response, "request-1")

    assert result["status"] == "FAIL"


def test_agent_message_without_context_id():
    result = validate_send_message_response(
        valid_agent_message(),
        "request-1",
    )

    assert result["status"] == "PASS"


def test_agent_message_with_invalid_role():
    response = valid_agent_message()
    response["result"]["message"]["role"] = "ROLE_USER"

    result = validate_send_message_response(response, "request-1")

    assert result["status"] == "FAIL"


def test_agent_message_with_empty_parts():
    response = valid_agent_message()
    response["result"]["message"]["parts"] = []

    result = validate_send_message_response(response, "request-1")

    assert result["status"] == "FAIL"


def test_agent_message_part_with_multiple_content_fields():
    response = valid_agent_message()
    response["result"]["message"]["parts"] = [
        {
            "text": "Hello",
            "data": {"value": "Hello"},
        }
    ]

    result = validate_send_message_response(response, "request-1")

    assert result["status"] == "FAIL"
