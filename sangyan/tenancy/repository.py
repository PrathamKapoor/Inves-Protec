"""Tenant-scoped persistence and administration layer for SANGYAN."""
from __future__ import annotations

import json
import time

from sangyan.core.errors import DomainValidationError, NotFoundError, PermissionDeniedError
from sangyan.database.engine import DatabaseEngine
from sangyan.domain.base import new_id
from sangyan.domain.models import (
    ActionGuidance,
    Claim,
    ContentItem,
    Entity,
    Evidence,
    Finding,
    Investigation,
    Review,
    Signal,
    Source,
)
from sangyan.tenancy.models import SANGYAN_ROLES, has_permission


class TenantAdministration:
    """Administrative provisioning service for organizations and memberships."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._db = engine

    def create_organization(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise DomainValidationError("organization name cannot be empty")
        org_id = new_id("org")
        self._db.execute(
            "INSERT INTO sangyan_organizations (id, name, status, created_at) VALUES (?,?,?,?)",
            (org_id, name, "active", time.time()),
        )
        return org_id

    def create_user(self, email: str, name: str) -> str:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise DomainValidationError("valid email address required")
        user_id = new_id("usr")
        self._db.execute(
            "INSERT INTO sangyan_users (id, email, name, status, created_at) VALUES (?,?,?,?,?)",
            (user_id, email, name.strip(), "active", time.time()),
        )
        return user_id

    def add_membership(self, organization_id: str, user_id: str, role: str) -> str:
        if role not in SANGYAN_ROLES:
            raise DomainValidationError(f"role '{role}' must be one of {SANGYAN_ROLES}")
        mem_id = new_id("mem")
        self._db.execute(
            "INSERT INTO sangyan_memberships (id, organization_id, user_id, role, status, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (mem_id, organization_id, user_id, role, "active", time.time()),
        )
        return mem_id


class TenantRepository:
    """Repository scoped strictly to a single tenant organization and authenticated user."""

    def __init__(self, engine: DatabaseEngine, organization_id: str, user_id: str) -> None:
        if not organization_id or not user_id:
            raise PermissionDeniedError("organization_id and user_id are required")
        self._db = engine
        self.organization_id = organization_id
        self.user_id = user_id
        self._role = self._resolve_role()

    def _resolve_role(self) -> str:
        row = self._db.query_one(
            "SELECT role FROM sangyan_memberships WHERE organization_id=? AND user_id=? AND status='active'",
            (self.organization_id, self.user_id),
        )
        if row is None:
            raise PermissionDeniedError(
                f"user '{self.user_id}' has no active membership in organization '{self.organization_id}'"
            )
        return row["role"]

    def _require_permission(self, permission: str) -> None:
        if not has_permission(self._role, permission):
            raise PermissionDeniedError(f"role '{self._role}' lacks required permission: {permission}")

    # -----------------------------------------------------------------------
    # Content Items
    # -----------------------------------------------------------------------

    def save_content_item(self, item: ContentItem) -> str:
        self._require_permission("investigation:create")
        if item.organization_id != self.organization_id:
            raise PermissionDeniedError("content item tenant does not match active organization")
        problems = item.validate()
        if problems:
            raise DomainValidationError(f"invalid content item: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_content_items
            (id, organization_id, content_type, raw_content, normalized_text, source_url,
             content_hash, language, created_at, processing_status, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                item.id,
                item.organization_id,
                item.content_type,
                item.raw_content,
                item.normalized_text,
                item.source_url,
                item.content_hash,
                item.language,
                item.created_at,
                item.processing_status,
                json.dumps(item.metadata),
                item.schema_version,
            ),
        )
        return item.id

    def get_content_item(self, content_id: str) -> ContentItem:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_content_items WHERE id=? AND organization_id=?",
            (content_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"content item '{content_id}' not found in organization")
        return ContentItem(
            id=row["id"],
            organization_id=row["organization_id"],
            content_type=row["content_type"],
            raw_content=row["raw_content"],
            normalized_text=row["normalized_text"],
            source_url=row["source_url"],
            content_hash=row["content_hash"],
            language=row["language"],
            created_at=row["created_at"],
            processing_status=row["processing_status"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    # -----------------------------------------------------------------------
    # Claims & Signals & Findings
    # -----------------------------------------------------------------------

    def save_claim(self, claim: Claim) -> str:
        self._require_permission("investigation:create")
        problems = claim.validate()
        if problems:
            raise DomainValidationError(f"invalid claim: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_claims
            (id, content_item_id, statement, claim_type, status, confidence, extracted_at, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                claim.id,
                claim.content_item_id,
                claim.statement,
                claim.claim_type,
                claim.status,
                json.dumps(claim.confidence.to_dict()) if claim.confidence else None,
                claim.extracted_at,
                json.dumps(claim.metadata),
                claim.schema_version,
            ),
        )
        return claim.id

    def get_claim(self, claim_id: str) -> Claim:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            """
            SELECT c.* FROM sangyan_claims c
            JOIN sangyan_content_items ci ON c.content_item_id = ci.id
            WHERE c.id=? AND ci.organization_id=?
            """,
            (claim_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"claim '{claim_id}' not found")
        conf_dict = json.loads(row["confidence"]) if row["confidence"] else None
        return Claim(
            id=row["id"],
            content_item_id=row["content_item_id"],
            statement=row["statement"],
            claim_type=row["claim_type"],
            status=row["status"],
            confidence=Finding.from_dict({"confidence": conf_dict, "claim_id": "", "statement": "", "status": "UNVERIFIED"}).confidence if conf_dict else None,
            extracted_at=row["extracted_at"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def save_signal(self, sig: Signal) -> str:
        self._require_permission("investigation:create")
        problems = sig.validate()
        if problems:
            raise DomainValidationError(f"invalid signal: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_signals
            (id, content_item_id, signal_type, excerpt, detection_basis, confidence, observed_at, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                sig.id,
                sig.content_item_id,
                sig.signal_type,
                sig.excerpt,
                sig.detection_basis,
                sig.confidence,
                sig.observed_at,
                json.dumps(sig.metadata),
                sig.schema_version,
            ),
        )
        return sig.id

    def save_finding(self, finding: Finding) -> str:
        self._require_permission("investigation:create")
        problems = finding.validate()
        if problems:
            raise DomainValidationError(f"invalid finding: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_findings
            (id, claim_id, statement, status, confidence, evidence_refs, source_refs,
             rationale, limitations, generated_at, verification_version, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                finding.id,
                finding.claim_id,
                finding.statement,
                finding.status,
                json.dumps(finding.confidence.to_dict()) if finding.confidence else None,
                json.dumps(finding.evidence_refs),
                json.dumps(finding.source_refs),
                finding.rationale,
                finding.limitations,
                finding.generated_at,
                finding.verification_version,
                finding.schema_version,
            ),
        )
        return finding.id

    # -----------------------------------------------------------------------
    # Investigations
    # -----------------------------------------------------------------------

    def save_investigation(self, inv: Investigation) -> str:
        self._require_permission("investigation:create")
        if inv.organization_id != self.organization_id:
            raise PermissionDeniedError("investigation tenant does not match active organization")
        problems = inv.validate()
        if problems:
            raise DomainValidationError(f"invalid investigation: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_investigations
            (id, organization_id, user_id, content_item_id, claim_ids, entity_ids, signal_ids,
             finding_ids, guidance_ids, status, summary, created_at, completed_at, trust_receipt_id,
             metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                inv.id,
                inv.organization_id,
                inv.user_id,
                inv.content_item_id,
                json.dumps(inv.claim_ids),
                json.dumps(inv.entity_ids),
                json.dumps(inv.signal_ids),
                json.dumps(inv.finding_ids),
                json.dumps(inv.guidance_ids),
                inv.status,
                inv.summary,
                inv.created_at,
                inv.completed_at,
                inv.trust_receipt_id,
                json.dumps(inv.metadata),
                inv.schema_version,
            ),
        )
        return inv.id

    def get_investigation(self, inv_id: str) -> Investigation:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_investigations WHERE id=? AND organization_id=?",
            (inv_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"investigation '{inv_id}' not found in organization")
        return Investigation(
            id=row["id"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            content_item_id=row["content_item_id"],
            claim_ids=json.loads(row["claim_ids"] or "[]"),
            entity_ids=json.loads(row["entity_ids"] or "[]"),
            signal_ids=json.loads(row["signal_ids"] or "[]"),
            finding_ids=json.loads(row["finding_ids"] or "[]"),
            guidance_ids=json.loads(row["guidance_ids"] or "[]"),
            status=row["status"],
            summary=row["summary"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            trust_receipt_id=row["trust_receipt_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    # -----------------------------------------------------------------------
    # Reviews
    # -----------------------------------------------------------------------

    def record_review(self, rev: Review) -> str:
        self._require_permission("investigation:review")
        # Verify investigation belongs to this tenant
        self.get_investigation(rev.investigation_id)
        problems = rev.validate()
        if problems:
            raise DomainValidationError(f"invalid review: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_reviews
            (id, investigation_id, reviewer_id, action, finding_id, reason, occurred_at,
             previous_revision_id, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rev.id,
                rev.investigation_id,
                rev.reviewer_id,
                rev.action,
                rev.finding_id,
                rev.reason,
                rev.occurred_at,
                rev.previous_revision_id,
                json.dumps(rev.metadata),
                rev.schema_version,
            ),
        )
        return rev.id
