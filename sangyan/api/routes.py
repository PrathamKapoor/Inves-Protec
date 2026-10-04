"""REST API routes for authoritative verification, evidence retrieval, and findings."""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from sangyan.correlation.orchestrator import InvestigationOrchestrator
from sangyan.core.errors import DomainValidationError, NotFoundError, PermissionDeniedError
from sangyan.domain.models import Claim, ContentItem
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


def get_api_router(
    engine: ClaimVerificationEngine,
    repository_factory: Optional[Any] = None,
    orchestrator: Optional[InvestigationOrchestrator] = None,
    workflow_service: Optional[WorkflowService] = None,
) -> APIRouter:
    """Build FastAPI router configured with verification engine and tenancy repository."""
    router = APIRouter(prefix="/api/v1", tags=["verification"])

    def _get_repo(org_id: Optional[str], usr_id: Optional[str]):
        if repository_factory and org_id and usr_id:
            try:
                return repository_factory(org_id, usr_id)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        return None

    @router.post("/verify/claim", response_model=dict[str, Any])
    def verify_single_claim(req: ClaimVerifyRequest):
        """Verify an isolated atomic assertion against authoritative institutional registries."""
        repo = _get_repo(req.organization_id, req.user_id)
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
    def verify_content(req: ContentVerifyRequest):
        """End-to-end investigation pipeline: intelligence decomposition, multi-adapter verification, and trust receipts."""
        repo = _get_repo(req.organization_id, req.user_id)
        org_id = repo.organization_id if repo else (req.organization_id or "default_org")

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

        report = engine.verify_content_item(item, repository=repo, user_id=req.user_id)
        return report.to_dict()

    @router.get("/investigations/{investigation_id}", response_model=dict[str, Any])
    def get_investigation(
        investigation_id: str,
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve full investigation details including linked claims, entities, signals, and findings."""
        repo = _get_repo(organization_id, user_id)
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Fetch individual claim by ID."""
        repo = _get_repo(organization_id, user_id)
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """List all authoritative evidence items retrieved for a claim."""
        repo = _get_repo(organization_id, user_id)
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """List all synthesized verification findings for a claim."""
        repo = _get_repo(organization_id, user_id)
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
        """List all controlled authoritative institutional sources registered in SANGYAN."""
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
        action: Optional[str] = None,
        limit: int = 100,
    ):
        """Query tamper-evident audit ledger events for the active tenant."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        events = repo.list_audit_events(limit=limit, action=action)
        return [e.to_dict() for e in events]

    @router.post("/investigate", response_model=dict[str, Any])
    def run_investigation(req: InvestigationBatchRequest):
        """Execute full Phase 4 investigation pipeline across single or multi-content inputs."""
        repo = _get_repo(req.organization_id, req.user_id)
        org_id = repo.organization_id if repo else (req.organization_id or "default_org")
        usr_id = repo.user_id if repo else (req.user_id or "usr_analyst")

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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve graph correlation edges for an investigation."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        corrs = repo.list_correlations_for_investigation(investigation_id)
        return [c.to_dict() for c in corrs]

    @router.get("/investigations/{investigation_id}/scam_chain", response_model=list[dict[str, Any]])
    def get_investigation_scam_chain(
        investigation_id: str,
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve reconstructed scam chain stages for an investigation."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
        stages = repo.list_scam_chain_stages(investigation_id)
        return [s.to_dict() for s in stages]

    @router.get("/investigations/{investigation_id}/guidance", response_model=list[dict[str, Any]])
    def get_investigation_guidance(
        investigation_id: str,
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve safe non-investment action guidance for an investigation."""
        repo = _get_repo(organization_id, user_id)
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve grievance classification and official resolution pathway for an investigation."""
        repo = _get_repo(organization_id, user_id)
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
    def start_workflow_investigation(req: WorkflowStartRequest):
        """Initiate durable LangGraph investigation workflow across multiple content items."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        repo = _get_repo(req.organization_id, req.user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        items = [
            ContentItem(
                organization_id=req.organization_id,
                content_type=req.content_type,
                raw_content=c,
            )
            for c in req.contents
        ]
        try:
            state = workflow_service.start_investigation(
                content_items=items,
                user_id=req.user_id,
                organization_id=req.organization_id,
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
    def resume_workflow_investigation(investigation_id: str, req: WorkflowResumeRequest):
        """Resume an investigation paused at review_gate_node with an authorized supervisory decision."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        repo = _get_repo(req.organization_id, req.user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            state = workflow_service.resume_investigation(
                investigation_id=investigation_id,
                review_action=req.action,
                user_id=req.user_id,
                organization_id=req.organization_id,
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
    def cancel_workflow_investigation(investigation_id: str, req: WorkflowCancelRequest):
        """Cancel an in-flight or awaiting-review workflow investigation while preserving evidence."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        repo = _get_repo(req.organization_id, req.user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            inv = workflow_service.cancel_investigation(
                investigation_id=investigation_id,
                user_id=req.user_id,
                organization_id=req.organization_id,
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
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Retrieve current durable checkpoint snapshot state for an investigation."""
        if not workflow_service:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow service not configured")
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            state = workflow_service.get_workflow_state(investigation_id, organization_id, user_id=user_id)
            if not state:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow state not found")
            return state
        except PermissionDeniedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    @router.get("/workflow/runs", response_model=list[dict[str, Any]])
    def list_workflow_runs(
        organization_id: str = Query(...),
        user_id: str = Query(...),
        status_filter: Optional[str] = Query(None, alias="status"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """List historical workflow execution runs for tenant."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        runs = repo.list_workflow_runs(limit=limit, offset=offset, status=status_filter)
        return [r.to_dict() for r in runs]

    return router

