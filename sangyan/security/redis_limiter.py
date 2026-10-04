"""Redis-backed distributed rate limiting and failed-authentication throttling."""
from __future__ import annotations

import math
import time
from typing import Any, Optional

from sangyan.security.rate_limiter import RATE_LIMIT_POLICIES, TokenBucketRateLimiter

# ---------------------------------------------------------------------------
# Atomic Lua Script for Token Bucket (Continuous Refill + Consumption)
# ---------------------------------------------------------------------------
# KEYS[1]: bucket key
# ARGV[1]: capacity (float)
# ARGV[2]: refill_rate in tokens/second (float)
# ARGV[3]: current timestamp in seconds (float)
# ARGV[4]: requested tokens (float)
# ARGV[5]: TTL in seconds (integer)
# Returns: {allowed (1 or 0), remaining_tokens (integer), retry_after (integer)}
LUA_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if not tokens or not last_refill then
    tokens = capacity
    last_refill = now
else
    local elapsed = math.max(0, now - last_refill)
    tokens = math.min(capacity, tokens + elapsed * refill_rate)
    last_refill = now
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call("HMSET", key, "tokens", tostring(tokens), "last_refill", tostring(last_refill))
    redis.call("EXPIRE", key, ttl)
    return {1, math.floor(tokens), 0}
else
    local deficit = requested - tokens
    local retry_after = 60
    if refill_rate > 0 then
        retry_after = math.ceil(deficit / refill_rate)
    end
    redis.call("HMSET", key, "tokens", tostring(tokens), "last_refill", tostring(last_refill))
    redis.call("EXPIRE", key, ttl)
    return {0, math.floor(tokens), math.max(1, retry_after)}
end
"""


class RedisFailedAuthTracker:
    """Tracks failed authentication attempts in Redis across all cluster replicas."""

    def __init__(
        self,
        redis_client: Any,
        failure_threshold: int = 5,
        window_seconds: float = 60.0,
        prefix: str = "sangyan:authfail",
    ) -> None:
        self.redis = redis_client
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.prefix = prefix

    def _get_key(self, client_ip: str) -> str:
        return f"{self.prefix}:{client_ip}"

    def record_failure(self, client_ip: str) -> None:
        """Record an auth failure timestamp in a Redis sorted set."""
        now = time.time()
        key = self._get_key(client_ip)
        try:
            pipe = self.redis.pipeline()
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, int(self.window_seconds * 2))
            pipe.execute()
        except Exception:
            pass  # Fallback gracefully if Redis is momentarily unavailable

    def record_success(self, client_ip: str) -> None:
        """Reset failed attempts on successful authentication."""
        key = self._get_key(client_ip)
        try:
            self.redis.delete(key)
        except Exception:
            pass

    def is_throttled(self, client_ip: str) -> tuple[bool, int]:
        """Check if client IP has exceeded the failure threshold within sliding window.
        
        Returns (is_throttled, retry_after_seconds).
        """
        now = time.time()
        key = self._get_key(client_ip)
        cutoff = now - self.window_seconds
        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zrange(key, 0, 0, withscores=True)
            _, count, oldest_items = pipe.execute()

            if count >= self.failure_threshold:
                if oldest_items:
                    oldest_score = oldest_items[0][1]
                    retry_after = math.ceil((oldest_score + self.window_seconds) - now)
                else:
                    retry_after = int(self.window_seconds)
                return True, max(1, retry_after)
            return False, 0
        except Exception:
            # On Redis error, fail-open for auth checking unless strict policy configured
            return False, 0


class RedisRateLimiter:
    """Cluster-wide distributed rate limiter backed by Redis with atomic Lua script execution."""

    def __init__(
        self,
        redis_client: Any = None,
        redis_url: Optional[str] = None,
        policies: Optional[dict[str, tuple[int, int]]] = None,
        auth_failure_threshold: int = 5,
        auth_lockout_seconds: float = 60.0,
        prefix: str = "sangyan:ratelimit",
        failure_mode: str = "fail_closed_mutations",
    ) -> None:
        if redis_client is not None:
            self.redis = redis_client
        elif redis_url:
            import redis

            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        else:
            raise ValueError("Either redis_client or redis_url must be provided for RedisRateLimiter")

        self.policies = policies or dict(RATE_LIMIT_POLICIES)
        self.prefix = prefix
        self.failure_mode = failure_mode  # fail_closed_mutations | fail_open | local_fallback
        self.local_fallback = TokenBucketRateLimiter(
            policies=self.policies,
            auth_failure_threshold=auth_failure_threshold,
            auth_lockout_seconds=auth_lockout_seconds,
        )
        self.auth_tracker = RedisFailedAuthTracker(
            redis_client=self.redis,
            failure_threshold=auth_failure_threshold,
            window_seconds=auth_lockout_seconds,
        )
        self._script = None

    def _get_script(self):
        if self._script is None:
            self._script = self.redis.register_script(LUA_TOKEN_BUCKET_SCRIPT)
        return self._script

    def ping(self) -> bool:
        """Check if Redis connection is responsive."""
        try:
            return bool(self.redis.ping())
        except Exception:
            return False

    def check_rate_limit(
        self,
        identifier: str,
        endpoint_class: str = "default",
        consume_tokens: float = 1.0,
    ) -> tuple[bool, int, int, int]:
        """Check and consume rate limit tokens cluster-wide across all API pods.
        
        Returns (allowed, capacity_limit, remaining_tokens, retry_after_seconds).
        """
        policy = self.policies.get(endpoint_class) or self.policies.get("default", (100, 600))
        capacity, per_min = policy
        refill_rate = per_min / 60.0
        now = time.time()
        key = f"{self.prefix}:{identifier}:{endpoint_class}"
        ttl = max(120, int(capacity / refill_rate * 2)) if refill_rate > 0 else 300

        try:
            script = self._get_script()
            res = script(
                keys=[key],
                args=[capacity, refill_rate, now, consume_tokens, ttl],
            )
            # res is [allowed (1/0), remaining_tokens, retry_after]
            allowed = bool(res[0])
            remaining = int(res[1])
            retry_after = int(res[2])
            return allowed, capacity, remaining, retry_after

        except Exception as exc:
            # Redis is unreachable or errored
            if self.failure_mode == "fail_closed_mutations":
                # Security-critical operations fail closed; read-only operations fail open
                if endpoint_class in ("auth", "workflow_mutate", "investigation"):
                    return False, capacity, 0, 60
                return True, capacity, capacity, 0
            elif self.failure_mode == "fail_open":
                return True, capacity, capacity, 0
            else:  # local_fallback
                return self.local_fallback.check_rate_limit(
                    identifier, endpoint_class, consume_tokens
                )
