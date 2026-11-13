from urllib.parse import urlsplit

from pydantic import ValidationError

from schemas.a2a import A2AAgentCard


A2A_SPEC_RELEASE = "1.0.0"
A2A_PROTOCOL_VERSION = "1.0"

STANDARD_BINDINGS = {
    "JSONRPC",
    "GRPC",
    "HTTP+JSON",
}

IMPLEMENTED_BINDINGS = {
    "JSONRPC",
}

A2A_TASK_STATES = {
    "TASK_STATE_UNSPECIFIED",
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_REJECTED",
    "TASK_STATE_AUTH_REQUIRED",
}

A2A_TERMINAL_STATES = {
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
}


def is_valid_custom_binding(binding: str) -> bool:
    try:
        parsed = urlsplit(binding)
        return bool(parsed.scheme and (parsed.netloc or parsed.path))
    except ValueError:
        return False


def is_valid_interface_address(interface) -> bool:
    binding = interface.protocolBinding
    address = interface.url

    try:
        if binding in {"JSONRPC", "HTTP+JSON"}:
            parsed = urlsplit(address)
            return (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
            )

        if binding == "GRPC":
            parsed = urlsplit("//" + address)
            return bool(parsed.hostname and parsed.port)

        return bool(address.strip())

    except ValueError:
        return False


def validate_agent_card(card: dict) -> dict:
    if not isinstance(card, dict):
        raise TypeError("Agent Card must be a dictionary.")

    try:
        validated = A2AAgentCard.model_validate(card)

    except ValidationError as error:
        return {
            "protocol": "A2A",
            "spec_release": A2A_SPEC_RELEASE,
            "status": "FAIL",
            "checks": [
                {
                    "name": "agent_card_schema",
                    "status": "FAIL",
                }
            ],
            "errors": error.errors(
                include_input=False,
                include_url=False,
            ),
        }

    interfaces = validated.supportedInterfaces

    addresses_valid = all(
        is_valid_interface_address(interface)
        for interface in interfaces
    )

    bindings_valid = all(
        binding in STANDARD_BINDINGS
        or is_valid_custom_binding(binding)
        for binding in (
            interface.protocolBinding for interface in interfaces
        )
    )

    versions_declared = all(
        bool(interface.protocolVersion.strip())
        for interface in interfaces
    )

    usable_interfaces = [
        {
            "url": interface.url,
            "protocol_binding": interface.protocolBinding,
            "protocol_version": interface.protocolVersion,
        }
        for interface in interfaces
        if (
            interface.protocolBinding in IMPLEMENTED_BINDINGS
            and interface.protocolVersion == A2A_PROTOCOL_VERSION
            and is_valid_interface_address(interface)
        )
    ]

    checks = [
        {
            "name": "agent_card_schema",
            "status": "PASS",
        },
        {
            "name": "supported_interfaces",
            "status": "PASS" if interfaces else "FAIL",
        },
        {
            "name": "protocol_binding_declarations",
            "status": "PASS" if bindings_valid else "FAIL",
        },
        {
            "name": "interface_addresses",
            "status": "PASS" if addresses_valid else "FAIL",
        },
        {
            "name": "protocol_version_declarations",
            "status": "PASS" if versions_declared else "FAIL",
        },
        {
            "name": "lyrax_protocol_support",
            "status": "PASS" if usable_interfaces else "UNSUPPORTED",
        },
    ]

    structural_failure = any(
        check["status"] == "FAIL"
        for check in checks
    )

    if structural_failure:
        overall_status = "FAIL"
    elif usable_interfaces:
        overall_status = "PASS"
    else:
        overall_status = "UNSUPPORTED"

    return {
        "protocol": "A2A",
        "spec_release": A2A_SPEC_RELEASE,
        "status": overall_status,
        "agent_name": validated.name,
        "checks": checks,
        "implemented_bindings": sorted(IMPLEMENTED_BINDINGS),
        "usable_interfaces": usable_interfaces,
        "errors": [],
    }


