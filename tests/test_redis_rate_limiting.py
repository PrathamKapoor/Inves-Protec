"""Tests for Redis-backed distributed rate limiting and failed-authentication throttling."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from sangyan.security.redis_limiter import RedisFailedAuthTracker, RedisRateLimiter


class MockRedisScript:
    def __init__(self):
        self.buckets = {}

    def __call__(self, keys, args):
        key = keys[0]
        capacity = float(args[0])
        refill_rate = float(args[1])
        now = float(args[2])
        requested = float(args[3])
        ttl = int(args[4])

        if key not in self.buckets:
            tokens = capacity
            last_refill = now
        else:
            tokens, last_refill = self.buckets[key]
            elapsed = max(0.0, now - last_refill)
            tokens = min(capacity, tokens + elapsed * refill_rate)
            last_refill = now

        if tokens >= requested:
            tokens -= requested
            self.buckets[key] = (tokens, last_refill)
            return [1, int(tokens), 0]
        else:
            deficit = requested - tokens
            retry_after = int(deficit / refill_rate) if refill_rate > 0 else 60
            self.buckets[key] = (tokens, last_refill)
            return [0, int(tokens), max(1, retry_after)]


class MockRedisPipeline:
    def __init__(self, parent):
        self.parent = parent
        self.ops = []

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def zremrangebyscore(self, key, min_s, max_s):
        self.ops.append(("zrem", key, min_s, max_s))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zrange(self, key, start, stop, withscores=False):
        self.ops.append(("zrange", key, start, stop, withscores))
        return self

    def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "zrem":
                key, min_s, max_s = op[1], op[2], op[3]
                items = self.parent.zsets.get(key, [])
                self.parent.zsets[key] = [(m, s) for (m, s) in items if not (min_s <= s <= max_s)]
                results.append(1)
            elif op[0] == "zcard":
                key = op[1]
                count = len(self.parent.zsets.get(key, []))
                results.append(count)
            elif op[0] == "zrange":
                key, withscores = op[1], op[4]
                items = self.parent.zsets.get(key, [])
                if items and withscores:
                    results.append([items[0]])
                else:
                    results.append([])
            elif op[0] == "zadd":
                key, mapping = op[1], op[2]
                if key not in self.parent.zsets:
                    self.parent.zsets[key] = []
                for m, s in mapping.items():
                    self.parent.zsets[key].append((m, s))
                results.append(1)
            else:
                results.append(1)
        return results


class MockRedisClient:
    def __init__(self):
        self.mock_script = MockRedisScript()
        self.zsets = {}

    def register_script(self, script_text):
        return self.mock_script

    def pipeline(self):
        return MockRedisPipeline(self)

    def delete(self, key):
        self.zsets.pop(key, None)

    def ping(self):
        return True


def test_redis_rate_limiter_token_consumption_and_exhaustion():
    redis_client = MockRedisClient()
    policies = {"investigation": (5, 60)}  # 5 capacity, 60 per minute
    limiter = RedisRateLimiter(redis_client=redis_client, policies=policies)

    # Consume 5 tokens
    for i in range(5):
        allowed, cap, rem, retry_after = limiter.check_rate_limit(
            identifier="test_user",
            endpoint_class="investigation",
            consume_tokens=1.0,
        )
        assert allowed is True
        assert cap == 5
        assert rem == 4 - i
        assert retry_after == 0

    # 6th request must be rejected
    allowed, cap, rem, retry_after = limiter.check_rate_limit(
        identifier="test_user",
        endpoint_class="investigation",
        consume_tokens=1.0,
    )
    assert allowed is False
    assert cap == 5
    assert rem == 0
    assert retry_after > 0


def test_redis_rate_limiter_distributed_shared_exhaustion():
    """Verify that multiple API replicas consuming against the same key share the quota."""
    redis_client = MockRedisClient()
    policies = {"workflow_mutate": (10, 60)}

    # Pod A and Pod B both instantiate a limiter pointing to the shared Redis
    pod_a_limiter = RedisRateLimiter(redis_client=redis_client, policies=policies)
    pod_b_limiter = RedisRateLimiter(redis_client=redis_client, policies=policies)

    # Pod A executes 5 mutations
    for _ in range(5):
        allowed, _, _, _ = pod_a_limiter.check_rate_limit("shared_tenant_id", "workflow_mutate")
        assert allowed is True

    # Pod B executes 5 mutations
    for _ in range(5):
        allowed, _, _, _ = pod_b_limiter.check_rate_limit("shared_tenant_id", "workflow_mutate")
        assert allowed is True

    # Total 10 consumed. Now Pod A and Pod B must both be rejected!
    allowed_a, _, _, _ = pod_a_limiter.check_rate_limit("shared_tenant_id", "workflow_mutate")
    assert allowed_a is False

    allowed_b, _, _, _ = pod_b_limiter.check_rate_limit("shared_tenant_id", "workflow_mutate")
    assert allowed_b is False


def test_redis_failed_auth_lockout_and_reset():
    redis_client = MockRedisClient()
    tracker = RedisFailedAuthTracker(redis_client=redis_client, failure_threshold=3, window_seconds=60.0)

    client_ip = "192.168.1.100"
    assert tracker.is_throttled(client_ip)[0] is False

    tracker.record_failure(client_ip)
    tracker.record_failure(client_ip)
    assert tracker.is_throttled(client_ip)[0] is False

    # 3rd failure locks out client
    tracker.record_failure(client_ip)
    is_throttled, retry_after = tracker.is_throttled(client_ip)
    assert is_throttled is True
    assert retry_after > 0

    # Successful authentication resets the counter
    tracker.record_success(client_ip)
    assert tracker.is_throttled(client_ip)[0] is False


def test_redis_failure_mode_fail_closed_mutations():
    # Simulate broken Redis
    broken_redis = MagicMock()
    broken_redis.register_script.side_effect = RuntimeError("Redis connection lost")

    limiter = RedisRateLimiter(
        redis_client=broken_redis,
        failure_mode="fail_closed_mutations",
    )

    # Mutation should fail closed
    allowed, _, _, _ = limiter.check_rate_limit("user1", endpoint_class="workflow_mutate")
    assert allowed is False

    # Investigation should fail closed
    allowed, _, _, _ = limiter.check_rate_limit("user1", endpoint_class="investigation")
    assert allowed is False

    # Read-only operation should fail open
    allowed, _, _, _ = limiter.check_rate_limit("user1", endpoint_class="read")
    assert allowed is True


def test_redis_failure_mode_local_fallback():
    broken_redis = MagicMock()
    broken_redis.register_script.side_effect = RuntimeError("Redis connection lost")

    limiter = RedisRateLimiter(
        redis_client=broken_redis,
        failure_mode="local_fallback",
    )

    # Local fallback handles the request in process memory
    allowed, cap, rem, _ = limiter.check_rate_limit("user_fallback", endpoint_class="read")
    assert allowed is True
    assert rem < cap
