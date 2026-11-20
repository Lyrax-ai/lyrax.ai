from __future__ import annotations

import ipaddress
from typing import Any

import httpx


class PinnedConnectionError(httpx.TransportError):
    """Raised when a connection attempts to leave its validated endpoint."""


def _normalize_host(host: str) -> str:
    return host.rstrip(".").lower()


class _PinnedSyncBackend:
    def __init__(self, backend: Any, hostname: str, port: int, address: str):
        self._backend = backend
        self._hostname = _normalize_host(hostname)
        self._port = port
        self._address = str(ipaddress.ip_address(address))

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ):
        if _normalize_host(host) != self._hostname or port != self._port:
            raise PinnedConnectionError(
                "Connection target does not match the validated endpoint."
            )

        return self._backend.connect_tcp(
            host=self._address,
            port=self._port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def __getattr__(self, name: str):
        return getattr(self._backend, name)


class _PinnedAsyncBackend:
    def __init__(self, backend: Any, hostname: str, port: int, address: str):
        self._backend = backend
        self._hostname = _normalize_host(hostname)
        self._port = port
        self._address = str(ipaddress.ip_address(address))

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ):
        if _normalize_host(host) != self._hostname or port != self._port:
            raise PinnedConnectionError(
                "Connection target does not match the validated endpoint."
            )

        return await self._backend.connect_tcp(
            host=self._address,
            port=self._port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def __getattr__(self, name: str):
        return getattr(self._backend, name)


def _endpoint_values(validated_endpoint: Any):
    hostname = validated_endpoint.hostname
    port = validated_endpoint.port
    addresses = validated_endpoint.resolved_addresses

    if not hostname or not port or not addresses:
        raise ValueError(
            "Validated endpoint must contain a hostname, port, "
            "and at least one resolved IP address."
        )

    return hostname, port, addresses[0]


def create_pinned_sync_transport(validated_endpoint: Any):
    hostname, port, address = _endpoint_values(validated_endpoint)

    transport = httpx.HTTPTransport(trust_env=False)
    backend = transport._pool._network_backend

    transport._pool._network_backend = _PinnedSyncBackend(
        backend, hostname, port, address
    )

    return transport


def create_pinned_async_transport(validated_endpoint: Any):
    hostname, port, address = _endpoint_values(validated_endpoint)

    transport = httpx.AsyncHTTPTransport(trust_env=False)
    backend = transport._pool._network_backend

    transport._pool._network_backend = _PinnedAsyncBackend(
        backend, hostname, port, address
    )

    return transport
