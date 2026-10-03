"""Ingestion service converting raw text or URLs into canonical ContentItem records."""
from __future__ import annotations

import time
from typing import Any, Optional

from sangyan.crypto.hashing import sha3_256_text
from sangyan.domain.models import ContentItem
from sangyan.ingest.cleaner import clean_text, extract_urls
from sangyan.ingest.fetcher import FetchedContent, UrlFetcher
from sangyan.tenancy.repository import TenantRepository


class IngestionService:
    """Service for ingesting, normalizing, and persisting user-submitted content."""

    def __init__(self, repository: TenantRepository, fetcher: Optional[UrlFetcher] = None) -> None:
        self.repository = repository
        self.fetcher = fetcher or UrlFetcher()

    def ingest_text(
        self,
        raw_text: str,
        *,
        source_uri: Optional[str] = None,
        channel: str = "DIRECT_INPUT",
        platform: Optional[str] = None,
        language_hint: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ContentItem:
        """Ingest raw textual content (e.g. WhatsApp message, SMS, social post).

        Normalizes text, strips evasion artifacts, extracts embedded URLs, computes
        canonical SHA3-256 hash, and saves the ContentItem.
        """
        cleaned = clean_text(raw_text)
        content_hash = sha3_256_text(cleaned if cleaned else raw_text)
        detected_urls = extract_urls(raw_text)

        meta = dict(metadata or {})
        meta["channel"] = channel
        if platform:
            meta["platform"] = platform
        if detected_urls:
            meta["extracted_urls"] = detected_urls
        meta["raw_length"] = len(raw_text)
        meta["cleaned_length"] = len(cleaned)

        item = ContentItem(
            organization_id=self.repository.organization_id,
            content_type="text",
            raw_content=raw_text,
            normalized_text=cleaned,
            source_url=source_uri or "",
            content_hash=content_hash,
            language=language_hint or "en",
            metadata=meta,
        )

        item_id = self.repository.save_content_item(item)
        item.id = item_id
        return item

    def ingest_url(
        self,
        url: str,
        *,
        channel: str = "URL_SUBMISSION",
        platform: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ContentItem:
        """Fetch remote URL safely under SSRF protection, clean text, and persist as ContentItem."""
        fetched: FetchedContent = self.fetcher.fetch(url)

        meta = dict(metadata or {})
        meta["channel"] = channel
        meta["platform"] = platform or "WEB"
        meta["final_url"] = fetched.final_url
        meta["http_status"] = fetched.status_code
        meta["http_content_type"] = fetched.content_type
        meta["fetch_duration_ms"] = fetched.fetch_duration_ms
        if fetched.title:
            meta["title"] = fetched.title
        extracted_urls = extract_urls(fetched.raw_content)
        if extracted_urls:
            meta["extracted_urls"] = extracted_urls[:50]  # bound list of links

        item = ContentItem(
            organization_id=self.repository.organization_id,
            content_type="url",
            raw_content=fetched.raw_content,
            normalized_text=fetched.extracted_text,
            source_url=url,
            content_hash=fetched.content_hash,
            metadata=meta,
        )

        item_id = self.repository.save_content_item(item)
        item.id = item_id
        return item
