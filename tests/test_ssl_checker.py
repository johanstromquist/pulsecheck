import socket
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pulsecheck.checker.ssl_checker import (
    _format_x509_name,
    _get_cert_info,
    _parse_cert_date,
    check_ssl_certificate,
    extract_host_from_url,
)


class TestExtractHostFromUrl:
    def test_https_url(self):
        assert extract_host_from_url("https://example.com") == "example.com"

    def test_https_with_path(self):
        assert extract_host_from_url("https://example.com/path/to/page") == "example.com"

    def test_https_with_port(self):
        assert extract_host_from_url("https://example.com:8443/api") == "example.com"

    def test_http_url_returns_none(self):
        assert extract_host_from_url("http://example.com") is None

    def test_no_scheme_returns_none(self):
        assert extract_host_from_url("example.com") is None

    def test_subdomain(self):
        assert extract_host_from_url("https://api.example.com") == "api.example.com"


class TestFormatX509Name:
    def test_simple_name(self):
        name = [
            (("commonName", "example.com"),),
            (("organizationName", "Example Inc"),),
        ]
        result = _format_x509_name(name)
        assert "commonName=example.com" in result
        assert "organizationName=Example Inc" in result

    def test_empty_name(self):
        assert _format_x509_name([]) == ""


class TestParseCertDate:
    def test_valid_date(self):
        result = _parse_cert_date("Jan 15 12:00:00 2025 GMT")
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc


class TestGetCertInfo:
    def test_successful_cert_retrieval(self):
        mock_cert = {
            "issuer": [(("commonName", "Test CA"),)],
            "subject": [(("commonName", "example.com"),)],
            "notBefore": "Jan 01 00:00:00 2024 GMT",
            "notAfter": "Dec 31 23:59:59 2030 GMT",
            "serialNumber": "ABC123",
        }

        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = mock_cert
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch("pulsecheck.checker.ssl_checker.socket.create_connection", return_value=mock_sock):
            with patch("pulsecheck.checker.ssl_checker.ssl.create_default_context") as mock_ctx:
                ctx_instance = MagicMock()
                ctx_instance.wrap_socket.return_value = mock_ssock
                mock_ctx.return_value = ctx_instance

                result = _get_cert_info("example.com", 443)

        assert "commonName=Test CA" in result["issuer"]
        assert "commonName=example.com" in result["subject"]
        assert result["serial_number"] == "ABC123"
        assert result["days_until_expiry"] > 0

    def test_no_cert_raises(self):
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = None
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch("pulsecheck.checker.ssl_checker.socket.create_connection", return_value=mock_sock):
            with patch("pulsecheck.checker.ssl_checker.ssl.create_default_context") as mock_ctx:
                ctx_instance = MagicMock()
                ctx_instance.wrap_socket.return_value = mock_ssock
                mock_ctx.return_value = ctx_instance

                with pytest.raises(ValueError, match="No certificate returned"):
                    _get_cert_info("example.com", 443)

    def test_connection_error_raises(self):
        with patch(
            "pulsecheck.checker.ssl_checker.socket.create_connection",
            side_effect=socket.timeout("connection timed out"),
        ):
            with pytest.raises(socket.timeout):
                _get_cert_info("unreachable.example.com", 443)


class TestCheckSSLCertificate:
    @pytest.mark.asyncio
    async def test_async_wrapper_calls_sync(self):
        mock_result = {
            "issuer": "Test CA",
            "subject": "example.com",
            "not_before": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime(2030, 12, 31, tzinfo=timezone.utc),
            "days_until_expiry": 1800,
            "serial_number": "ABC123",
        }

        with patch("pulsecheck.checker.ssl_checker._get_cert_info", return_value=mock_result):
            result = await check_ssl_certificate("example.com")
            assert result == mock_result
