"""OpenTelemetry distributed tracing with privacy guardrails and context propagation."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from sangyan.security.telemetry import normalize_route, redact_sensitive_text

logger = logging.getLogger("sangyan.tracing")

# Forbidden attribute keys that must never be set on spans to protect investor privacy
FORBIDDEN_SPAN_ATTRS = frozenset(
    [
        "content",
        "raw_content",
        "claim",
        "claim_text",
        "evidence",
        "evidence_excerpt",
        "url",
        "token",
        "authorization",
        "api_key",
        "password",
        "phone",
        "upi",
        "email",
        "secret",
        "jwt",
    ]
)


def sanitize_span_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Scrub sensitive credentials and forbid PII / raw content attributes from spans."""
    clean: dict[str, Any] = {}
    for key, val in attributes.items():
        k_lower = key.lower()
        # Reject forbidden keys
        if any(f in k_lower for f in FORBIDDEN_SPAN_ATTRS):
            continue

        if isinstance(val, (str, bytes)):
            clean[key] = redact_sensitive_text(str(val))
        elif isinstance(val, (int, float, bool)):
            clean[key] = val
        else:
            clean[key] = redact_sensitive_text(str(val))
    return clean


class NoOpSpan:
    """Fallback no-op span when OpenTelemetry is disabled or unavailable."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: Optional[str] = None) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class NoOpTracer:
    """Fallback no-op tracer."""

    @contextmanager
    def start_as_current_span(self, name: str, attributes: Optional[dict] = None) -> Iterator[NoOpSpan]:
        yield NoOpSpan()


_TRACER: Optional[Any] = None


def setup_tracer(
    service_name: str = "sangyan-api",
    sample_rate: float = 1.0,
    exporter_endpoint: Optional[str] = None,
) -> Any:
    """Initialize OpenTelemetry TracerProvider with trace sampling and optional OTLP exporter."""
    global _TRACER
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        resource = Resource.create({"service.name": service_name, "service.version": "0.8.0"})
        sampler = ParentBased(TraceIdRatioBased(max(0.0, min(1.0, sample_rate))))
        provider = TracerProvider(resource=resource, sampler=sampler)

        if exporter_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception as exc:
                logger.warning("Failed to initialize OTLP exporter at %s: %s", exporter_endpoint, exc)

        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer("sangyan", "0.8.0")
        return _TRACER
    except Exception as exc:
        logger.info("OpenTelemetry SDK setup deferred or failed: %s; using NoOpTracer", exc)
        _TRACER = NoOpTracer()
        return _TRACER


def get_tracer() -> Any:
    """Return active tracer or initialize default NoOpTracer."""
    global _TRACER
    if _TRACER is None:
        _TRACER = setup_tracer()
    return _TRACER


@contextmanager
def trace_span(name: str, attributes: Optional[dict[str, Any]] = None) -> Iterator[Any]:
    """Context manager starting a sanitized, privacy-safe span."""
    tracer = get_tracer()
    clean_attrs = sanitize_span_attributes(attributes or {})
    with tracer.start_as_current_span(name, attributes=clean_attrs) as span:
        yield span


class TracingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware injecting trace correlation and creating root HTTP spans."""

    def __init__(self, app, tracer: Optional[Any] = None) -> None:
        super().__init__(app)
        self.tracer = tracer or get_tracer()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract X-Request-ID from request headers or state
        req_id = request.headers.get("x-request-id", getattr(request.state, "request_id", "unknown"))
        route = normalize_route(request.url.path)
        method = request.method

        attrs = {
            "http.method": method,
            "http.route": route,
            "sangyan.request_id": req_id,
        }

        with trace_span(f"HTTP {method} {route}", attributes=attrs) as span:
            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("http.status_code", 500)
                raise
