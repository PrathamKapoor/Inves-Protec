"""Unit and integration tests for sangyan.ingest (text cleaning, SSRF-safe fetching, IngestionService)."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from sangyan.core.errors import SecurityViolationError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import ContentItem
from sangyan.ingest.cleaner import clean_text, extract_urls
from sangyan.ingest.fetcher import FetchedContent, IngestionError, UrlFetcher
from sangyan.ingest.service import IngestionService
from sangyan.tenancy.repository import TenantAdministration, TenantRepository


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_ingest.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Ingestion Test Org")
        user_id = admin.create_user("ingest@test.org", "Ingest Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        yield TenantRepository(engine, org_id, user_id)
        engine.close()


class TestCleaner:
    def test_clean_text_strips_zero_width_characters(self):
        # Scammers inject zero-width spaces (U+200B) between characters: S​E​B​I
        evasive = "S\u200bE\u200cB\u200dI registered broker"
        cleaned = clean_text(evasive)
        assert cleaned == "SEBI registered broker"

    def test_clean_text_extracts_html_and_unescapes(self):
        html_input = """
        <html>
            <head><title>Test</title><style>.hidden{display:none}</style></head>
            <body>
                <h1>Guaranteed Profit Scheme &amp; Advisory</h1>
                <p>Deposit &#8377;10,000 today &amp; get 100% returns.<script>alert('xss')</script></p>
            </body>
        </html>
        """
        cleaned = clean_text(html_input)
        assert "Guaranteed Profit Scheme & Advisory" in cleaned
        assert "Deposit ₹10,000 today & get 100% returns." in cleaned
        assert "alert('xss')" not in cleaned
        assert ".hidden" not in cleaned

    def test_clean_text_normalizes_whitespace_and_unicode_nfkc(self):
        # Fullwidth Latin letters: ＳＥＢＩ -> SEBI
        fullwidth = "ＳＥＢＩ   \n\n\n\n   approved"
        cleaned = clean_text(fullwidth)
        assert cleaned == "SEBI\n\napproved"

    def test_extract_urls(self):
        text = "Visit https://groww.in or our portal http://suspicious-profit.cc/join for offers. Also https://t.me/fake_group."
        urls = extract_urls(text)
        assert "https://groww.in" in urls
        assert "http://suspicious-profit.cc/join" in urls
        assert "https://t.me/fake_group" in urls


class TestUrlFetcher:
    def test_fetch_blocks_ssrf_private_ips(self):
        fetcher = UrlFetcher()
        # Private IPs must be rejected immediately by SSRF preflight
        with pytest.raises(SecurityViolationError):
            fetcher.fetch("http://127.0.0.1/admin")

        with pytest.raises(SecurityViolationError):
            fetcher.fetch("http://169.254.169.254/latest/meta-data")

    def test_fetch_mocked_success(self):
        fetcher = UrlFetcher()

        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.encoding = "utf-8"
        mock_response.iter_bytes.return_value = [
            b"<html><head><title>Invest Pro</title></head><body>Double your money</body></html>"
        ]

        with patch("httpx.Client.send", return_value=mock_response):
            result = fetcher.fetch("https://example.com/invest")

        assert result.status_code == 200
        assert result.title == "Invest Pro"
        assert "Double your money" in result.extracted_text
        assert len(result.content_hash) == 64


class TestIngestionService:
    def test_ingest_text(self, repo):
        service = IngestionService(repo)
        raw = "Exclusive offer: 100% guaranteed returns on WhatsApp. Contact https://wa.me/12345."
        item = service.ingest_text(raw, channel="WHATSAPP", platform="ANDROID")

        assert item.id.startswith("content_")
        assert item.organization_id == repo.organization_id
        assert item.content_type == "text"
        assert item.metadata["channel"] == "WHATSAPP"
        assert item.metadata["platform"] == "ANDROID"
        assert "https://wa.me/12345" in item.metadata["extracted_urls"]
        assert len(item.content_hash) == 64

        # Read back from repo
        fetched = repo.get_content_item(item.id)
        assert fetched.id == item.id
        assert fetched.raw_content == raw
