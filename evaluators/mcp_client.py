import itertools
import json

import httpx

from evaluators.mcp import (
    MCP_SPEC_VERSION,
    validate_discover_response,
    validate_tools_list_response,
    validate_tool_call_response,
)
from evaluators.endpoint_security import (
    EndpointSecurityError,
    validate_endpoint,
)
from evaluators.pinned_transport import create_pinned_sync_transport


class MCPClientError(Exception):
    pass


class MCPClient:

    def __init__(
        self,
        endpoint: str,
        client_name: str = "Lyrax",
        client_version: str = "0.1.0",
        timeout: float = 15.0,
        max_response_bytes: int = 2_000_000,
        allow_private_network: bool = False,
        transport=None,
    ):
        self.endpoint = endpoint
        self.client_name = client_name
        self.client_version = client_version
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.allow_private_network = allow_private_network
        self.transport = transport
        self._request_ids = itertools.count(1)

        try:
            self.validated_endpoint = validate_endpoint(
                endpoint,
                allow_private_network=allow_private_network,
            )
        except EndpointSecurityError as exc:
            raise MCPClientError(str(exc)) from exc

    def _metadata(self):
        return {
            "io.modelcontextprotocol/protocolVersion": MCP_SPEC_VERSION,
            "io.modelcontextprotocol/clientInfo": {
                "name": self.client_name,
                "version": self.client_version,
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }

    def _request(self, method, params=None, tool_name=None):
        request_id = next(self._request_ids)

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": {
                **(params or {}),
                "_meta": self._metadata(),
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": MCP_SPEC_VERSION,
            "Mcp-Method": method,
        }

        if tool_name is not None:
            headers["Mcp-Name"] = tool_name

        # A fresh pinned transport is created for each real request.
        # Injected transports remain available for deterministic tests.
        transport = (
            self.transport
            if self.transport is not None
            else create_pinned_sync_transport(self.validated_endpoint)
        )

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:

                with client.stream(
                    "POST",
                    self.validated_endpoint.url,
                    json=payload,
                    headers=headers,
                ) as response:

                    if response.status_code < 200 or response.status_code >= 300:
                        raise MCPClientError(
                            f"MCP server returned HTTP {response.status_code}."
                        )

                    content = bytearray()

                    for chunk in response.iter_bytes():
                        content.extend(chunk)

                        if len(content) > self.max_response_bytes:
                            raise MCPClientError(
                                "MCP response exceeded the configured size limit."
                            )

                    try:
                        response_data = json.loads(content)
                    except (ValueError, UnicodeDecodeError) as exc:
                        raise MCPClientError(
                            "MCP server returned invalid JSON."
                        ) from exc

        except httpx.TimeoutException as exc:
            raise MCPClientError("MCP request timed out.") from exc

        except httpx.HTTPError as exc:
            raise MCPClientError(
                f"MCP transport error: {exc}"
            ) from exc

        return request_id, response_data

    def discover(self):
        request_id, response = self._request("server/discover")
        return validate_discover_response(response, request_id)

    def list_tools(self):
        request_id, response = self._request("tools/list")
        return validate_tools_list_response(response, request_id)

    def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        tool_definition: dict | None = None,
    ):
        if not isinstance(name, str) or not name:
            raise ValueError("Tool name must be a non-empty string.")

        if arguments is not None and not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a dictionary.")

        request_id, response = self._request(
            "tools/call",
            params={
                "name": name,
                "arguments": arguments or {},
            },
            tool_name=name,
        )

        return validate_tool_call_response(
            response,
            request_id,
            tool_definition=tool_definition,
        )
