"""FastAPI Application Factory for SANGYAN Authoritative Verification, Security & Evidence API."""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from sangyan.api.routes import get_api_router
from sangyan.api.views import get_views_router
from sangyan.config import SangyanConfig, load_config, validate_production_config
from sangyan.core.logging import get_logger
from sangyan.correlation.orchestrator import InvestigationOrchestrator
from sangyan.database.engine import DatabaseEngine, SQLiteDatabaseEngine, create_engine
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
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService

logger = get_logger("sangyan.api")


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
    config: Optional[SangyanConfig] = None,
) -> FastAPI:
    """Create and configure a production-ready SANGYAN FastAPI application instance with security controls."""
    # 0. Load & validate configuration
    app_config = config or load_config()
    validate_production_config(app_config)

    # Effective require_auth: if either explicitly passed as True, or configured as True, enforce it
    effective_require_auth = require_auth or app_config.require_auth

    sec_config = security_config or app_config.to_security_config()
    metrics = metrics_registry or MetricsRegistry.get_default()
    limiter = rate_limiter or TokenBucketRateLimiter()

    # Database Engine initialization
    if engine is not None:
        db_engine = engine
    elif app_config.database_url:
        db_engine = create_engine(app_config.database_url)
    else:
        db_engine = SQLiteDatabaseEngine(":memory:")

    # Execute auto-migrations if configured
    if app_config.auto_migrate:
        MigrationRunner(db_engine).migrate()

    t_service = trust_service or TrustService(db_engine, key_dir=app_config.key_dir)
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

    # Durable checkpointer setup
    wf_checkpointer: Optional[WorkflowCheckpointer] = None
    if workflow_service is not None:
        wf_service = workflow_service
    else:
        if app_config.checkpoint_db_path:
            wf_checkpointer = WorkflowCheckpointer(db_path=app_config.checkpoint_db_path)
        else:
            wf_checkpointer = WorkflowCheckpointer(in_memory=True)

        wf_service = WorkflowService(
            repository_factory=lambda oid, user_id=None: TenantRepository(db_engine, organization_id=oid, user_id=user_id or "system"),
            node_suite=node_suite,
            checkpointer=wf_checkpointer,
        )

    # Setup Gateway Authenticator
    authenticator = Authenticator(
        engine=db_engine,
        config=sec_config,
        rate_limiter=limiter,
        metrics_registry=metrics,
        require_auth=effective_require_auth,
    )

    start_time = time.time()

    # Lifespan context manager for orderly startup and shutdown
    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        logger.info(
            "SANGYAN API starting up in environment=%s (host=%s, port=%d)",
            app_config.env,
            app_config.host,
            app_config.port,
        )
        yield
        logger.info("SANGYAN API shutting down; releasing database and checkpointer resources...")
        try:
            db_engine.close()
        except Exception as e:
            logger.warning("Error closing database engine on shutdown: %s", e)
        if wf_checkpointer is not None:
            try:
                wf_checkpointer.close()
            except Exception as e:
                logger.warning("Error closing workflow checkpointer on shutdown: %s", e)
        logger.info("SANGYAN API graceful shutdown complete.")

    app = FastAPI(
        title="SANGYAN Authoritative Verification API",
        description="Public-good investor safety platform: authoritative claim verification, evidence provenance, post-quantum trust receipts, and security hardening.",
        version="0.7.0",
        lifespan=lifespan,
    )

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

    # -----------------------------------------------------------------------
    # Operational Health Probes
    # -----------------------------------------------------------------------

    @app.get("/health/live", tags=["system"])
    def liveness_probe():
        """Liveness probe: verifies process event loop is active and accepting connections."""
        return {
            "status": "live",
            "uptime_seconds": round(time.time() - start_time, 2),
        }

    @app.get("/health/ready", tags=["system"])
    def readiness_probe():
        """Readiness probe: verifies database connectivity, schema migrations, and engine readiness."""
        try:
            # Query database
            db_engine.connect()
            row = db_engine.query_one("SELECT 1 AS ready")
            if not row:
                return Response(
                    content=json.dumps({"status": "not_ready", "reason": "database_query_empty"}),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    media_type="application/json",
                )

            # Check migrations
            runner = MigrationRunner(db_engine)
            if not runner.is_up_to_date():
                return Response(
                    content=json.dumps({"status": "not_ready", "reason": "pending_migrations"}),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    media_type="application/json",
                )

            return {
                "status": "ready",
                "database": "connected",
                "migrations": "current",
            }
        except Exception as exc:
            return Response(
                content=json.dumps({"status": "not_ready", "reason": "database_unavailable"}),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

    @app.get("/health", tags=["system"])
    def health_check():
        """Aggregated system health summary (backward-compatible with Phase 3-6 tests)."""
        is_ready = True
        try:
            db_engine.query_one("SELECT 1")
        except Exception:
            is_ready = False

        return {
            "status": "healthy" if is_ready else "degraded",
            "service": "sangyan-verification-engine",
            "version": "0.7.0",
            "sources_registered": len(src_reg.list_sources()),
            "live": True,
            "ready": is_ready,
        }

    @app.get("/metrics", tags=["system"])
    def prometheus_metrics():
        return metrics.export_metrics()

    return app


# Default module-level application instance for uvicorn runner
app = create_app()
