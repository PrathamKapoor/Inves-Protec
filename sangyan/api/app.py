"""FastAPI Application Factory for SANGYAN Authoritative Verification, Security & Evidence API."""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sangyan.api.routes import get_api_router
from sangyan.api.views import get_views_router
from sangyan.correlation.orchestrator import InvestigationOrchestrator
from sangyan.database.engine import DatabaseEngine, SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.security.auth import Authenticator
from sangyan.security.middleware import (
    MAX_REQUEST_BODY_BYTES,
    CorrelationIdMiddleware,
    RateLimiterMiddleware,
    RequestSizeLimiterMiddleware,
    SecurityHeadersMiddleware,
)
from sangyan.security.models import SecurityConfig
from sangyan.security.rate_limiter import TokenBucketRateLimiter
from sangyan.security.telemetry import MetricsRegistry, PrometheusMetricsMiddleware
from sangyan.tenancy.repository import TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.cache import RateLimiter, VerificationCache
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.snapshots import SnapshotManager
from sangyan.verification.sources import AuthoritativeSourceRegistry
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


def create_app(
    engine: Optional[DatabaseEngine] = None,
    trust_service: Optional[TrustService] = None,
    source_registry: Optional[AuthoritativeSourceRegistry] = None,
    snapshot_manager: Optional[SnapshotManager] = None,
    verification_engine: Optional[ClaimVerificationEngine] = None,
    orchestrator: Optional[InvestigationOrchestrator] = None,
    workflow_service: Optional[WorkflowService] = None,
    security_config: Optional[SecurityConfig] = None,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
    metrics_registry: Optional[MetricsRegistry] = None,
    require_auth: bool = False,
) -> FastAPI:
    """Create and configure a production-ready SANGYAN FastAPI application instance with security controls."""
    app = FastAPI(
        title="SANGYAN Authoritative Verification API",
        description="Public-good investor safety platform: authoritative claim verification, evidence provenance, post-quantum trust receipts, and security hardening.",
        version="0.6.0",
    )

    sec_config = security_config or SecurityConfig()
    metrics = metrics_registry or MetricsRegistry.get_default()
    limiter = rate_limiter or TokenBucketRateLimiter()

    # 1. Telemetry middleware (low-cardinality Prometheus collector)
    app.add_middleware(PrometheusMetricsMiddleware, metrics_registry=metrics)

    # 2. Rate limiter middleware (token-bucket + failed-auth throttle)
    app.add_middleware(RateLimiterMiddleware, rate_limiter=limiter, enabled=sec_config.rate_limit_enabled)

    # 3. Request body size bounding (2 MB limit)
    app.add_middleware(RequestSizeLimiterMiddleware, max_body_bytes=sec_config.max_request_body_bytes)

    # 4. Defensive HTTP security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 5. Distributed trace correlation
    app.add_middleware(CorrelationIdMiddleware)

    # 6. Hardened CORS configuration
    allow_credentials = False if sec_config.allowed_origins == ["*"] else True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sec_config.allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    db_engine = engine or SQLiteDatabaseEngine(":memory:")
    # Ensure database migrations are executed up to Migration 004
    MigrationRunner(db_engine).migrate()

    t_service = trust_service or TrustService(db_engine)
    src_reg = source_registry or AuthoritativeSourceRegistry()
    snap_mgr = snapshot_manager or SnapshotManager()
    trust_binding = TrustBindingService(t_service)

    verif_engine = verification_engine or ClaimVerificationEngine(
        source_registry=src_reg,
        snapshot_manager=snap_mgr,
        trust_binding=trust_binding,
        cache=VerificationCache(),
        rate_limiter=RateLimiter(),
    )

    orch = orchestrator or InvestigationOrchestrator(
        verification_engine=verif_engine,
        trust_binding=trust_binding,
    )

    def repository_factory(org_id: str, usr_id: str) -> TenantRepository:
        return TenantRepository(db_engine, organization_id=org_id, user_id=usr_id)

    node_suite = WorkflowNodeSuite(
        verification_engine=verif_engine,
        trust_binding=trust_binding,
        repository_factory=lambda oid, user_id=None: TenantRepository(db_engine, organization_id=oid, user_id=user_id or "system"),
    )
    wf_service = workflow_service or WorkflowService(
        repository_factory=lambda oid, user_id=None: TenantRepository(db_engine, organization_id=oid, user_id=user_id or "system"),
        node_suite=node_suite,
    )

    # Setup Gateway Authenticator
    authenticator = Authenticator(
        engine=db_engine,
        config=sec_config,
        rate_limiter=limiter,
        metrics_registry=metrics,
        require_auth=require_auth,
    )

    # Mount REST API and Inspection HTML views
    api_router = get_api_router(
        verif_engine,
        repository_factory,
        orch,
        wf_service,
        authenticator=authenticator,
        metrics_registry=metrics,
    )
    views_router = get_views_router(repository_factory, t_service)

    app.include_router(api_router)
    app.include_router(views_router)

    @app.get("/health", tags=["system"])
    def health_check():
        return {
            "status": "healthy",
            "service": "sangyan-verification-engine",
            "version": "0.6.0",
            "sources_registered": len(src_reg.list_sources()),
        }

    @app.get("/metrics", tags=["system"])
    def prometheus_metrics():
        return metrics.export_metrics()

    return app
