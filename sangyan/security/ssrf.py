"""SSRF protection and DNS-rebinding prevention for network ingestion."""
from __future__ import annotations

import ipaddress
import socket
from contextlib import contextmanager
from urllib.parse import urlparse

from sangyan.core.errors import SecurityViolationError

# Optional urllib3 hook if installed
try:
    import urllib3.util.connection as _urllib3_connection
except ImportError:
    _urllib3_connection = None

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "127.0.0.1", "::1"}


def validate_url_shape(url: str):
    """Format-only validation of URL scheme and host without network access."""
    if not url or not isinstance(url, str):
        raise SecurityViolationError("The URL is missing or empty.", code="INVALID_URL")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise SecurityViolationError("The URL is not well-formed.", code="INVALID_URL") from exc

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SecurityViolationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.",
            code="UNSUPPORTED_SCHEME",
        )
    if not parsed.hostname:
        raise SecurityViolationError("The URL has no hostname.", code="INVALID_HOST")

    if parsed.hostname.lower() in BLOCKED_HOSTNAMES:
        raise SecurityViolationError("Requests to localhost are blocked.", code="SSRF_BLOCKED")

    return parsed


def is_unsafe_ip(ip_str: str) -> bool:
    """Check whether an IP address is private, loopback, link-local, reserved, or multicast."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # Treat unparseable IPs as unsafe by default
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_url_ssrf(url: str):
    """Format check + DNS resolution + IP range verification."""
    parsed = validate_url_shape(url)
    hostname = parsed.hostname.lower()

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, OSError) as exc:
        raise SecurityViolationError(f"Host '{hostname}' could not be resolved.", code="DNS_RESOLUTION_FAILED") from exc

    if not addrinfo:
        raise SecurityViolationError(f"Host '{hostname}' could not be resolved.", code="DNS_RESOLUTION_FAILED")

    for _family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if is_unsafe_ip(ip_str):
            raise SecurityViolationError(
                f"URL resolves to restricted IP range ({ip_str}); connection blocked.",
                code="SSRF_BLOCKED",
            )
    return parsed


_real_socket_create_connection = socket.create_connection
_real_urllib3_create_connection = getattr(_urllib3_connection, "create_connection", None) if _urllib3_connection else None


def _ssrf_checked_create_connection(address, *args, **kwargs):
    """Hook intercepting socket connection to verify IP at connect time, preventing DNS rebinding."""
    host = address[0]
    try:
        infos = socket.getaddrinfo(host, address[1])
    except OSError:
        infos = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        if is_unsafe_ip(sockaddr[0]):
            raise SecurityViolationError(
                f"Connection to internal IP {sockaddr[0]} blocked at socket connect.",
                code="SSRF_BLOCKED",
            )
    return _real_socket_create_connection(address, *args, **kwargs)


@contextmanager
def ssrf_safe_connections():
    """Context manager scoping socket creation to DNS-rebinding-safe verification."""
    old_socket = socket.create_connection
    socket.create_connection = _ssrf_checked_create_connection
    if _urllib3_connection is not None:
        _urllib3_connection.create_connection = _ssrf_checked_create_connection
    try:
        yield
    finally:
        socket.create_connection = old_socket
        if _urllib3_connection is not None and _real_urllib3_create_connection is not None:
            _urllib3_connection.create_connection = _real_urllib3_create_connection
