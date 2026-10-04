"""Typed state definition and serialization contracts for LangGraph investigation workflows."""
from __future__ import annotations

import time
from typing import Any, Optional, TypedDict

from sangyan.domain.base import new_id
from sangyan.domain.models import ContentItem


class InvestigationWorkflowState(TypedDict, total=False):
    """Explicitly typed workflow execution state passed across LangGraph nodes."""

    # Identifiers & Tenancy
    investigation_id: str
    organization_id: str
    user_id: str
    run_id: str
    thread_id: str

    # Content & Extraction
    content_items: list[dict[str, Any]]
    content_item_ids: list[str]
    claims: list[dict[str, Any]]
    claim_ids: list[str]
    entities: list[dict[str, Any]]
    entity_ids: list[str]
    signals: list[dict[str, Any]]
    signal_ids: list[str]

    # Verification & Grounding
    findings: list[dict[str, Any]]
    finding_ids: list[str]
    evidence_items: list[dict[str, Any]]
    evidence_ids: list[str]

    # Correlation & Synthesis
    correlations: list[dict[str, Any]]
    correlation_ids: list[str]
    scam_chain: list[dict[str, Any]]
    scam_patterns: list[str]
    risk_posture: str
    is_educational_warning: bool

    # Guidance, Grievance & Explanation
    guidance: list[dict[str, Any]]
    guidance_ids: list[str]
    grievance: Optional[dict[str, Any]]
    explanation: Optional[dict[str, Any]]

    # Review & Governance
    review_required: bool
    review_reason: str
    review_decision: Optional[dict[str, Any]]

    # Execution Lifecycle & Trust
    current_stage: str
    status: str
    trust_status: str
    trust_receipt_id: Optional[str]
    errors: list[str]
    warnings: list[str]
    retry_count: int
    max_retries: int
    created_at: float
    updated_at: float
    metadata: dict[str, Any]


def create_initial_workflow_state(
    content_items: list[ContentItem],
    organization_id: str,
    user_id: str,
    investigation_id: Optional[str] = None,
    run_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    max_retries: int = 3,
    force_review: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> InvestigationWorkflowState:
    """Construct a clean, valid initial state for an investigation workflow."""
    now = time.time()
    inv_id = investigation_id or new_id("inv")
    r_id = run_id or new_id("run")
    th_id = thread_id or f"{organization_id}:{inv_id}:{r_id}"

    return {
        "investigation_id": inv_id,
        "organization_id": organization_id,
        "user_id": user_id,
        "run_id": r_id,
        "thread_id": th_id,
        "content_items": [c.to_dict() for c in content_items],
        "content_item_ids": [c.id for c in content_items],
        "claims": [],
        "claim_ids": [],
        "entities": [],
        "entity_ids": [],
        "signals": [],
        "signal_ids": [],
        "findings": [],
        "finding_ids": [],
        "evidence_items": [],
        "evidence_ids": [],
        "correlations": [],
        "correlation_ids": [],
        "scam_chain": [],
        "scam_patterns": [],
        "risk_posture": "UNVERIFIED",
        "is_educational_warning": False,
        "guidance": [],
        "guidance_ids": [],
        "grievance": None,
        "explanation": None,
        "review_required": force_review,
        "review_reason": "Forced supervisory review requested at launch" if force_review else "",
        "review_decision": None,
        "current_stage": "intake_node",
        "status": "QUEUED",
        "trust_status": "PENDING",
        "trust_receipt_id": None,
        "errors": [],
        "warnings": [],
        "retry_count": 0,
        "max_retries": max_retries,
        "created_at": now,
        "updated_at": now,
        "metadata": dict(metadata or {}),
    }
