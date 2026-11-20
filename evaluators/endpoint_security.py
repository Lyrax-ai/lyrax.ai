import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


class EndpointSecurityError(ValueError):
    """Raised when an endpoint violates Lyrax security policy."""


@dataclass(frozen=True)
class ValidatedEndpoint:
    url: str
    scheme: str
    hostname: str
    port: int
    resolved_addresses: tuple[str, ...]


def validate_endpoint(
    endpoint: str,
    allow_private_network: bool = False,
    resolver=None,
) -> ValidatedEndpoint:
    if not isinstance(endpoint, str) or not endpoint:
        raise EndpointSecurityError("Endpoint must be a non-empty string.")

    if endpoint != endpoint.strip():
        raise EndpointSecurityError("Endpoint cannot contain surrounding whitespace.")

    if any(ord(char) < 32 or ord(char) == 127 for char in endpoint):
        raise EndpointSecurityError("Endpoint contains control characters.")

    if "\\" in endpoint:
        raise EndpointSecurityError("Endpoint cannot contain backslashes.")

    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise EndpointSecurityError("Endpoint URL is malformed.") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise EndpointSecurityError("Only HTTP and HTTPS endpoints are supported.")

    if not parsed.hostname:
        raise EndpointSecurityError("Endpoint must contain a hostname.")

    if parsed.username is not None or parsed.password is not None:
        raise EndpointSecurityError("Embedded endpoint credentials are prohibited.")

    if parsed.fragment:
        raise EndpointSecurityError("Endpoint fragments are prohibited.")

    hostname = parsed.hostname.rstrip(".").lower()

    if not hostname:
        raise EndpointSecurityError("Endpoint hostname is invalid.")

    effective_port = port or (443 if parsed.scheme.lower() == "https" else 80)

    if not 1 <= effective_port <= 65535:
        raise EndpointSecurityError("Endpoint port is invalid.")

    if allow_private_network:
        return ValidatedEndpoint(
            url=endpoint,
            scheme=parsed.scheme.lower(),
            hostname=hostname,
            port=effective_port,
            resolved_addresses=(),
        )

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise EndpointSecurityError("Localhost endpoints are prohibited.")

    try:
        literal_ip = ipaddress.ip_address(hostname)
        addresses = [literal_ip]
    except ValueError:
        try:
            resolve = resolver or socket.getaddrinfo

            results = resolve(
                hostname,
                effective_port,
                type=socket.SOCK_STREAM,
            )

            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in results
            ]

        except (OSError, ValueError) as exc:
            raise EndpointSecurityError(
                f"Could not safely resolve endpoint hostname: {exc}"
            ) from exc

    if not addresses:
        raise EndpointSecurityError("Endpoint hostname resolved to no addresses.")

    for address in addresses:
        if not address.is_global:
            raise EndpointSecurityError(
                "Endpoint resolves to a non-public IP address."
            )

    return ValidatedEndpoint(
        url=endpoint,
        scheme=parsed.scheme.lower(),
        hostname=hostname,
        port=effective_port,
        resolved_addresses=tuple(
            sorted({str(address) for address in addresses})
        ),
    )