def validate_send_message_response(
    response: dict,
    request_id,
) -> dict:

    errors = []

    if not isinstance(response, dict):
        raise TypeError("A2A response must be a dictionary.")

    if response.get("jsonrpc") != "2.0":
        errors.append("Invalid JSON-RPC version.")

    if response.get("id") != request_id:
        errors.append("Response ID does not match request ID.")

    if "error" in response:
        errors.append("Agent returned a JSON-RPC error.")

    result = response.get("result")

    if not isinstance(result, dict):
        errors.append("Response result must be an object.")

    else:
        has_task = "task" in result
        has_message = "message" in result

        if has_task == has_message:
            errors.append(
                "Response must contain exactly one of task or message."
            )

        elif has_task:
            task = result["task"]

            if not isinstance(task, dict):
                errors.append("Task must be an object.")
            else:
                if (
                    not isinstance(task.get("id"), str)
                    or not task["id"].strip()
                ):
                    errors.append("Task is missing a valid ID.")

                status = task.get("status")

                if not isinstance(status, dict):
                    errors.append("Task is missing its status object.")
                elif status.get("state") not in A2A_TASK_STATES:
                    errors.append("Task has an unsupported status state.")

        elif has_message:
            message = result["message"]

            if not isinstance(message, dict):
                errors.append("Message must be an object.")
            else:
                if (
                    not isinstance(message.get("messageId"), str)
                    or not message["messageId"].strip()
                ):
                    errors.append(
                        "Agent message is missing a valid messageId."
                    )

                if message.get("role") != "ROLE_AGENT":
                    errors.append("Agent message has an invalid role.")

                parts = message.get("parts")

                if not isinstance(parts, list) or not parts:
                    errors.append(
                        "Agent message has invalid or missing parts."
                    )
                else:
                    for index, part in enumerate(parts):
                        if not isinstance(part, dict):
                            errors.append(
                                f"Message part {index} must be an object."
                            )
                            continue

                        content_fields = [
                            field
                            for field in ("text", "raw", "url", "data")
                            if field in part
                        ]

                        if len(content_fields) != 1:
                            errors.append(
                                f"Message part {index} must contain exactly "
                                "one of text, raw, url, or data."
                            )
                        elif content_fields[0] in ("text", "raw", "url"):
                            if not isinstance(part[content_fields[0]], str):
                                errors.append(
                                    f"Message part {index} has an invalid "
                                    f"{content_fields[0]} value."
                                )

    valid = not errors

    return {
        "protocol": "A2A",
        "operation": "SendMessage",
        "status": "PASS" if valid else "FAIL",
        "checks": [
            {
                "name": "jsonrpc_response",
                "status": "PASS" if valid else "FAIL",
            },
            {
                "name": "send_message_payload",
                "status": "PASS" if valid else "FAIL",
            },
        ],
        "errors": errors,
        "response": response,
    }


def validate_get_task_response(
    response: dict,
    request_id,
    expected_task_id: str,
) -> dict:

    errors = []

    if not isinstance(response, dict):
        raise TypeError("A2A response must be a dictionary.")

    if response.get("jsonrpc") != "2.0":
        errors.append("Invalid JSON-RPC version.")

    if response.get("id") != request_id:
        errors.append("Response ID does not match request ID.")

    if "error" in response:
        errors.append("Agent returned a JSON-RPC error.")

    task = response.get("result")

    if not isinstance(task, dict):
        errors.append("Task result must be an object.")

    else:
        if task.get("id") != expected_task_id:
            errors.append("Returned task ID does not match requested ID.")

        status = task.get("status")

        if not isinstance(status, dict):
            errors.append("Task status is missing.")
        else:
            state = status.get("state")

            if state not in A2A_TASK_STATES:
                errors.append("Task has an unsupported status state.")

    state = None

    if isinstance(task, dict):
        status = task.get("status")

        if isinstance(status, dict):
            state = status.get("state")

    valid = not errors

    return {
        "protocol": "A2A",
        "operation": "GetTask",
        "status": "PASS" if valid else "FAIL",
        "task_id": expected_task_id,
        "task_state": state if valid else None,
        "is_terminal": (
            state in A2A_TERMINAL_STATES if valid else None
        ),
        "checks": [
            {
                "name": "task_response",
                "status": "PASS" if valid else "FAIL",
            }
        ],
        "errors": errors,
        "task": task if valid else None,
    }
