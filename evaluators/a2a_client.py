import uuid

import httpx

from evaluators.a2a import (
    validate_agent_card,
    validate_send_message_response,
    validate_get_task_response,
)
from evaluators.endpoint_security import validate_endpoint
from evaluators.pinned_transport import _PinnedAsyncBackend


A2A_HEADERS = {
    "Content-Type": "application/json",
    "A2A-Version": "1.0",
}


def _validate_client_transport(client: httpx.AsyncClient) -> None:
    """
    Permit only DNS-pinned network transports or isolated MockTransport.

    Reject mounted transports because they can override the main transport
    for matching hosts.
    """
    if client.is_closed:
        raise ValueError("A2A client is closed.")

    if client._mounts:
        raise ValueError(
            "A2A clients with custom transport mounts are not permitted."
        )

    transport = client._transport

    if isinstance(transport, httpx.MockTransport):
        return

    if not isinstance(transport, httpx.AsyncHTTPTransport):
        raise ValueError(
            "A2A requires a DNS-pinned async transport."
        )

    backend = transport._pool._network_backend

    if not isinstance(backend, _PinnedAsyncBackend):
        raise ValueError(
            "A2A requires a DNS-pinned async transport."
        )


async def fetch_agent_card(
    client: httpx.AsyncClient,
    card_url: str,
    allow_private_network: bool = False,
) -> dict:
    evidence = {
        "operation": "fetch_agent_card",
        "url": card_url,
    }

    try:
        _validate_client_transport(client)

        validated = validate_endpoint(
            card_url,
            allow_private_network=allow_private_network,
        )

        response = await client.get(
            validated.url,
            follow_redirects=False,
        )
        evidence["http_status"] = response.status_code
        response.raise_for_status()

        card = response.json()

        if not isinstance(card, dict):
            raise ValueError("Agent Card response must be a JSON object.")

        validation = validate_agent_card(card)

        return {
            **evidence,
            "fetch_status": "PASS",
            "validation": validation,
            "status": validation["status"],
            "agent_card": card,
        }

    except (httpx.HTTPError, ValueError) as error:
        return {
            **evidence,
            "fetch_status": "FAIL",
            "status": "FAIL",
            "error": str(error),
        }


async def send_message(
    client: httpx.AsyncClient,
    endpoint: str,
    message_text: str,
    allow_private_network: bool = False,
) -> dict:
    request_id = str(uuid.uuid4())

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_USER",
                "parts": [{"text": message_text}],
            }
        },
    }

    try:
        _validate_client_transport(client)

        validated = validate_endpoint(
            endpoint,
            allow_private_network=allow_private_network,
        )

        response = await client.post(
            validated.url,
            json=payload,
            follow_redirects=False,
            headers=A2A_HEADERS,
        )

        response.raise_for_status()
        result = response.json()

        validation = validate_send_message_response(
            result,
            request_id,
        )

        return {
            "http_status": response.status_code,
            **validation,
        }

    except (httpx.HTTPError, ValueError) as error:
        return {
            "protocol": "A2A",
            "operation": "SendMessage",
            "status": "FAIL",
            "errors": [str(error)],
        }


async def get_task(
    client: httpx.AsyncClient,
    endpoint: str,
    task_id: str,
    history_length: int | None = None,
    allow_private_network: bool = False,
) -> dict:
    if not task_id:
        raise ValueError("Task ID cannot be empty.")

    if history_length is not None and (
        isinstance(history_length, bool)
        or not isinstance(history_length, int)
        or history_length < 0
    ):
        raise ValueError("History length must be a non-negative integer.")

    request_id = str(uuid.uuid4())

    params = {"id": task_id}

    if history_length is not None:
        params["historyLength"] = history_length

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "GetTask",
        "params": params,
    }

    try:
        _validate_client_transport(client)

        validated = validate_endpoint(
            endpoint,
            allow_private_network=allow_private_network,
        )

        response = await client.post(
            validated.url,
            json=payload,
            follow_redirects=False,
            headers=A2A_HEADERS,
        )

        response.raise_for_status()
        result = response.json()

        validation = validate_get_task_response(
            result,
            request_id,
            task_id,
        )

        return {
            "http_status": response.status_code,
            **validation,
        }

    except (httpx.HTTPError, ValueError) as error:
        return {
            "protocol": "A2A",
            "operation": "GetTask",
            "status": "FAIL",
            "task_id": task_id,
            "errors": [str(error)],
        }
