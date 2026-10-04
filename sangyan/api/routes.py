"""REST API routes for authoritative verification, evidence retrieval, and findings."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from sangyan.correlation.orchestrator import InvestigationOrchestrator
from sangyan.core.errors import DomainValidationError, NotFoundError, PermissionDeniedError
from sangyan.domain.models import Claim, ContentItem
from sangyan.security.api_keys import generate_api_key
from sangyan.security.auth import enforce_tenant_boundary
from sangyan.security.models import ApiKey, Principal
from sangyan.security.telemetry import MetricsRegistry
from sangyan.verification.engine import ClaimVerificationEngine, InvestigationReport, VerificationOutcome
from sangyan.verification.sources import AuthoritativeSourceMetadata
from sangyan.workflow.errors import (
    CannotCancelCompletedInvestigationError,
    InvestigationCancelledError,
    ReviewConflictError,
    TenantMismatchError,
)
from sangyan.workflow.service import WorkflowService


class ClaimVerifyRequest(BaseModel):
    statement: str = Field(..., min_length=3, description="Assertion text to verify against authoritative registries")
    claim_type: str = Field(default="regulatory", description="regulatory, return, urgency, payment, affiliation, or other")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization ID")
    user_id: Optional[str] = Field(default=None, description="Authenticated user identifier")


class ContentVerifyRequest(BaseModel):
    raw_content: str = Field(..., min_length=1, description="Message body or URL content to analyze and verify")
    content_type: str = Field(default="text", description="text or url")
    source_url: Optional[str] = Field(default="", description="Target URL if content_type is url")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization ID")
    user_id: Optional[str] = Field(default=None, description="Authenticated user identifier")


class InvestigationBatchRequest(BaseModel):
    contents: list[str] = Field(..., min_length=1, description="List of messages, claims, or URLs in investigation chain")
    content_type: str = Field(default="text", description="text or url")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization ID")
    user_id: Optional[str] = Field(default=None, description="Authenticated user identifier")


class WorkflowStartRequest(BaseModel):
    contents: list[str] = Field(..., min_length=1, description="List of messages, claims, or URLs in investigation chain")
    content_type: str = Field(default="text/plain", description="Content type e.g. text/plain or url")
    organization_id: str = Field(..., description="Tenant organization ID")
    user_id: str = Field(..., description="Authenticated user identifier")
    require_review: bool = Field(default=False, description="Whether to require human review gate")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Optional metadata")


class WorkflowResumeRequest(BaseModel):
    action: str = Field(..., description="Review action: CONFIRM, DISMISS, ESCALATE, ANNOTATE")
    user_id: str = Field(..., description="Authenticated reviewer user ID")
    organization_id: str = Field(..., description="Tenant organization ID")
    reason: str = Field(default="", description="Review justification / notes")
    finding_id: Optional[str] = Field(default=None, description="Specific finding ID if applicable")


class WorkflowCancelRequest(BaseModel):
    user_id: str = Field(..., description="Authenticated user ID")
    organization_id: str = Field(..., description="Tenant organization ID")
    reason: str = Field(default="", description="Cancellation reason")


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Descriptive label for machine API key")
    role: str = Field(default="sangyan_analyst", description="Role to assign: sangyan_admin, sangyan_analyst, or sangyan_viewer")
    scopes: list[str] = Field(default_factory=list, description="Explicit granular scopes")
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365, description="Key validity in days")


def get_api_router(
    engine: ClaimVerificationEngine,
    repository_factory: Optional[Any] = None,
    orchestrator: Optional[InvestigationOrchestrator] = None,
    workflow_service: Optional[WorkflowService] = None,
    authenticator: Optional[Callable] = None,
    metrics_registry: Optional[MetricsRegistry] = None,
) -> APIRouter:
    """Build FastAPI router configured with verification engine, tenancy repository, and security boundary."""
    router = APIRouter(prefix="/api/v1", tags=["verification"])
    metrics = metrics_registry or MetricsRegistry.get_default()

    async def _auth(request: Request) -> Principal:
        if authenticator:
            return await authenticator(request)
        principal = getattr(request.state, "principal", None)
        if principal is not None:
            return principal
        # Development fallback
        org_id = request.query_params.get("organization_id", "default_org")
        usr_id = request.query_params.get("user_id", "default_usr")
        return Principal(
            principal_id=usr_id,
            organization_id=org_id,
            roles=("sangyan_analyst",),
            auth_method="development",
        )

    def _get_repo(org_id: Optional[str], usr_id: Optional[str]):
        if repository_factory and org_id and usr_id:
            try:
                return repository_factory(org_id, usr_id)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        return None

    # -----------------------------------------------------------------------
    # API Key Provisioning & Lifecycle (Admin Only)
    # -----------------------------------------------------------------------

    @router.post("/auth/api-keys", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
    def create_api_key(
        req: ApiKeyCreateRequest,
        principal: Principal = Depends(_auth),
    ):
        """Generate a new secure, hashed API key for automated tenant integrations (admin only)."""
        if not principal.has_permission("api_key:manage"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires api_key:manage permission")
        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")

        raw_key, api_key_model = generate_api_key(
            organization_id=principal.organization_id,
            user_id=principal.principal_id,
            name=req.name,
            role=req.role,
            scopes=req.scopes,
            expires_in_days=req.expires_in_days,
        )
        repo.save_api_key(api_key_model)
        metrics.security_events_total.labels(event_type="api_key_created", status="success").inc()
        return {
            "raw_api_key": raw_key,
            "api_key": api_key_model.to_dict(),
        }

    @router.get("/auth/api-keys", response_model=list[dict[str, Any]])
    def list_api_keys(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        principal: Principal = Depends(_auth),
    ):
        """List active and revoked API keys for calling tenant (admin only)."""
        if not principal.has_permission("api_key:manage"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires api_key:manage permission")
        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")
        keys = repo.list_api_keys(limit=limit, offset=offset)
        return [k.to_dict() for k in keys]

    @router.delete("/auth/api-keys/{key_id}", response_model=dict[str, Any])
    def revoke_api_key(
        key_id: str,
        principal: Principal = Depends(_auth),
    ):
        """Immediately revoke an API key for calling tenant (admin only)."""
        if not principal.has_permission("api_key:manage"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires api_key:manage permission")
        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")
        try:
            revoked_key = repo.revoke_api_key(key_id)
            metrics.security_events_total.labels(event_type="api_key_revoked", status="success").inc()
            return revoked_key.to_dict()
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # -----------------------------------------------------------------------
    # Verification & Ingestion Endpoints
    # -----------------------------------------------------------------------

    @router.post("/verify/claim", response_model=dict[str, Any])
    def verify_single_claim(
        req: ClaimVerifyRequest,
        principal: Principal = Depends(_auth),
    ):
        """Verify an isolated atomic assertion against authoritative institutional registries."""
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not principal.has_permission("investigation:create"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:create permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        content_item_id = "ad_hoc_claim"
        if repo:
            try:
                item = ContentItem(
                    organization_id=repo.organization_id,
                    content_type="text",
                    raw_content=req.statement,
                )
                content_item_id = repo.save_content_item(item)
            except Exception:
                pass

        claim = Claim(
            content_item_id=content_item_id,
            statement=req.statement,
            claim_type=req.claim_type,
        )
        if repo:
            try:
                repo.save_claim(claim)
            except Exception:
                pass

        outcome = engine.verify_claim(claim, repository=repo)
        return outcome.to_dict()

    @router.post("/verify/content", response_model=dict[str, Any])
    def verify_content(
        req: ContentVerifyRequest,
        principal: Principal = Depends(_auth),
    ):
        """End-to-end investigation pipeline: intelligence decomposition, multi-adapter verification, and trust receipts."""
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not principal.has_permission("investigation:create"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:create permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        org_id = principal.organization_id

        # Ingestion handling
        item = ContentItem(
            organization_id=org_id,
            content_type=req.content_type,
            raw_content=req.raw_content,
            source_url=req.source_url or "",
        )
        if repo:
            try:
                repo.save_content_item(item)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        report = engine.verify_content_item(item, repository=repo, user_id=principal.principal_id)
        return report.to_dict()

    @router.get("/investigations/{investigation_id}", response_model=dict[str, Any])
    def get_investigation(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve full investigation details including linked claims, entities, signals, and findings."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication and tenant context required")
        try:
            inv = repo.get_investigation(investigation_id)
            return inv.to_dict()
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
        except PermissionDeniedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    @router.get("/claims/{claim_id}", response_model=dict[str, Any])
    def get_claim(
        claim_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Fetch individual claim by ID."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        try:
            c = repo.get_claim(claim_id)
            return c.to_dict()
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    @router.get("/claims/{claim_id}/evidence", response_model=list[dict[str, Any]])
    def list_claim_evidence(
        claim_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """List all authoritative evidence items retrieved for a claim."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        try:
            evidence_items = repo.list_evidence_for_claim(claim_id)
            return [e.to_dict() for e in evidence_items]
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    @router.get("/claims/{claim_id}/findings", response_model=list[dict[str, Any]])
    def list_claim_findings(
        claim_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """List all synthesized verification findings for a claim."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        try:
            findings = repo.list_findings_for_claim(claim_id)
            return [f.to_dict() for f in findings]
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    @router.get("/sources", response_model=list[dict[str, Any]])
    def list_authoritative_sources(
        claim_type: Optional[str] = None,
        authority_tier: Optional[str] = None,
        authority: Optional[str] = None,
    ):
        """List all controlled authoritative institutional sources registered in SANGYAN (public metadata)."""
        sources = engine.registry.list_sources(
            claim_type=claim_type,
            authority_tier=authority_tier,
            authority=authority,
        )
        return [
            {
                "source_id": s.source_id,
                "name": s.name,
                "authority_tier": s.authority_tier,
                "source_type": s.source_type,
                "authority": s.authority,
                "provenance_policy": s.provenance_policy,
                "base_url": s.base_url,
                "allowed_domains": s.allowed_domains,
                "supported_claim_types": s.supported_claim_types,
                "retrieval_method": s.retrieval_method,
                "mode": s.mode,
                "version": s.version,
                "enabled": s.enabled,
                "description": s.description,
            }
            for s in sources
        ]

    @router.get("/audit/events", response_model=list[dict[str, Any]])
    def list_audit_events(
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        action: Optional[str] = None,
        limit: int = 100,
        principal: Principal = Depends(_auth),
    ):
        """Query tamper-evident audit ledger events for the active tenant."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        events = repo.list_audit_events(limit=limit, action=action)
        return [e.to_dict() for e in events]

    @router.post("/investigate", response_model=dict[str, Any])
    def run_investigation(
        req: InvestigationBatchRequest,
        principal: Principal = Depends(_auth),
    ):
        """Execute full Phase 4 investigation pipeline across single or multi-content inputs."""
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not principal.has_permission("investigation:create"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:create permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        org_id = principal.organization_id
        usr_id = principal.principal_id

        items: list[ContentItem] = []
        for text in req.contents:
            item = ContentItem(
                organization_id=org_id,
                content_type=req.content_type,
                raw_content=text,
            )
            if repo:
                try:
                    repo.save_content_item(item)
                except Exception:
                    pass
            items.append(item)

        orch = orchestrator or InvestigationOrchestrator(verification_engine=engine)
        report = orch.investigate(items, repository=repo, user_id=usr_id)
        return report.to_dict()

    @router.get("/investigations/{investigation_id}/correlations", response_model=list[dict[str, Any]])
    def get_investigation_correlations(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve graph correlation edges for an investigation."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        corrs = repo.list_correlations_for_investigation(investigation_id)
        return [c.to_dict() for c in corrs]

    @router.get("/investigations/{investigation_id}/scam_chain", response_model=list[dict[str, Any]])
    def get_investigation_scam_chain(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve reconstructed scam chain stages for an investigation."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        stages = repo.list_scam_chain_stages(investigation_id)
        return [s.to_dict() for s in stages]

    @router.get("/investigations/{investigation_id}/guidance", response_model=list[dict[str, Any]])
    def get_investigation_guidance(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve safe non-investment action guidance for an investigation."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        try:
            inv = repo.get_investigation(investigation_id)
            guidance_items = [repo.get_guidance(gid) for gid in inv.guidance_ids]
            return [g.to_dict() for g in guidance_items]
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    @router.get("/investigations/{investigation_id}/grievance", response_model=Optional[dict[str, Any]])
    def get_investigation_grievance(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve grievance classification and official resolution pathway for an investigation."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        record = repo.get_grievance_record(investigation_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance record not found")
        return record.to_dict()

    # -----------------------------------------------------------------------
    # LangGraph Workflow Endpoints
    # -----------------------------------------------------------------------

    @router.post("/workflow/start", response_model=dict[str, Any])
    def start_workflow_investigation(
        req: WorkflowStartRequest,
        principal: Principal = Depends(_auth),
    ):
        """Initiate durable LangGraph investigation workflow across multiple content items."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not principal.has_permission("investigation:create"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:create permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        items = [
            ContentItem(
                organization_id=principal.organization_id,
                content_type=req.content_type,
                raw_content=c,
            )
            for c in req.contents
        ]
        try:
            state = workflow_service.start_investigation(
                content_items=items,
                user_id=principal.principal_id,
                organization_id=principal.organization_id,
                require_review=req.require_review,
                metadata=req.metadata,
            )
            return state
        except PermissionDeniedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except DomainValidationError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    @router.post("/workflow/{investigation_id}/resume", response_model=dict[str, Any])
    def resume_workflow_investigation(
        investigation_id: str,
        req: WorkflowResumeRequest,
        principal: Principal = Depends(_auth),
    ):
        """Resume an investigation paused at review_gate_node with an authorized supervisory decision."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not principal.has_permission("investigation:review"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:review permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            state = workflow_service.resume_investigation(
                investigation_id=investigation_id,
                review_action=req.action,
                user_id=principal.principal_id,
                organization_id=principal.organization_id,
                reason=req.reason,
                finding_id=req.finding_id,
            )
            return state
        except ReviewConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except InvestigationCancelledError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except (PermissionDeniedError, TenantMismatchError) as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    @router.post("/workflow/{investigation_id}/cancel", response_model=dict[str, Any])
    def cancel_workflow_investigation(
        investigation_id: str,
        req: WorkflowCancelRequest,
        principal: Principal = Depends(_auth),
    ):
        """Cancel an in-flight or awaiting-review workflow investigation while preserving evidence."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        if req.organization_id:
            enforce_tenant_boundary(principal, req.organization_id, metrics)
        if not (principal.has_permission("investigation:create") or principal.has_permission("tenant:manage")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires investigation:create or tenant:manage permission",
            )

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            inv = workflow_service.cancel_investigation(
                investigation_id=investigation_id,
                user_id=principal.principal_id,
                organization_id=principal.organization_id,
                reason=req.reason,
            )
            return inv.to_dict()
        except CannotCancelCompletedInvestigationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except (PermissionDeniedError, TenantMismatchError) as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    @router.get("/workflow/{investigation_id}/state", response_model=dict[str, Any])
    def get_workflow_investigation_state(
        investigation_id: str,
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        principal: Principal = Depends(_auth),
    ):
        """Retrieve current durable checkpoint snapshot state for an investigation."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        try:
            state = workflow_service.get_workflow_state(
                investigation_id, principal.organization_id, user_id=principal.principal_id
            )
            if not state:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow state not found")
            return state
        except PermissionDeniedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    @router.get("/workflow/runs", response_model=list[dict[str, Any]])
    def list_workflow_runs(
        organization_id: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        status_filter: Optional[str] = Query(None, alias="status"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        principal: Principal = Depends(_auth),
    ):
        """List historical workflow execution runs for tenant."""
        if organization_id:
            enforce_tenant_boundary(principal, organization_id, metrics)
        if not principal.has_permission("investigation:read"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires investigation:read permission")

        repo = _get_repo(principal.organization_id, principal.principal_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        runs = repo.list_workflow_runs(limit=limit, offset=offset, status=status_filter)
        return [r.to_dict() for r in runs]

    return router
