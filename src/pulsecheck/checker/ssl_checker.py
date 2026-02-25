import asyncio
import logging
import ssl
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SSL_CONNECT_TIMEOUT = 10  # seconds


def _format_x509_name(x509_name: list[tuple[tuple[str, str], ...]]) -> str:
    """Format an X.509 distinguished name into a readable string."""
    parts = []
    for rdn in x509_name:
        for attr_type, attr_value in rdn:
            parts.append(f"{attr_type}={attr_value}")
    return ", ".join(parts)


def _parse_cert_date(date_str: str) -> datetime:
    """Parse SSL certificate date string to datetime."""
    # OpenSSL date format: 'Mon DD HH:MM:SS YYYY GMT'
    return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=timezone.utc
    )


async def check_ssl_certificate(host: str, port: int = 443) -> dict[str, Any]:
    """Connect to a host and retrieve SSL certificate details.

    Returns a dict with: issuer, subject, not_before, not_after,
    days_until_expiry, serial_number.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_cert_info, host, port)


def _get_cert_info(host: str, port: int) -> dict[str, Any]:
    """Synchronous SSL certificate retrieval."""
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=SSL_CONNECT_TIMEOUT) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()

    if not cert:
        raise ValueError(f"No certificate returned by {host}:{port}")

    not_before = _parse_cert_date(cert["notBefore"])
    not_after = _parse_cert_date(cert["notAfter"])
    now = datetime.now(timezone.utc)
    days_until_expiry = (not_after - now).days

    issuer = _format_x509_name(cert.get("issuer", []))
    subject = _format_x509_name(cert.get("subject", []))
    serial_number = str(cert.get("serialNumber", ""))

    return {
        "issuer": issuer,
        "subject": subject,
        "not_before": not_before,
        "not_after": not_after,
        "days_until_expiry": days_until_expiry,
        "serial_number": serial_number,
    }


def extract_host_from_url(url: str) -> str | None:
    """Extract hostname from a URL. Returns None if not HTTPS."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    return parsed.hostname
