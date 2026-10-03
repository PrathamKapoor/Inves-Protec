"""Verification caching and rate limiting with TTL freshness controls."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from sangyan.crypto.hashing import digest_document, sha3_hex


@dataclass
class CacheEntry:
    """A cached verification or authoritative retrieval result."""

    key: str
    data: Any
    source_id: str
    content_hash: str
    created_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class VerificationCache:
    """In-memory thread-safe TTL cache with cryptographic content hashing and freshness tracking."""

    def __init__(self, default_ttl_sec: int = 3600) -> None:
        self.default_ttl_sec = default_ttl_sec
        self._entries: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def make_key(self, source_id: str, identifier: str, version: str = "default") -> str:
        """Construct deterministic cache key."""
        raw = f"{source_id}:{identifier.lower().strip()}:{version}"
        return sha3_hex(raw.encode("utf-8"))

    def get(self, key: str) -> Optional[Any]:
        """Retrieve entry if present and not expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._entries[key]
                return None
            return entry.data

    def set(
        self,
        key: str,
        data: Any,
        source_id: str,
        ttl_sec: Optional[int] = None,
    ) -> CacheEntry:
        """Store data in cache with TTL and content hash."""
        now = time.time()
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        content_hash = digest_document(data) if isinstance(data, (dict, list, str, int, float)) else ""

        entry = CacheEntry(
            key=key,
            data=data,
            source_id=source_id,
            content_hash=content_hash,
            created_at=now,
            expires_at=now + ttl,
        )
        with self._lock:
            self._entries[key] = entry
        return entry

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class RateLimiter:
    """Thread-safe sliding-window rate limiter per source to prevent upstream denial-of-service."""

    def __init__(self, default_requests_per_sec: float = 5.0) -> None:
        self.default_rate = default_requests_per_sec
        self._history: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow_request(self, source_id: str, max_rate: Optional[float] = None) -> bool:
        """Check whether a request is allowed within rate limits."""
        limit = max_rate if max_rate is not None else self.default_rate
        now = time.time()
        window_start = now - 1.0

        with self._lock:
            history = self._history.setdefault(source_id, [])
            # Prune calls older than 1 second
            self._history[source_id] = [ts for ts in history if ts > window_start]

            if len(self._history[source_id]) >= limit:
                return False

            self._history[source_id].append(now)
            return True

    @staticmethod
    def calculate_backoff(attempt: int, base_delay: float = 0.5, max_delay: float = 4.0) -> float:
        """Exponential backoff delay in seconds."""
        delay = base_delay * (2 ** max(attempt, 0))
        return min(delay, max_delay)

