import re
from typing import Any

from jsonschema import validators


MCP_SPEC_VERSION = "2026-07-28"

TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")

CONTENT_TYPES = {
    "text",
    "image",
    "audio",
    "resource_link",
    "resource",
}


def _check(name: str, status: str, details: str) -> dict:
    return {
        "name": name,
        "status": status,
        "details": details,
    }


def _result(checks: list[dict], evidence: dict | None = None) -> dict:
    statuses = {item["status"] for item in checks}

    if "FAIL" in statuses:
        overall = "FAIL"
    elif "UNSUPPORTED" in statuses:
        overall = "UNSUPPORTED"
    else:
        overall = "PASS"

    return {
        "protocol": "MCP",
        "spec_version": MCP_SPEC_VERSION,
        "status": overall,
        "checks": checks,
        "evidence": evidence or {},
    }


def _validate_rpc_response(
    response: Any,
    request_id: str | int,
) -> tuple[list[dict], dict | None]:
    checks = []

    if not isinstance(response, dict):
        return [
            _check(
                "jsonrpc_response",
                "FAIL",
                "Response must be a JSON object."
            )
        ], None

    if response.get("jsonrpc") != "2.0":
        checks.append(
            _check(
                "jsonrpc_version",
                "FAIL",
                "Response must declare JSON-RPC version 2.0."
            )
        )
    else:
        checks.append(
            _check(
                "jsonrpc_version",
                "PASS",
                "JSON-RPC version is 2.0."
            )
        )

    response_id = response.get("id")

    if isinstance(response_id, bool) or not isinstance(
        response_id, (str, int)
    ):
        checks.append(
            _check(
                "response_id",
                "FAIL",
                "Response ID must be a string or integer."
            )
        )
    elif response_id != request_id:
        checks.append(
            _check(
                "response_id",
                "FAIL",
                "Response ID does not match the request ID."
            )
        )
    else:
        checks.append(
            _check(
                "response_id",
                "PASS",
                "Response ID matches the request."
            )
        )

    has_result = "result" in response
    has_error = "error" in response

    if has_result == has_error:
        checks.append(
            _check(
                "response_envelope",
                "FAIL",
                "Response must contain exactly one of result or error."
            )
        )
        return checks, None

    if has_error:
        error = response["error"]

        if (
            not isinstance(error, dict)
            or isinstance(error.get("code"), bool)
            or not isinstance(error.get("code"), int)
            or not isinstance(error.get("message"), str)
        ):
            checks.append(
                _check(
                    "jsonrpc_error",
                    "FAIL",
                    "JSON-RPC error must contain an integer code and string message."
                )
            )
        else:
            checks.append(
                _check(
                    "jsonrpc_error",
                    "PASS",
                    "Server returned a structurally valid JSON-RPC error."
                )
            )
            checks.append(
                _check(
                    "rpc_operation",
                    "FAIL",
                    "The requested MCP operation failed with a JSON-RPC error."
                )
            )

        return checks, None

    result = response["result"]

    if not isinstance(result, dict):
        checks.append(
            _check(
                "response_result",
                "FAIL",
                "Result must be a JSON object."
            )
        )
        return checks, None

    checks.append(
        _check(
            "response_envelope",
            "PASS",
            "Response contains a result object."
        )
    )

    return checks, result


def _validate_json_schema(schema: Any) -> tuple[bool, str]:
    if not isinstance(schema, dict):
        return False, "JSON Schema must be an object."

    try:
        validator_class = validators.validator_for(schema)
        validator_class.check_schema(schema)
    except Exception as exc:
        return False, f"Invalid JSON Schema: {exc}"

    return True, "JSON Schema is structurally valid."


