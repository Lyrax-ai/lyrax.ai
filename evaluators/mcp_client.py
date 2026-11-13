import itertools
import ipaddress
import json
import socket
from urllib.parse import urlparse

import httpx

from evaluators.mcp import (
    MCP_SPEC_VERSION,
    validate_discover_response,
    validate_tools_list_response,
    validate_tool_call_response,
)


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

        self._validate_endpoint()

    def _validate_endpoint(self):
        parsed = urlparse(self.endpoint)

        if parsed.scheme not in {"http", "https"}:
            raise MCPClientError("Endpoint must use HTTP or HTTPS.")

        if not parsed.hostname:
            raise MCPClientError("Endpoint must contain a hostname.")

        if parsed.username or parsed.password:
            raise MCPClientError(
                "Credentials must not be embedded in endpoint URLs."
            )

        if parsed.fragment:
            raise MCPClientError("Endpoint URLs must not contain fragments.")

        if self.allow_private_network:
            return

        try:
            addresses = socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise MCPClientError(
                f"Could not resolve endpoint hostname: {exc}"
            ) from exc

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])

            if not ip.is_global:
                raise MCPClientError(
                    "Endpoint resolves to a non-public IP address."
                )

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

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:

                with client.stream(
                    "POST",
                    self.endpoint,
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
