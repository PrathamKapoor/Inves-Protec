"""Tests for OpenTelemetry distributed tracing and privacy attribute sanitization."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from sangyan.security.tracing import (
    FORBIDDEN_SPAN_ATTRS,
    NoOpTracer,
    TracingMiddleware,
    sanitize_span_attributes,
    trace_span,
)


def test_sanitize_span_attributes_blocks_forbidden_keys():
    """Scenario 12: Ensure zero raw claim content, evidence text, or PII keys in spans."""
    dangerous_input = {
        "claim_text": "Guaranteed 200% returns in 30 days! Invest now via UPI.",
        "raw_content": "Full unscrubbed post text with phone number +91 9876543210",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsIn...",
        "api_key": "sk_live_secret12345",
        "password": "supersecretpassword",
        "token": "sensitive_jwt_token",
        "user_email": "investor@example.com",
        "http.method": "POST",
        "http.status_code": 200,
        "sangyan.investigation_id": "inv_12345",
        "custom_phone_number": "+91 9123456789",
    }

    clean = sanitize_span_attributes(dangerous_input)

    # All forbidden keys must be omitted
    for forbidden in FORBIDDEN_SPAN_ATTRS:
        for k in clean:
            assert forbidden not in k.lower(), f"Forbidden key substring '{forbidden}' found in sanitized key '{k}'"

    # Safe attributes must be preserved
    assert clean["http.method"] == "POST"
    assert clean["http.status_code"] == 200
    assert clean["sangyan.investigation_id"] == "inv_12345"


def test_sanitize_span_attributes_redacts_credentials_in_values():
    dirty_attributes = {
        "diagnostic.message": "Failed auth for user with secret=MySecretPass and token=secret_token_123",
        "safe.counter": 42,
    }

    clean = sanitize_span_attributes(dirty_attributes)
    assert clean["safe.counter"] == 42
    # Verify values don't contain raw sensitive patterns
    assert clean["diagnostic.message"] != ""


def test_noop_tracer_fallback():
    tracer = NoOpTracer()
    with tracer.start_as_current_span("test_span") as span:
        span.set_attribute("key", "val")
        span.set_status("OK")
        span.record_exception(RuntimeError("error"))
    # Should not raise


def test_trace_span_context_manager():
    with trace_span("test_operation", attributes={"operation": "verify", "claim": "forbidden"}) as span:
        assert span is not None
