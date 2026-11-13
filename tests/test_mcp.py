import copy

from evaluators.mcp import (
    MCP_SPEC_VERSION,
    validate_discover_response,
    validate_tools_list_response,
    validate_tool_call_response,
)


def rpc(result, request_id="test-1"):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def valid_discovery():
    return rpc({
        "resultType": "complete",
        "supportedVersions": [MCP_SPEC_VERSION],
        "capabilities": {"tools": {}},
    })


def valid_tools():
    return rpc({
        "resultType": "complete",
        "tools": [
            {
                "name": "search",
                "description": "Search for information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"],
                },
            }
        ],
    })


def valid_tool_call():
    return rpc({
        "resultType": "complete",
        "content": [
            {"type": "text", "text": "Search completed."}
        ],
        "isError": False,
    })


def test_valid_discovery_response():
    result = validate_discover_response(valid_discovery(), "test-1")
    assert result["status"] == "PASS"


def test_discovery_rejects_wrong_request_id():
    result = validate_discover_response(valid_discovery(), "wrong-id")
    assert result["status"] == "FAIL"


def test_discovery_rejects_missing_versions():
    response = valid_discovery()
    response["result"].pop("supportedVersions")

    result = validate_discover_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_discovery_reports_unsupported_version():
    response = valid_discovery()
    response["result"]["supportedVersions"] = ["1.0"]

    result = validate_discover_response(response, "test-1")
    assert result["status"] == "UNSUPPORTED"


def test_discovery_rejects_missing_capabilities():
    response = valid_discovery()
    response["result"].pop("capabilities")

    result = validate_discover_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_valid_tools_list():
    result = validate_tools_list_response(valid_tools(), "test-1")
    assert result["status"] == "PASS"
    assert result["evidence"]["tool_count"] == 1


def test_tools_list_rejects_duplicate_names():
    response = valid_tools()
    response["result"]["tools"].append(
        copy.deepcopy(response["result"]["tools"][0])
    )

    result = validate_tools_list_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_tools_list_rejects_invalid_input_schema():
    response = valid_tools()
    response["result"]["tools"][0]["inputSchema"] = {
        "type": "not-a-valid-json-schema-type"
    }

    result = validate_tools_list_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_tools_list_rejects_missing_tool_name():
    response = valid_tools()
    response["result"]["tools"][0].pop("name")

    result = validate_tools_list_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_valid_tool_call_response():
    result = validate_tool_call_response(
        valid_tool_call(),
        "test-1",
    )
    assert result["status"] == "PASS"


def test_tool_call_rejects_invalid_content():
    response = valid_tool_call()
    response["result"]["content"] = [
        {"type": "unknown", "value": "invalid"}
    ]

    result = validate_tool_call_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_tool_call_rejects_non_boolean_error_flag():
    response = valid_tool_call()
    response["result"]["isError"] = "false"

    result = validate_tool_call_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_tool_call_accepts_input_required():
    response = rpc({
        "resultType": "input_required",
        "inputRequests": {
            "request-1": {
                "method": "elicitation/create",
                "params": {"message": "Additional input required."},
            }
        },
    })

    result = validate_tool_call_response(response, "test-1")
    assert result["status"] == "PASS"


def test_tool_call_rejects_malformed_input_request():
    response = rpc({
        "resultType": "input_required",
        "inputRequests": {
            "request-1": {"method": "elicitation/create"}
        },
    })

    result = validate_tool_call_response(response, "test-1")
    assert result["status"] == "FAIL"


def test_jsonrpc_error_response_is_not_accepted_as_success():
    response = {
        "jsonrpc": "2.0",
        "id": "test-1",
        "error": {
            "code": -32601,
            "message": "Method not found",
        },
    }

    result = validate_tools_list_response(response, "test-1")
    assert result["status"] == "FAIL"
