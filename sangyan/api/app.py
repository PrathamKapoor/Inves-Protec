"""FastAPI Application Factory for SANGYAN Authoritative Verification & Evidence API."""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sangyan.api.routes import get_api_router
from sangyan.api.views import get_views_router
from sangyan.correlation.orchestrator import InvestigationOrchestrator
from sangyan.database.engine import DatabaseEngine, SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.tenancy.repository import TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.cache import RateLimiter, VerificationCache
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.snapshots import SnapshotManager
from sangyan.verification.sources import AuthoritativeSourceRegistry
from sangyan.verification.trust_binding import TrustBindingService


def create_app(
    engine: Optional[DatabaseEngine] = None,
    trust_service: Optional[TrustService] = None,
    source_registry: Optional[AuthoritativeSourceRegistry] = None,
    snapshot_manager: Optional[SnapshotManager] = None,
    verification_engine: Optional[ClaimVerificationEngine] = None,
    orchestrator: Optional[InvestigationOrchestrator] = None,
) -> FastAPI:
    """Create and configure a production-ready SANGYAN FastAPI application instance."""
    app = FastAPI(
        title="SANGYAN Authoritative Verification API",
        description="Public-good investor safety platform: authoritative claim verification, evidence provenance, and ML-DSA-65 post-quantum trust receipts.",
        version="0.4.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_engine = engine or SQLiteDatabaseEngine(":memory:")
    # Ensure database migrations are executed
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

    # Mount REST API and Inspection HTML views
    api_router = get_api_router(verif_engine, repository_factory, orch)
    views_router = get_views_router(repository_factory, t_service)

    app.include_router(api_router)
    app.include_router(views_router)

    @app.get("/health", tags=["system"])
    def health_check():
        return {
            "status": "healthy",
            "service": "sangyan-verification-engine",
            "version": "0.4.0",
            "sources_registered": len(src_reg.list_sources()),
        }

    return app
