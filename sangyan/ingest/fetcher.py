"""SSRF-protected HTTP URL fetcher with bounded streaming and extraction."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Optional

import httpx

from sangyan.core.errors import SangyanError, SecurityViolationError
from sangyan.crypto.hashing import sha3_256_text
from sangyan.ingest.cleaner import clean_text
from sangyan.security.ssrf import ssrf_safe_connections, validate_url_ssrf


class IngestionError(SangyanError):
    """Raised when content fetching or processing fails."""


@dataclass
class FetchedContent:
    """Canonical representation of content retrieved from a network URL."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    raw_content: str
    extracted_text: str
    title: Optional[str] = None
    content_hash: str = ""
    fetch_duration_ms: float = 0.0
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = sha3_256_text(self.raw_content)


class _TitleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    def get_title(self) -> str:
        return " ".join("".join(self.title_parts).split())


class UrlFetcher:
    """SSRF-safe, bounded HTTP client for retrieving suspicious web content."""

    DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; SangyanInvestorSafety/1.0; +https://sangyan.gov.in)"
    MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB limit prevents decompression or memory exhaustion
    CONNECT_TIMEOUT_SEC = 3.0
    READ_TIMEOUT_SEC = 5.0
    MAX_REDIRECTS = 3

    def __init__(
        self,
        max_size_bytes: int = MAX_SIZE_BYTES,
        connect_timeout: float = CONNECT_TIMEOUT_SEC,
        read_timeout: float = READ_TIMEOUT_SEC,
    ) -> None:
        self.max_size_bytes = max_size_bytes
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def fetch(self, url: str) -> FetchedContent:
        """Fetch content safely from the given URL.

        Enforces:
        - Strict SSRF check on initial URL and each redirected URL
        - Socket-level interception preventing DNS-rebinding
        - Bounded streaming (max 2MB)
        - Timeout protection
        """
        # 1. Pre-flight SSRF check
        validate_url_ssrf(url)

        headers = {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        }

        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.read_timeout,
            pool=self.connect_timeout,
        )

        start_time = time.perf_counter()

        # Wrap in socket-level SSRF interceptor
        with ssrf_safe_connections():
            try:
                # We handle redirects manually to ensure every redirect target is validated against SSRF
                current_url = url
                redirect_count = 0

                with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                    while True:
                        req = client.build_request("GET", current_url, headers=headers)
                        response = client.send(req, stream=True)

                        # Handle redirects
                        if response.is_redirect:
                            redirect_count += 1
                            if redirect_count > self.MAX_REDIRECTS:
                                response.close()
                                raise IngestionError(
                                    f"Exceeded maximum allowed redirects ({self.MAX_REDIRECTS})"
                                )

                            location = response.headers.get("location")
                            response.close()
                            if not location:
                                raise IngestionError("Redirect received without Location header")

                            # Resolve relative redirect URLs
                            resolved = str(req.url.join(location))
                            # Re-verify redirect URL against SSRF policy
                            validate_url_ssrf(resolved)
                            current_url = resolved
                            continue

                        # Not a redirect, read body under size bounds
                        chunks: list[bytes] = []
                        total_bytes = 0

                        for chunk in response.iter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_size_bytes:
                                response.close()
                                raise IngestionError(
                                    f"Response exceeded maximum allowed size of {self.max_size_bytes} bytes"
                                )
                            chunks.append(chunk)

                        response.close()
                        break

            except httpx.TimeoutException as exc:
                raise IngestionError(f"Connection timed out retrieving URL '{url}': {exc}") from exc
            except httpx.RequestError as exc:
                raise IngestionError(f"Network error retrieving URL '{url}': {exc}") from exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        content_bytes = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        try:
            raw_text = content_bytes.decode(encoding, errors="replace")
        except Exception:
            raw_text = content_bytes.decode("utf-8", errors="replace")

        # Extract title if HTML
        title: Optional[str] = None
        content_type = response.headers.get("content-type", "").lower()
        if "html" in content_type or "<html" in raw_text[:500].lower():
            title_parser = _TitleExtractor()
            try:
                title_parser.feed(raw_text)
                title = title_parser.get_title() or None
            except Exception:
                title = None

        extracted_text = clean_text(raw_text)

        header_dict = {k.lower(): v for k, v in response.headers.items()}

        return FetchedContent(
            requested_url=url,
            final_url=current_url,
            status_code=response.status_code,
            content_type=content_type,
            raw_content=raw_text,
            extracted_text=extracted_text,
            title=title,
            fetch_duration_ms=round(duration_ms, 2),
            headers=header_dict,
        )
