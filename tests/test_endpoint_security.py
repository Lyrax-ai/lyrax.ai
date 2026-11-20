import socket

import pytest

from evaluators.endpoint_security import (
    EndpointSecurityError,
    validate_endpoint,
)


def public_resolver(host, port, type=None):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", port),
        )
    ]


def test_valid_public_endpoint():
    result = validate_endpoint(
        "https://example.com/mcp",
        resolver=public_resolver,
    )

    assert result.hostname == "example.com"
    assert result.scheme == "https"
    assert result.port == 443
    assert result.resolved_addresses == ("8.8.8.8",)


@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "https://user:password@example.com",
        "https://example.com/path#fragment",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://192.168.1.10",
        "http://10.0.0.1",
        "http://[::1]",
        "https://example.com:99999",
        "https://example.com\\@127.0.0.1",
    ],
)
def test_unsafe_endpoints_rejected(endpoint):
    with pytest.raises(EndpointSecurityError):
        validate_endpoint(endpoint, resolver=public_resolver)


def test_private_dns_resolution_rejected():
    def private_resolver(host, port, type=None):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", port),
            )
        ]

    with pytest.raises(EndpointSecurityError):
        validate_endpoint(
            "https://example.com",
            resolver=private_resolver,
        )


def test_mixed_public_and_private_dns_rejected():
    def mixed_resolver(host, port, type=None):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("8.8.8.8", port),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.0.0.1", port),
            ),
        ]

    with pytest.raises(EndpointSecurityError):
        validate_endpoint(
            "https://example.com",
            resolver=mixed_resolver,
        )


def test_private_network_requires_explicit_permission():
    result = validate_endpoint(
        "http://127.0.0.1:8000",
        allow_private_network=True,
    )

    assert result.hostname == "127.0.0.1"
    assert result.port == 8000


def test_dns_resolution_failure_rejected():
    def failing_resolver(host, port, type=None):
        raise socket.gaierror("DNS lookup failed")

    with pytest.raises(EndpointSecurityError):
        validate_endpoint(
            "https://unknown.example",
            resolver=failing_resolver,
        )
