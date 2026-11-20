import asyncio
from types import SimpleNamespace

import pytest

from evaluators.pinned_transport import (
    PinnedConnectionError,
    _PinnedAsyncBackend,
    _PinnedSyncBackend,
    create_pinned_async_transport,
    create_pinned_sync_transport,
)


class FakeSyncBackend:
    def __init__(self):
        self.calls = []

    def connect_tcp(self, **kwargs):
        self.calls.append(kwargs)
        return "sync connection"


class FakeAsyncBackend:
    def __init__(self):
        self.calls = []

    async def connect_tcp(self, **kwargs):
        self.calls.append(kwargs)
        return "async connection"


@pytest.fixture
def endpoint():
    return SimpleNamespace(
        hostname="example.com",
        port=443,
        resolved_addresses=("93.184.216.34",),
    )


def test_sync_backend_connects_to_validated_ip(endpoint):
    backend = FakeSyncBackend()
    pinned = _PinnedSyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    result = pinned.connect_tcp(
        host="example.com",
        port=443,
        timeout=5.0,
    )

    assert result == "sync connection"
    assert backend.calls[0]["host"] == "93.184.216.34"
    assert backend.calls[0]["port"] == 443


def test_sync_backend_normalizes_hostname(endpoint):
    backend = FakeSyncBackend()
    pinned = _PinnedSyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    pinned.connect_tcp(host="EXAMPLE.COM.", port=443)

    assert backend.calls[0]["host"] == "93.184.216.34"


def test_sync_backend_rejects_unvalidated_hostname(endpoint):
    backend = FakeSyncBackend()
    pinned = _PinnedSyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    with pytest.raises(PinnedConnectionError):
        pinned.connect_tcp(host="attacker.example", port=443)

    assert backend.calls == []


def test_sync_backend_rejects_unvalidated_port(endpoint):
    backend = FakeSyncBackend()
    pinned = _PinnedSyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    with pytest.raises(PinnedConnectionError):
        pinned.connect_tcp(host="example.com", port=8443)

    assert backend.calls == []


def test_async_backend_connects_to_validated_ip(endpoint):
    backend = FakeAsyncBackend()
    pinned = _PinnedAsyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    result = asyncio.run(
        pinned.connect_tcp(
            host="example.com",
            port=443,
            timeout=5.0,
        )
    )

    assert result == "async connection"
    assert backend.calls[0]["host"] == "93.184.216.34"
    assert backend.calls[0]["port"] == 443


def test_async_backend_rejects_unvalidated_target(endpoint):
    backend = FakeAsyncBackend()
    pinned = _PinnedAsyncBackend(
        backend,
        endpoint.hostname,
        endpoint.port,
        endpoint.resolved_addresses[0],
    )

    async def attempt():
        with pytest.raises(PinnedConnectionError):
            await pinned.connect_tcp(
                host="attacker.example",
                port=443,
            )

    asyncio.run(attempt())

    assert backend.calls == []


def test_sync_transport_installs_pinned_backend(endpoint):
    transport = create_pinned_sync_transport(endpoint)

    try:
        assert isinstance(
            transport._pool._network_backend,
            _PinnedSyncBackend,
        )
    finally:
        transport.close()


def test_async_transport_installs_pinned_backend(endpoint):
    transport = create_pinned_async_transport(endpoint)

    async def check():
        try:
            assert isinstance(
                transport._pool._network_backend,
                _PinnedAsyncBackend,
            )
        finally:
            await transport.aclose()

    asyncio.run(check())