def validate_discover_response(
    response: Any,
    request_id: str | int,
) -> dict:
    checks, result = _validate_rpc_response(response, request_id)

    if result is None:
        return _result(checks, {"response": response})

    if result.get("resultType") != "complete":
        checks.append(
            _check(
                "discover_result_type",
                "FAIL",
                "server/discover must return a complete result."
            )
        )
    else:
        checks.append(
            _check(
                "discover_result_type",
                "PASS",
                "Discovery result is complete."
            )
        )

    versions = result.get("supportedVersions")

    if (
        not isinstance(versions, list)
        or not versions
        or not all(isinstance(version, str) and version for version in versions)
    ):
        checks.append(
            _check(
                "supported_protocol_versions",
                "FAIL",
                "supportedVersions must be a non-empty list of version strings."
            )
        )
    elif MCP_SPEC_VERSION not in versions:
        checks.append(
            _check(
                "supported_protocol_versions",
                "UNSUPPORTED",
                f"Server does not advertise {MCP_SPEC_VERSION}."
            )
        )
    else:
        checks.append(
            _check(
                "supported_protocol_versions",
                "PASS",
                f"Server advertises {MCP_SPEC_VERSION}."
            )
        )

    capabilities = result.get("capabilities")

    if not isinstance(capabilities, dict):
        checks.append(
            _check(
                "server_capabilities",
                "FAIL",
                "Discovery response must include a capabilities object."
            )
        )
    else:
        checks.append(
            _check(
                "server_capabilities",
                "PASS",
                "Server capabilities are represented as an object."
            )
        )

    metadata = result.get("_meta", {})
    if metadata is not None and not isinstance(metadata, dict):
        checks.append(
            _check(
                "server_metadata",
                "FAIL",
                "Response _meta must be an object when present."
            )
        )
    elif isinstance(metadata, dict):
        server_info = metadata.get(
            "io.modelcontextprotocol/serverInfo"
        )

        if server_info is not None and (
            not isinstance(server_info, dict)
            or not isinstance(server_info.get("name"), str)
            or not isinstance(server_info.get("version"), str)
        ):
            checks.append(
                _check(
                    "server_metadata",
                    "FAIL",
                    "serverInfo must contain string name and version fields."
                )
            )
        else:
            checks.append(
                _check(
                    "server_metadata",
                    "PASS",
                    "Optional server metadata is valid."
                )
            )

    return _result(checks, {"response": response})


def validate_tools_list_response(
    response: Any,
    request_id: str | int,
) -> dict:
    checks, result = _validate_rpc_response(response, request_id)

    if result is None:
        return _result(checks, {"response": response})

    if result.get("resultType") != "complete":
        checks.append(
            _check(
                "tools_list_result_type",
                "FAIL",
                "tools/list must return a complete result."
            )
        )
        return _result(checks, {"response": response})

    checks.append(
        _check(
            "tools_list_result_type",
            "PASS",
            "Tool listing result is complete."
        )
    )

    tools = result.get("tools")

    if not isinstance(tools, list):
        checks.append(
            _check(
                "tools_collection",
                "FAIL",
                "tools must be a list."
            )
        )
        return _result(checks, {"response": response})

    checks.append(
        _check(
            "tools_collection",
            "PASS",
            f"Server returned {len(tools)} tool definitions."
        )
    )

    names = []
    invalid_tools = []

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            invalid_tools.append({
                "index": index,
                "reason": "Tool definition must be an object."
            })
            continue

        name = tool.get("name")

        if not isinstance(name, str) or not TOOL_NAME_PATTERN.fullmatch(name):
            invalid_tools.append({
                "index": index,
                "reason": "Tool name is missing or violates the MCP name format."
            })
            continue

        names.append(name)

        valid_schema, schema_message = _validate_json_schema(
            tool.get("inputSchema")
        )

        if not valid_schema:
            invalid_tools.append({
                "index": index,
                "name": name,
                "reason": schema_message,
            })

        output_schema = tool.get("outputSchema")
        if output_schema is not None:
            valid_output, output_message = _validate_json_schema(
                output_schema
            )
            if not valid_output:
                invalid_tools.append({
                    "index": index,
                    "name": name,
                    "reason": f"Invalid outputSchema: {output_message}",
                })

    duplicates = sorted({
        name for name in names if names.count(name) > 1
    })

    if duplicates:
        invalid_tools.append({
            "reason": "Duplicate tool names.",
            "names": duplicates,
        })

    if invalid_tools:
        checks.append(
            _check(
                "tool_definitions",
                "FAIL",
                f"{len(invalid_tools)} tool-definition issue(s) found."
            )
        )
    else:
        checks.append(
            _check(
                "tool_definitions",
                "PASS",
                "All tool names are valid and unique; input and output schemas are valid."
            )
        )

    return _result(
        checks,
        {
            "tool_count": len(tools),
            "tool_names": names,
            "invalid_tools": invalid_tools,
            "response": response,
        },
    )


