"""Token-bucket rate limiting, failed-authentication throttling, and traffic shaping."""
from __future__ import annotations

import math
import threading
import time
from typing import Optional

from sangyan.security.models import RateLimitExceededError


class TokenBucket:
    """Thread-safe sliding token bucket with continuous refill."""

    def __init__(self, capacity: float, refill_rate: float) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)  # tokens per second
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.last_accessed = self.last_refill
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> tuple[bool, int, int]:
        """Attempt to consume tokens. Returns (allowed, remaining_tokens, retry_after_seconds)."""
        with self._lock:
            now = time.time()
            elapsed = max(0.0, now - self.last_refill)
            self.last_refill = now
            self.last_accessed = now

            # Refill tokens up to maximum capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

            if self.tokens >= amount:
                self.tokens -= amount
                return True, int(self.tokens), 0
            else:
                deficit = amount - self.tokens
                retry_after = math.ceil(deficit / self.refill_rate) if self.refill_rate > 0 else 60
                return False, int(self.tokens), max(1, retry_after)


class FailedAuthTracker:
    """Tracks consecutive authentication failures per IP address for brute-force mitigation."""

    def __init__(self, failure_threshold: int = 5, window_seconds: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def record_failure(self, client_ip: str) -> None:
        with self._lock:
            now = time.time()
            timestamps = self._failures.setdefault(client_ip, [])
            timestamps.append(now)
            # Evict timestamps outside sliding window
            cutoff = now - self.window_seconds
            self._failures[client_ip] = [t for t in timestamps if t >= cutoff]

    def record_success(self, client_ip: str) -> None:
        with self._lock:
            self._failures.pop(client_ip, None)

    def is_throttled(self, client_ip: str) -> tuple[bool, int]:
        with self._lock:
            now = time.time()
            timestamps = self._failures.get(client_ip, [])
            cutoff = now - self.window_seconds
            valid_timestamps = [t for t in timestamps if t >= cutoff]
            self._failures[client_ip] = valid_timestamps

            if len(valid_timestamps) >= self.failure_threshold:
                oldest_in_window = valid_timestamps[0]
                retry_after = math.ceil((oldest_in_window + self.window_seconds) - now)
                return True, max(1, retry_after)
            return False, 0


# Default rate limits per endpoint category: (capacity, refill_tokens_per_minute)
RATE_LIMIT_POLICIES: dict[str, tuple[int, int]] = {
    "auth": (10, 10),              # 10 req/min for auth endpoints
    "investigation": (30, 30),     # 30 req/min for compute-heavy verification
    "workflow_mutate": (20, 20),   # 20 req/min for graph mutation (start, resume, cancel)
    "read": (120, 120),            # 120 req/min for reads and inspections
    "default": (60, 60),           # 60 req/min default
}


class TokenBucketRateLimiter:
    """Central multi-dimensional rate limiter with endpoint class policies."""

    def __init__(
        self,
        policies: Optional[dict[str, tuple[int, int]]] = None,
        auth_failure_threshold: int = 5,
        auth_lockout_seconds: float = 60.0,
    ) -> None:
        self.policies = policies or dict(RATE_LIMIT_POLICIES)
        self.auth_tracker = FailedAuthTracker(
            failure_threshold=auth_failure_threshold,
            window_seconds=auth_lockout_seconds,
        )
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, key: str, endpoint_class: str) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                capacity, per_min = self.policies.get(endpoint_class, self.policies["default"])
                refill_rate = per_min / 60.0
                self._buckets[key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)
            return self._buckets[key]

    def check_rate_limit(
        self,
        identifier: str,
        endpoint_class: str = "default",
        consume_tokens: float = 1.0,
    ) -> tuple[bool, int, int, int]:
        """Check rate limit for caller and endpoint class.

        Returns (allowed, capacity_limit, remaining_tokens, retry_after_seconds).
        """
        key = f"{identifier}:{endpoint_class}"
        bucket = self._get_bucket(key, endpoint_class)
        allowed, remaining, retry_after = bucket.consume(consume_tokens)
        capacity = int(bucket.capacity)
        return allowed, capacity, remaining, retry_after

    def cleanup_stale_buckets(self, max_idle_seconds: float = 300.0) -> int:
        """Evict inactive buckets to conserve memory."""
        with self._lock:
            now = time.time()
            stale_keys = [
                k for k, b in self._buckets.items()
                if (now - b.last_accessed) > max_idle_seconds
            ]
            for k in stale_keys:
                del self._buckets[k]
            return len(stale_keys)
