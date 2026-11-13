import httpx
import pytest

from evaluators.mcp import MCP_SPEC_VERSION
from evaluators.mcp_client import MCPClient, MCPClientError


ENDPOINT = "https://example.com/mcp"


def make_transport(response_data, status_code=200, captured=None):
    def handler(request):
        if captured is not None:
            captured["request"] = request
            captured["body"] = request.read()

        return httpx.Response(
            status_code,
            json=response_data,
        )

    return httpx.MockTransport(handler)


def rpc(result, request_id=1):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def discovery_response():
    return rpc({
        "resultType": "complete",
        "supportedVersions": [MCP_SPEC_VERSION],
        "capabilities": {"tools": {}},
    })


def tools_response():
    return rpc({
        "resultType": "complete",
        "tools": [
            {
                "name": "search",
                "description": "Search documents",
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


def tool_call_response():
    return rpc({
        "resultType": "complete",
        "content": [
            {"type": "text", "text": "Search completed."}
        ],
        "isError": False,
    })


def make_client(response_data, captured=None, status_code=200):
    return MCPClient(
        endpoint=ENDPOINT,
        transport=make_transport(
            response_data,
            status_code,
            captured,
        ),
        allow_private_network=True,
    )


def test_discover_server():
    client = make_client(discovery_response())

    result = client.discover()

    assert result["status"] == "PASS"


def test_list_tools():
    client = make_client(tools_response())

    result = client.list_tools()

    assert result["status"] == "PASS"
    assert result["evidence"]["tool_count"] == 1
    assert result["evidence"]["tool_names"] == ["search"]


def test_call_tool():
    client = make_client(tool_call_response())

    result = client.call_tool("search", {"query": "Lyrax"})

    assert result["status"] == "PASS"


def test_request_contains_protocol_headers():
    captured = {}
    client = make_client(
        discovery_response(),
        captured,
    )

    client.discover()

    request = captured["request"]

    assert request.headers["MCP-Protocol-Version"] == MCP_SPEC_VERSION
    assert request.headers["Mcp-Method"] == "server/discover"
    assert request.headers["Content-Type"] == "application/json"


def test_request_contains_client_metadata():
    captured = {}
    client = make_client(
        discovery_response(),
        captured,
    )

    client.discover()

    import json
    payload = json.loads(captured["body"])

    metadata = payload["params"]["_meta"]

    assert metadata[
        "io.modelcontextprotocol/protocolVersion"
    ] == MCP_SPEC_VERSION

    assert metadata[
        "io.modelcontextprotocol/clientInfo"
    ]["name"] == "Lyrax"


def test_tool_call_contains_tool_name_header():
    captured = {}
    client = make_client(
        tool_call_response(),
        captured,
    )

    client.call_tool("search", {"query": "test"})

    request = captured["request"]

    assert request.headers["Mcp-Method"] == "tools/call"
    assert request.headers["Mcp-Name"] == "search"


def test_http_error_raises_client_error():
    client = make_client(
        {},
        status_code=500,
    )

    with pytest.raises(MCPClientError):
        client.discover()


def test_invalid_json_raises_client_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"not valid json",
        )
    )

    client = MCPClient(
        ENDPOINT,
        transport=transport,
        allow_private_network=True,
    )

    with pytest.raises(MCPClientError):
        client.discover()


def test_invalid_endpoint_scheme_rejected():
    with pytest.raises(MCPClientError):
        MCPClient("ftp://example.com/mcp")


def test_endpoint_credentials_rejected():
    with pytest.raises(MCPClientError):
        MCPClient("https://user:password@example.com/mcp")


def test_empty_tool_name_rejected():
    client = make_client(tool_call_response())

    with pytest.raises(ValueError):
        client.call_tool("")


def test_non_dictionary_arguments_rejected():
    client = make_client(tool_call_response())

    with pytest.raises(ValueError):
        client.call_tool("search", ["invalid"])


def test_jsonrpc_error_is_not_reported_as_success():
    error_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32601,
            "message": "Method not found",
        },
    }

    client = make_client(error_response)

    result = client.discover()

    assert result["status"] == "FAIL"


def test_client_uses_sequential_request_ids():
    captured = {}

    client = make_client(
        discovery_response(),
        captured,
    )

    first_id, _ = client._request("server/discover")
    second_id, _ = client._request("server/discover")

    assert second_id == first_id + 1
