from __future__ import annotations

"""
ThinkWiki Module: url_safety

Purpose:
- Validate outbound fetch URLs to reduce SSRF risk for user-supplied links.
"""

import ipaddress
import os
import socket
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google",
})

_METADATA_IPV4 = ipaddress.ip_address("169.254.169.254")


def _allow_private_url_fetch() -> bool:
    return os.environ.get("THINKWIKI_ALLOW_PRIVATE_URL_FETCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip == _METADATA_IPV4
    )


def validate_fetch_url(url: str) -> str:
    """Validate a user-supplied URL before outbound fetch.

    Raises ValueError when the URL is unsafe or malformed.
    """
    normalized = url.strip()
    if _allow_private_url_fetch():
        return normalized
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"URL scheme not allowed: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError(f"URL hostname not allowed: {hostname}")
    try:
        addr_infos = socket.getaddrinfo(
            hostname,
            parsed.port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve URL hostname {hostname!r}") from exc
    if not addr_infos:
        raise ValueError(f"Could not resolve URL hostname {hostname!r}")
    for info in addr_infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise ValueError(f"URL resolves to blocked address: {ip}")
    return normalized


class _SafeRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_fetch_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(request: urllib_request.Request, timeout: int = 30):
    validate_fetch_url(request.full_url)
    opener = urllib_request.build_opener(_SafeRedirectHandler)
    return opener.open(request, timeout=timeout)


def fetch_url_text(request: urllib_request.Request, timeout: int = 30) -> bytes:
    with safe_urlopen(request, timeout=timeout) as response:
        return response.read()
