"""Unit tests for SSRF protection and unsafe IP verification."""
import pytest

from sangyan.core.errors import SecurityViolationError
from sangyan.security.ssrf import is_unsafe_ip, validate_url_shape, validate_url_ssrf


class TestSSRFProtection:
    def test_unsafe_ip_detection(self):
        # Loopback
        assert is_unsafe_ip("127.0.0.1") is True
        assert is_unsafe_ip("::1") is True
        # Private RFC 1918
        assert is_unsafe_ip("10.0.0.1") is True
        assert is_unsafe_ip("172.16.0.1") is True
        assert is_unsafe_ip("192.168.1.100") is True
        # Cloud metadata / link-local
        assert is_unsafe_ip("169.254.169.254") is True
        # Multicast / unspecified
        assert is_unsafe_ip("224.0.0.1") is True
        assert is_unsafe_ip("0.0.0.0") is True

        # Public IPs must be safe
        assert is_unsafe_ip("8.8.8.8") is False
        assert is_unsafe_ip("1.1.1.1") is False

    def test_url_shape_validation(self):
        # Valid URLs
        parsed = validate_url_shape("https://www.sebi.gov.in/filings")
        assert parsed.scheme == "https"
        assert parsed.hostname == "www.sebi.gov.in"

        # Invalid schemes
        with pytest.raises(SecurityViolationError) as exc:
            validate_url_shape("file:///etc/passwd")
        assert "UNSUPPORTED_SCHEME" in exc.value.code

        with pytest.raises(SecurityViolationError) as exc:
            validate_url_shape("gopher://internal-service")
        assert "UNSUPPORTED_SCHEME" in exc.value.code

        # Localhost blocking
        with pytest.raises(SecurityViolationError) as exc:
            validate_url_shape("http://localhost:8000/admin")
        assert "SSRF_BLOCKED" in exc.value.code

        with pytest.raises(SecurityViolationError) as exc:
            validate_url_shape("http://127.0.0.1:5432")
        assert "SSRF_BLOCKED" in exc.value.code

    def test_validate_url_ssrf_resolves_and_blocks_loopback(self):
        with pytest.raises(SecurityViolationError):
            validate_url_ssrf("http://127.0.0.1/test")