def _validate_content_item(item: Any) -> tuple[bool, str]:
    if not isinstance(item, dict):
        return False, "Content item must be an object."

    content_type = item.get("type")

    if content_type not in CONTENT_TYPES:
        return False, f"Unsupported content type: {content_type!r}."

    if content_type == "text":
        if not isinstance(item.get("text"), str):
            return False, "Text content requires a string text field."

    elif content_type in {"image", "audio"}:
        if not isinstance(item.get("data"), str):
            return False, f"{content_type} content requires string data."
        if not isinstance(item.get("mimeType"), str):
            return False, f"{content_type} content requires mimeType."

    elif content_type == "resource_link":
        if not isinstance(item.get("uri"), str):
            return False, "Resource link requires a URI."
        if not isinstance(item.get("name"), str):
            return False, "Resource link requires a name."

    elif content_type == "resource":
        if not isinstance(item.get("resource"), dict):
            return False, "Embedded resource requires a resource object."

    return True, "Content item is structurally valid."


def validate_tool_call_response(
    response: Any,
    request_id: str | int,
    tool_definition: dict | None = None,
) -> dict:
    checks, result = _validate_rpc_response(response, request_id)

    if result is None:
        return _result(checks, {"response": response})

    result_type = result.get("resultType")

    if result_type == "input_required":
        input_requests = result.get("inputRequests")

        if not isinstance(input_requests, dict) or not input_requests:
            checks.append(
                _check(
                    "input_required_result",
                    "FAIL",
                    "input_required results must include a non-empty inputRequests object."
                )
            )
        else:
            valid_requests = all(
                isinstance(request, dict)
                and isinstance(request.get("method"), str)
                and isinstance(request.get("params"), dict)
                for request in input_requests.values()
            )

            checks.append(
                _check(
                    "input_required_result",
                    "PASS" if valid_requests else "FAIL",
                    "Input requests have valid method and params fields."
                    if valid_requests
                    else "One or more input requests are malformed."
                )
            )

        request_state = result.get("requestState")
        if request_state is not None and not isinstance(request_state, str):
            checks.append(
                _check(
                    "request_state",
                    "FAIL",
                    "requestState must be a string when present."
                )
            )

        return _result(checks, {"response": response})

    if result_type != "complete":
        checks.append(
            _check(
                "tool_call_result_type",
                "FAIL",
                "Tool call resultType must be complete or input_required."
            )
        )
        return _result(checks, {"response": response})

    checks.append(
        _check(
            "tool_call_result_type",
            "PASS",
            "Tool call returned a complete result."
        )
    )

    content = result.get("content")

    if not isinstance(content, list):
        checks.append(
            _check(
                "tool_result_content",
                "FAIL",
                "Tool result content must be a list."
            )
        )
    else:
        invalid_content = []

        for index, item in enumerate(content):
            valid, message = _validate_content_item(item)
            if not valid:
                invalid_content.append({
                    "index": index,
                    "reason": message,
                })

        checks.append(
            _check(
                "tool_result_content",
                "FAIL" if invalid_content else "PASS",
                f"{len(invalid_content)} invalid content item(s)."
                if invalid_content
                else f"All {len(content)} content item(s) are valid."
            )
        )

    is_error = result.get("isError")
    if is_error is not None and not isinstance(is_error, bool):
        checks.append(
            _check(
                "tool_execution_status",
                "FAIL",
                "isError must be a boolean when present."
            )
        )
    else:
        checks.append(
            _check(
                "tool_execution_status",
                "PASS",
                f"Tool execution error flag: {bool(is_error)}."
            )
        )

    if tool_definition and "structuredContent" in result:
        output_schema = tool_definition.get("outputSchema")

        if output_schema is not None:
            valid_schema, schema_message = _validate_json_schema(
                output_schema
            )

            if not valid_schema:
                checks.append(
                    _check(
                        "structured_output_schema",
                        "FAIL",
                        schema_message
                    )
                )
            else:
                try:
                    validator_class = validators.validator_for(output_schema)
                    validator_class(output_schema).validate(
                        result["structuredContent"]
                    )
                    checks.append(
                        _check(
                            "structured_output_schema",
                            "PASS",
                            "structuredContent conforms to the advertised outputSchema."
                        )
                    )
                except Exception as exc:
                    checks.append(
                        _check(
                            "structured_output_schema",
                            "FAIL",
                            f"structuredContent violates outputSchema: {exc}"
                        )
                    )

    return _result(checks, {"response": response})
