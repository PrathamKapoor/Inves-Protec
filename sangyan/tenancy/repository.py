"""Tenant-scoped persistence and administration layer for SANGYAN."""
from __future__ import annotations

import json
import time

from sangyan.core.errors import DomainValidationError, NotFoundError, PermissionDeniedError
from sangyan.database.engine import DatabaseEngine
from sangyan.domain.base import new_id
from sangyan.domain.models import (
    ActionGuidance,
    AuditEvent,
    Claim,
    ConfidenceVector,
    ContentItem,
    CorrelationEdge,
    Entity,
    Evidence,
    Finding,
    GrievanceRecord,
    Investigation,
    InvestigationStage,
    Review,
    Signal,
    Source,
    WorkflowRun,
    normalize_content_type,
)
from sangyan.security.models import ApiKey
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

    def __init__(
        self,
        engine: DatabaseEngine,
        organization_id: str,
        user_id: str,
        dr_manager: Optional[Any] = None,
        region_id: Optional[str] = None,
    ) -> None:
        if not organization_id or not user_id:
            raise PermissionDeniedError("organization_id and user_id are required")
        self._db = engine
        self.organization_id = organization_id
        self.user_id = user_id
        self._dr_manager = dr_manager
        self._region_id = region_id
        from sangyan.async_exec.repository import AsyncTaskRepository
        self._task_repo = AsyncTaskRepository(engine)
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

    def _require_permission(self, permission: str, write: bool = False) -> None:
        if not has_permission(self._role, permission):
            raise PermissionDeniedError(f"role '{self._role}' lacks required permission: {permission}")
        if write:
            self._assert_write_authority()

    def _assert_write_authority(self) -> None:
        if self._dr_manager is not None:
            self._dr_manager.verify_write_authority(self._region_id)

    # -----------------------------------------------------------------------
    # Content Items
    # -----------------------------------------------------------------------

    def save_content_item(self, item: ContentItem) -> str:
        self._require_permission("investigation:create")
        self._assert_write_authority()
        if item.organization_id != self.organization_id:
            raise PermissionDeniedError("content item tenant does not match active organization")
        # Canonicalize MIME-style / legacy content types before validation so
        # submissions (e.g. 'text/plain') are never silently dropped.
        item.content_type = normalize_content_type(item.content_type)
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
        self._require_permission("investigation:create", write=True)
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
            confidence=ConfidenceVector.from_dict(conf_dict) if conf_dict else None,
            extracted_at=row["extracted_at"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_claims_for_content(self, content_item_id: str) -> list[Claim]:
        self._require_permission("investigation:read")
        # Ensure content item belongs to this tenant
        self.get_content_item(content_item_id)
        rows = self._db.query_all(
            "SELECT * FROM sangyan_claims WHERE content_item_id=? ORDER BY extracted_at ASC",
            (content_item_id,),
        )
        claims = []
        for r in rows:
            conf_dict = json.loads(r["confidence"]) if r["confidence"] else None
            claims.append(
                Claim(
                    id=r["id"],
                    content_item_id=r["content_item_id"],
                    statement=r["statement"],
                    claim_type=r["claim_type"],
                    status=r["status"],
                    confidence=ConfidenceVector.from_dict(conf_dict) if conf_dict else None,
                    extracted_at=r["extracted_at"],
                    metadata=json.loads(r["metadata"] or "{}"),
                    schema_version=r["schema_version"],
                )
            )
        return claims

    # -----------------------------------------------------------------------
    # Signals
    # -----------------------------------------------------------------------

    def save_signal(self, sig: Signal) -> str:
        self._require_permission("investigation:create", write=True)
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

    def get_signal(self, signal_id: str) -> Signal:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            """
            SELECT s.* FROM sangyan_signals s
            JOIN sangyan_content_items ci ON s.content_item_id = ci.id
            WHERE s.id=? AND ci.organization_id=?
            """,
            (signal_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"signal '{signal_id}' not found")
        return Signal(
            id=row["id"],
            content_item_id=row["content_item_id"],
            signal_type=row["signal_type"],
            excerpt=row["excerpt"],
            detection_basis=row["detection_basis"],
            confidence=row["confidence"],
            observed_at=row["observed_at"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_signals_for_content(self, content_item_id: str) -> list[Signal]:
        self._require_permission("investigation:read")
        self.get_content_item(content_item_id)
        rows = self._db.query_all(
            "SELECT * FROM sangyan_signals WHERE content_item_id=? ORDER BY observed_at ASC",
            (content_item_id,),
        )
        return [
            Signal(
                id=r["id"],
                content_item_id=r["content_item_id"],
                signal_type=r["signal_type"],
                excerpt=r["excerpt"],
                detection_basis=r["detection_basis"],
                confidence=r["confidence"],
                observed_at=r["observed_at"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Findings
    # -----------------------------------------------------------------------

    def save_finding(self, finding: Finding) -> str:
        self._require_permission("investigation:create", write=True)
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

    def get_finding(self, finding_id: str) -> Finding:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            """
            SELECT f.* FROM sangyan_findings f
            JOIN sangyan_claims c ON f.claim_id = c.id
            JOIN sangyan_content_items ci ON c.content_item_id = ci.id
            WHERE f.id=? AND ci.organization_id=?
            """,
            (finding_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"finding '{finding_id}' not found")
        conf_dict = json.loads(row["confidence"]) if row["confidence"] else None
        return Finding(
            id=row["id"],
            claim_id=row["claim_id"],
            statement=row["statement"],
            status=row["status"],
            confidence=ConfidenceVector.from_dict(conf_dict) if conf_dict else None,
            evidence_refs=json.loads(row["evidence_refs"] or "[]"),
            source_refs=json.loads(row["source_refs"] or "[]"),
            rationale=row["rationale"],
            limitations=row["limitations"],
            generated_at=row["generated_at"],
            verification_version=row["verification_version"],
            schema_version=row["schema_version"],
        )

    def list_findings_for_claim(self, claim_id: str) -> list[Finding]:
        self._require_permission("investigation:read")
        # Ensure claim belongs to this tenant
        self.get_claim(claim_id)
        rows = self._db.query_all(
            "SELECT * FROM sangyan_findings WHERE claim_id=? ORDER BY generated_at ASC",
            (claim_id,),
        )
        findings = []
        for r in rows:
            conf_dict = json.loads(r["confidence"]) if r["confidence"] else None
            findings.append(
                Finding(
                    id=r["id"],
                    claim_id=r["claim_id"],
                    statement=r["statement"],
                    status=r["status"],
                    confidence=ConfidenceVector.from_dict(conf_dict) if conf_dict else None,
                    evidence_refs=json.loads(r["evidence_refs"] or "[]"),
                    source_refs=json.loads(r["source_refs"] or "[]"),
                    rationale=r["rationale"],
                    limitations=r["limitations"],
                    generated_at=r["generated_at"],
                    verification_version=r["verification_version"],
                    schema_version=r["schema_version"],
                )
            )
        return findings

    # -----------------------------------------------------------------------
    # Entities
    # -----------------------------------------------------------------------

    def save_entity(self, entity: Entity) -> str:
        self._require_permission("investigation:create", write=True)
        problems = entity.validate()
        if problems:
            raise DomainValidationError(f"invalid entity: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_entities
            (id, name, entity_type, aliases, registration_number, official_url, created_at, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                entity.id,
                entity.name,
                entity.entity_type,
                json.dumps(entity.aliases),
                entity.registration_number,
                entity.official_url,
                entity.created_at,
                json.dumps(entity.metadata),
                entity.schema_version,
            ),
        )
        return entity.id

    def get_entity(self, entity_id: str) -> Entity:
        self._require_permission("investigation:read")
        row = self._db.query_one("SELECT * FROM sangyan_entities WHERE id=?", (entity_id,))
        if row is None:
            raise NotFoundError(f"entity '{entity_id}' not found")
        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            aliases=json.loads(row["aliases"] or "[]"),
            registration_number=row["registration_number"],
            official_url=row["official_url"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_entities(self, limit: int = 50, offset: int = 0) -> list[Entity]:
        self._require_permission("investigation:read")
        rows = self._db.query_all(
            "SELECT * FROM sangyan_entities ORDER BY name ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [
            Entity(
                id=r["id"],
                name=r["name"],
                entity_type=r["entity_type"],
                aliases=json.loads(r["aliases"] or "[]"),
                registration_number=r["registration_number"],
                official_url=r["official_url"],
                created_at=r["created_at"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Sources
    # -----------------------------------------------------------------------

    def save_source(self, source: Source) -> str:
        self._require_permission("investigation:create", write=True)
        problems = source.validate()
        if problems:
            raise DomainValidationError(f"invalid source: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_sources
            (id, name, authority_tier, url, publisher, published_at, retrieved_at, valid_until, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                source.id,
                source.name,
                source.authority_tier,
                source.url,
                source.publisher,
                source.published_at,
                source.retrieved_at,
                source.valid_until,
                json.dumps(source.metadata),
                source.schema_version,
            ),
        )
        return source.id

    def get_source(self, source_id: str) -> Source:
        self._require_permission("investigation:read")
        row = self._db.query_one("SELECT * FROM sangyan_sources WHERE id=?", (source_id,))
        if row is None:
            raise NotFoundError(f"source '{source_id}' not found")
        return Source(
            id=row["id"],
            name=row["name"],
            authority_tier=row["authority_tier"],
            url=row["url"],
            publisher=row["publisher"],
            published_at=row["published_at"],
            retrieved_at=row["retrieved_at"],
            valid_until=row["valid_until"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_sources(self, authority_tier: str | None = None) -> list[Source]:
        self._require_permission("investigation:read")
        if authority_tier:
            rows = self._db.query_all(
                "SELECT * FROM sangyan_sources WHERE authority_tier=? ORDER BY retrieved_at DESC",
                (authority_tier,),
            )
        else:
            rows = self._db.query_all("SELECT * FROM sangyan_sources ORDER BY authority_tier ASC")
        return [
            Source(
                id=r["id"],
                name=r["name"],
                authority_tier=r["authority_tier"],
                url=r["url"],
                publisher=r["publisher"],
                published_at=r["published_at"],
                retrieved_at=r["retrieved_at"],
                valid_until=r["valid_until"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Evidence
    # -----------------------------------------------------------------------

    def save_evidence(self, evidence: Evidence) -> str:
        self._require_permission("investigation:create", write=True)
        problems = evidence.validate()
        if problems:
            raise DomainValidationError(f"invalid evidence: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_evidence
            (id, source_id, claim_id, excerpt, structured_fact, stance, relevance,
             content_hash, retrieved_at, published_at, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                evidence.id,
                evidence.source_id,
                evidence.claim_id,
                evidence.excerpt,
                json.dumps(evidence.structured_fact),
                evidence.stance,
                evidence.relevance,
                evidence.content_hash,
                evidence.retrieved_at,
                evidence.published_at,
                json.dumps(evidence.metadata),
                evidence.schema_version,
            ),
        )
        return evidence.id

    def get_evidence(self, evidence_id: str) -> Evidence:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            """
            SELECT e.* FROM sangyan_evidence e
            JOIN sangyan_claims c ON e.claim_id = c.id
            JOIN sangyan_content_items ci ON c.content_item_id = ci.id
            WHERE e.id=? AND ci.organization_id=?
            """,
            (evidence_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"evidence '{evidence_id}' not found")
        return Evidence(
            id=row["id"],
            source_id=row["source_id"],
            claim_id=row["claim_id"],
            excerpt=row["excerpt"],
            structured_fact=json.loads(row["structured_fact"] or "{}"),
            stance=row["stance"],
            relevance=row["relevance"],
            content_hash=row["content_hash"],
            retrieved_at=row["retrieved_at"],
            published_at=row["published_at"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_evidence_for_claim(self, claim_id: str) -> list[Evidence]:
        self._require_permission("investigation:read")
        self.get_claim(claim_id)
        rows = self._db.query_all(
            "SELECT * FROM sangyan_evidence WHERE claim_id=? ORDER BY relevance DESC",
            (claim_id,),
        )
        return [
            Evidence(
                id=r["id"],
                source_id=r["source_id"],
                claim_id=r["claim_id"],
                excerpt=r["excerpt"],
                structured_fact=json.loads(r["structured_fact"] or "{}"),
                stance=r["stance"],
                relevance=r["relevance"],
                content_hash=r["content_hash"],
                retrieved_at=r["retrieved_at"],
                published_at=r["published_at"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Action Guidance
    # -----------------------------------------------------------------------

    def save_guidance(self, guidance: ActionGuidance) -> str:
        self._require_permission("investigation:create", write=True)
        problems = guidance.validate()
        if problems:
            raise DomainValidationError(f"invalid guidance: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_action_guidance
            (id, category, title, description, official_url, priority, urgency, limitations, metadata, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                guidance.id,
                guidance.category,
                guidance.title,
                guidance.description,
                guidance.official_url,
                guidance.priority,
                1 if guidance.urgency else 0,
                guidance.limitations,
                json.dumps(guidance.metadata),
                guidance.schema_version,
            ),
        )
        return guidance.id

    def get_guidance(self, guidance_id: str) -> ActionGuidance:
        self._require_permission("investigation:read")
        row = self._db.query_one("SELECT * FROM sangyan_action_guidance WHERE id=?", (guidance_id,))
        if row is None:
            raise NotFoundError(f"action guidance '{guidance_id}' not found")
        return ActionGuidance(
            id=row["id"],
            category=row["category"],
            title=row["title"],
            description=row["description"],
            official_url=row["official_url"],
            priority=row["priority"],
            urgency=bool(row["urgency"]),
            limitations=row["limitations"],
            metadata=json.loads(row["metadata"] or "{}"),
            schema_version=row["schema_version"],
        )

    def list_guidance(self, category: str | None = None) -> list[ActionGuidance]:
        self._require_permission("investigation:read")
        if category:
            rows = self._db.query_all(
                "SELECT * FROM sangyan_action_guidance WHERE category=? ORDER BY priority ASC",
                (category,),
            )
        else:
            rows = self._db.query_all("SELECT * FROM sangyan_action_guidance ORDER BY priority ASC")
        return [
            ActionGuidance(
                id=r["id"],
                category=r["category"],
                title=r["title"],
                description=r["description"],
                official_url=r["official_url"],
                priority=r["priority"],
                urgency=bool(r["urgency"]),
                limitations=r["limitations"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Investigations
    # -----------------------------------------------------------------------

    def save_investigation(self, inv: Investigation) -> str:
        self._require_permission("investigation:create", write=True)
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

    def list_investigations(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[Investigation]:
        self._require_permission("investigation:read")
        if status:
            rows = self._db.query_all(
                """
                SELECT * FROM sangyan_investigations
                WHERE organization_id=? AND status=?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (self.organization_id, status, limit, offset),
            )
        else:
            rows = self._db.query_all(
                """
                SELECT * FROM sangyan_investigations
                WHERE organization_id=?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (self.organization_id, limit, offset),
            )
        return [
            Investigation(
                id=r["id"],
                organization_id=r["organization_id"],
                user_id=r["user_id"],
                content_item_id=r["content_item_id"],
                claim_ids=json.loads(r["claim_ids"] or "[]"),
                entity_ids=json.loads(r["entity_ids"] or "[]"),
                signal_ids=json.loads(r["signal_ids"] or "[]"),
                finding_ids=json.loads(r["finding_ids"] or "[]"),
                guidance_ids=json.loads(r["guidance_ids"] or "[]"),
                status=r["status"],
                summary=r["summary"],
                created_at=r["created_at"],
                completed_at=r["completed_at"],
                trust_receipt_id=r["trust_receipt_id"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    def update_investigation(
        self,
        inv_id: str,
        *,
        status: str | None = None,
        summary: str | None = None,
        completed: bool = False,
        trust_receipt_id: str | None = None,
        claim_ids: list[str] | None = None,
        signal_ids: list[str] | None = None,
        finding_ids: list[str] | None = None,
        entity_ids: list[str] | None = None,
        guidance_ids: list[str] | None = None,
    ) -> None:
        self._require_permission("investigation:create", write=True)
        inv = self.get_investigation(inv_id)
        new_status = status or inv.status
        new_summary = summary if summary is not None else inv.summary
        completed_at = time.time() if completed else inv.completed_at
        receipt_id = trust_receipt_id or inv.trust_receipt_id
        c_ids = json.dumps(claim_ids if claim_ids is not None else inv.claim_ids)
        s_ids = json.dumps(signal_ids if signal_ids is not None else inv.signal_ids)
        f_ids = json.dumps(finding_ids if finding_ids is not None else inv.finding_ids)
        e_ids = json.dumps(entity_ids if entity_ids is not None else inv.entity_ids)
        g_ids = json.dumps(guidance_ids if guidance_ids is not None else inv.guidance_ids)

        self._db.execute(
            """
            UPDATE sangyan_investigations
            SET status=?, summary=?, completed_at=?, trust_receipt_id=?,
                claim_ids=?, signal_ids=?, finding_ids=?, entity_ids=?, guidance_ids=?
            WHERE id=? AND organization_id=?
            """,
            (
                new_status,
                new_summary,
                completed_at,
                receipt_id,
                c_ids,
                s_ids,
                f_ids,
                e_ids,
                g_ids,
                inv_id,
                self.organization_id,
            ),
        )

    def transition_investigation_status(
        self,
        inv_id: str,
        from_status: str,
        to_status: str,
        *,
        summary: str | None = None,
    ) -> bool:
        """Atomically transition investigation status from from_status to to_status.

        Uses database-level conditional update for concurrency safety across multiple pods/workers.
        Returns True if the transition succeeded (1 row updated), False if the investigation was
        not in from_status or belonged to a different tenant.
        """
        self._require_permission("investigation:create", write=True)
        now = time.time()
        completed_clause = ", completed_at = ?" if to_status in ("COMPLETED", "FAILED", "CANCELLED") else ""
        summary_clause = ", summary = ?" if summary is not None else ""

        sql = f"""
        UPDATE sangyan_investigations
        SET status = ?{completed_clause}{summary_clause}
        WHERE id = ? AND organization_id = ? AND status = ?
        """
        params: list[Any] = [to_status]
        if completed_clause:
            params.append(now)
        if summary_clause:
            params.append(summary)
        params.extend([inv_id, self.organization_id, from_status])

        rowcount = self._db.execute(sql, tuple(params))
        return bool(rowcount and rowcount > 0)

    # -----------------------------------------------------------------------
    # Reviews
    # -----------------------------------------------------------------------

    def record_review(self, rev: Review) -> str:
        self._require_permission("investigation:review", write=True)
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

    def list_reviews_for_investigation(self, inv_id: str) -> list[Review]:
        self._require_permission("investigation:read")
        self.get_investigation(inv_id)
        rows = self._db.query_all(
            "SELECT * FROM sangyan_reviews WHERE investigation_id=? ORDER BY occurred_at ASC",
            (inv_id,),
        )
        return [
            Review(
                id=r["id"],
                investigation_id=r["investigation_id"],
                reviewer_id=r["reviewer_id"],
                action=r["action"],
                finding_id=r["finding_id"],
                reason=r["reason"],
                occurred_at=r["occurred_at"],
                previous_revision_id=r["previous_revision_id"],
                metadata=json.loads(r["metadata"] or "{}"),
                schema_version=r["schema_version"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Audit Events
    # -----------------------------------------------------------------------

    def record_audit_event(
        self,
        action: str,
        resource: str,
        result: str,
        metadata: dict | None = None,
    ) -> str:
        """Record a tamper-evident audit event with SHA3-256 chained ledger hashing."""
        self._require_permission("investigation:create", write=True)
        now = time.time()
        audit_id = new_id("audit")
        event_id = f"evt_{int(now * 1000)}_{audit_id[-8:]}"
        meta = dict(metadata or {})
        # Enforce tenant isolation by binding organization_id to metadata
        meta["organization_id"] = self.organization_id

        from sangyan.crypto.hashing import sha3_hex

        with self._db.transaction():
            if self._db.dialect == "postgresql":
                try:
                    self._db.execute("SELECT pg_advisory_xact_lock(918273)")
                except Exception:
                    pass

            last_row = self._db.query_one("SELECT ledger_hash FROM sangyan_audit_events ORDER BY timestamp DESC, id DESC LIMIT 1")
            prev_hash = last_row["ledger_hash"] if last_row and last_row.get("ledger_hash") else "0" * 64

            raw_ledger = f"{prev_hash}:{event_id}:{self.user_id}:{action}:{resource}:{result}:{now}"
            ledger_hash = sha3_hex(raw_ledger.encode("utf-8"))

            self._db.execute(
                """
                INSERT INTO sangyan_audit_events
                (id, event_id, timestamp, actor, action, resource, result, metadata, ledger_hash)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    audit_id,
                    event_id,
                    now,
                    self.user_id,
                    action,
                    resource,
                    result,
                    json.dumps(meta),
                    ledger_hash,
                ),
            )
        return audit_id

    def list_audit_events(
        self,
        limit: int = 100,
        action: str | None = None,
    ) -> list[AuditEvent]:
        """List audit events scoped strictly to this tenant organization."""
        self._require_permission("investigation:read")
        query = "SELECT * FROM sangyan_audit_events WHERE metadata LIKE ? "
        params: list = [f'%"organization_id": "{self.organization_id}"%']
        if action:
            query += "AND action = ? "
            params.append(action)
        query += "ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._db.query_all(query, tuple(params))
        return [
            AuditEvent(
                id=r["id"],
                event_id=r["event_id"],
                timestamp=r["timestamp"],
                actor=r["actor"],
                action=r["action"],
                resource=r["resource"],
                result=r["result"],
                metadata=json.loads(r["metadata"] or "{}"),
                ledger_hash=r["ledger_hash"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Correlations & Relationships
    # -----------------------------------------------------------------------

    def save_correlation(self, edge: CorrelationEdge) -> str:
        self._require_permission("investigation:create", write=True)
        if edge.organization_id != self.organization_id:
            raise PermissionDeniedError("correlation tenant does not match active organization")
        problems = edge.validate()
        if problems:
            raise DomainValidationError(f"invalid correlation edge: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_correlations
            (id, organization_id, investigation_id, source_id, source_type,
             target_id, target_type, relationship_type, strength, rationale, metadata, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                edge.id,
                edge.organization_id,
                edge.investigation_id,
                edge.source_id,
                edge.source_type,
                edge.target_id,
                edge.target_type,
                edge.relationship_type,
                edge.strength,
                edge.rationale,
                json.dumps(edge.metadata),
                edge.created_at,
            ),
        )
        return edge.id

    def get_correlation(self, corr_id: str) -> CorrelationEdge:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_correlations WHERE id=? AND organization_id=?",
            (corr_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"correlation '{corr_id}' not found in organization")
        return CorrelationEdge(
            id=row["id"],
            organization_id=row["organization_id"],
            investigation_id=row["investigation_id"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            relationship_type=row["relationship_type"],
            strength=row["strength"],
            rationale=row["rationale"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
        )

    def list_correlations_for_investigation(self, inv_id: str) -> list[CorrelationEdge]:
        self._require_permission("investigation:read")
        rows = self._db.query_all(
            "SELECT * FROM sangyan_correlations WHERE investigation_id=? AND organization_id=? ORDER BY created_at ASC",
            (inv_id, self.organization_id),
        )
        return [
            CorrelationEdge(
                id=r["id"],
                organization_id=r["organization_id"],
                investigation_id=r["investigation_id"],
                source_id=r["source_id"],
                source_type=r["source_type"],
                target_id=r["target_id"],
                target_type=r["target_type"],
                relationship_type=r["relationship_type"],
                strength=r["strength"],
                rationale=r["rationale"],
                metadata=json.loads(r["metadata"] or "{}"),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def find_correlations_by_target(self, target_id: str) -> list[CorrelationEdge]:
        self._require_permission("investigation:read")
        rows = self._db.query_all(
            "SELECT * FROM sangyan_correlations WHERE target_id=? AND organization_id=? ORDER BY created_at ASC",
            (target_id, self.organization_id),
        )
        return [
            CorrelationEdge(
                id=r["id"],
                organization_id=r["organization_id"],
                investigation_id=r["investigation_id"],
                source_id=r["source_id"],
                source_type=r["source_type"],
                target_id=r["target_id"],
                target_type=r["target_type"],
                relationship_type=r["relationship_type"],
                strength=r["strength"],
                rationale=r["rationale"],
                metadata=json.loads(r["metadata"] or "{}"),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Scam Chain Stages
    # -----------------------------------------------------------------------

    def save_scam_chain_stage(self, stage: InvestigationStage) -> str:
        self._require_permission("investigation:create", write=True)
        if stage.organization_id != self.organization_id:
            raise PermissionDeniedError("stage tenant does not match active organization")
        problems = stage.validate()
        if problems:
            raise DomainValidationError(f"invalid scam chain stage: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_scam_chain_stages
            (id, organization_id, investigation_id, stage, status,
             evidence_refs, signal_refs, details, sequence_order, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                stage.id,
                stage.organization_id,
                stage.investigation_id,
                stage.stage,
                stage.status,
                json.dumps(stage.evidence_refs),
                json.dumps(stage.signal_refs),
                stage.details,
                stage.sequence_order,
                stage.created_at,
            ),
        )
        return stage.id

    def list_scam_chain_stages(self, inv_id: str) -> list[InvestigationStage]:
        self._require_permission("investigation:read")
        rows = self._db.query_all(
            "SELECT * FROM sangyan_scam_chain_stages WHERE investigation_id=? AND organization_id=? "
            "ORDER BY sequence_order ASC, created_at ASC",
            (inv_id, self.organization_id),
        )
        return [
            InvestigationStage(
                id=r["id"],
                organization_id=r["organization_id"],
                investigation_id=r["investigation_id"],
                stage=r["stage"],
                status=r["status"],
                evidence_refs=json.loads(r["evidence_refs"] or "[]"),
                signal_refs=json.loads(r["signal_refs"] or "[]"),
                details=r["details"],
                sequence_order=r["sequence_order"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Grievance Records
    # -----------------------------------------------------------------------

    def save_grievance_record(self, record: GrievanceRecord) -> str:
        self._require_permission("investigation:create", write=True)
        if record.organization_id != self.organization_id:
            raise PermissionDeniedError("grievance record tenant does not match active organization")
        problems = record.validate()
        if problems:
            raise DomainValidationError(f"invalid grievance record: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_grievance_records
            (id, organization_id, investigation_id, category, routing_channel,
             portal_url, helpline, guidance_steps, metadata, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.id,
                record.organization_id,
                record.investigation_id,
                record.category,
                record.routing_channel,
                record.portal_url,
                record.helpline,
                json.dumps(record.guidance_steps),
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record.id

    def get_grievance_record(self, inv_id: str) -> GrievanceRecord | None:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_grievance_records WHERE investigation_id=? AND organization_id=?",
            (inv_id, self.organization_id),
        )
        if row is None:
            return None
        return GrievanceRecord(
            id=row["id"],
            organization_id=row["organization_id"],
            investigation_id=row["investigation_id"],
            category=row["category"],
            routing_channel=row["routing_channel"],
            portal_url=row["portal_url"],
            helpline=row["helpline"],
            guidance_steps=json.loads(row["guidance_steps"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
        )

    # -----------------------------------------------------------------------
    # Workflow Runs
    # -----------------------------------------------------------------------

    def save_workflow_run(self, run: WorkflowRun) -> str:
        self._require_permission("investigation:create", write=True)
        if run.organization_id != self.organization_id:
            raise PermissionDeniedError("workflow run tenant does not match active organization")
        problems = run.validate()
        if problems:
            raise DomainValidationError(f"invalid workflow run: {problems}", errors=problems)
        self._db.execute(
            """
            INSERT INTO sangyan_workflow_runs
            (id, organization_id, investigation_id, thread_id, run_id, status,
             current_node, retry_count, checkpoint_id, metadata, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run.id,
                run.organization_id,
                run.investigation_id,
                run.thread_id,
                run.run_id,
                run.status,
                run.current_node,
                run.retry_count,
                run.checkpoint_id,
                json.dumps(run.metadata),
                run.created_at,
                run.updated_at,
            ),
        )
        return run.id

    def get_workflow_run(self, run_id: str) -> WorkflowRun:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_workflow_runs WHERE id=? AND organization_id=?",
            (run_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"workflow run '{run_id}' not found in organization")
        return WorkflowRun(
            id=row["id"],
            organization_id=row["organization_id"],
            investigation_id=row["investigation_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            status=row["status"],
            current_node=row["current_node"],
            retry_count=int(row["retry_count"]),
            checkpoint_id=row["checkpoint_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_workflow_run_by_investigation(self, inv_id: str) -> WorkflowRun | None:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_workflow_runs WHERE investigation_id=? AND organization_id=? ORDER BY created_at DESC LIMIT 1",
            (inv_id, self.organization_id),
        )
        if row is None:
            return None
        return WorkflowRun(
            id=row["id"],
            organization_id=row["organization_id"],
            investigation_id=row["investigation_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            status=row["status"],
            current_node=row["current_node"],
            retry_count=int(row["retry_count"]),
            checkpoint_id=row["checkpoint_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_workflow_run_by_thread(self, thread_id: str) -> WorkflowRun | None:
        self._require_permission("investigation:read")
        row = self._db.query_one(
            "SELECT * FROM sangyan_workflow_runs WHERE thread_id=? AND organization_id=? ORDER BY created_at DESC LIMIT 1",
            (thread_id, self.organization_id),
        )
        if row is None:
            return None
        return WorkflowRun(
            id=row["id"],
            organization_id=row["organization_id"],
            investigation_id=row["investigation_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            status=row["status"],
            current_node=row["current_node"],
            retry_count=int(row["retry_count"]),
            checkpoint_id=row["checkpoint_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_workflow_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        current_node: str | None = None,
        retry_count: int | None = None,
        checkpoint_id: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._require_permission("investigation:create", write=True)
        run = self.get_workflow_run(run_id)
        new_status = status or run.status
        new_node = current_node or run.current_node
        new_retries = retry_count if retry_count is not None else run.retry_count
        new_cp = checkpoint_id if checkpoint_id is not None else run.checkpoint_id
        new_meta = dict(metadata) if metadata is not None else dict(run.metadata)
        if error_message:
            new_meta["error"] = error_message
        now = time.time()
        self._db.execute(
            """
            UPDATE sangyan_workflow_runs
            SET status=?, current_node=?, retry_count=?, checkpoint_id=?, metadata=?, updated_at=?
            WHERE id=? AND organization_id=?
            """,
            (
                new_status,
                new_node,
                new_retries,
                new_cp,
                json.dumps(new_meta),
                now,
                run_id,
                self.organization_id,
            ),
        )

    def list_workflow_runs(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[WorkflowRun]:
        self._require_permission("investigation:read")
        if status:
            rows = self._db.query_all(
                """
                SELECT * FROM sangyan_workflow_runs
                WHERE organization_id=? AND status=?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (self.organization_id, status, limit, offset),
            )
        else:
            rows = self._db.query_all(
                """
                SELECT * FROM sangyan_workflow_runs
                WHERE organization_id=?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (self.organization_id, limit, offset),
            )
        return [
            WorkflowRun(
                id=r["id"],
                organization_id=r["organization_id"],
                investigation_id=r["investigation_id"],
                thread_id=r["thread_id"],
                run_id=r["run_id"],
                status=r["status"],
                current_node=r["current_node"],
                retry_count=int(r["retry_count"]),
                checkpoint_id=r["checkpoint_id"],
                metadata=json.loads(r["metadata"] or "{}"),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # API Keys
    # -----------------------------------------------------------------------

    def save_api_key(self, api_key: ApiKey) -> str:
        self._require_permission("api_key:manage", write=True)
        if api_key.organization_id != self.organization_id:
            raise PermissionDeniedError("api key tenant does not match active organization")
        self._db.execute(
            """
            INSERT INTO sangyan_api_keys
            (id, organization_id, user_id, name, key_prefix, key_hash, role, scopes,
             expires_at, revoked_at, last_used_at, created_at, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                api_key.id,
                api_key.organization_id,
                api_key.user_id,
                api_key.name,
                api_key.key_prefix,
                api_key.key_hash,
                api_key.role,
                json.dumps(api_key.scopes),
                api_key.expires_at,
                api_key.revoked_at,
                api_key.last_used_at,
                api_key.created_at,
                api_key.schema_version,
            ),
        )
        return api_key.id

    def get_api_key(self, key_id: str) -> ApiKey:
        self._require_permission("api_key:manage")
        row = self._db.query_one(
            "SELECT * FROM sangyan_api_keys WHERE id=? AND organization_id=?",
            (key_id, self.organization_id),
        )
        if row is None:
            raise NotFoundError(f"API key '{key_id}' not found in organization '{self.organization_id}'")
        return ApiKey(
            id=row["id"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            key_hash=row["key_hash"],
            role=row["role"],
            scopes=json.loads(row["scopes"] or "[]"),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
            schema_version=int(row["schema_version"]),
        )

    def get_api_key_by_prefix(self, key_prefix: str) -> Optional[ApiKey]:
        """Fetch API key by prefix scoped to current organization."""
        row = self._db.query_one(
            "SELECT * FROM sangyan_api_keys WHERE key_prefix=? AND organization_id=?",
            (key_prefix, self.organization_id),
        )
        if row is None:
            return None
        return ApiKey(
            id=row["id"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            key_hash=row["key_hash"],
            role=row["role"],
            scopes=json.loads(row["scopes"] or "[]"),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
            schema_version=int(row["schema_version"]),
        )

    def list_api_keys(self, limit: int = 50, offset: int = 0) -> list[ApiKey]:
        self._require_permission("api_key:manage")
        rows = self._db.query_all(
            """
            SELECT * FROM sangyan_api_keys
            WHERE organization_id=?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (self.organization_id, limit, offset),
        )
        return [
            ApiKey(
                id=r["id"],
                organization_id=r["organization_id"],
                user_id=r["user_id"],
                name=r["name"],
                key_prefix=r["key_prefix"],
                key_hash=r["key_hash"],
                role=r["role"],
                scopes=json.loads(r["scopes"] or "[]"),
                expires_at=r["expires_at"],
                revoked_at=r["revoked_at"],
                last_used_at=r["last_used_at"],
                created_at=r["created_at"],
                schema_version=int(r["schema_version"]),
            )
            for r in rows
        ]

    def revoke_api_key(self, key_id: str) -> ApiKey:
        self._require_permission("api_key:manage", write=True)
        key = self.get_api_key(key_id)
        if key.revoked_at is None:
            now = time.time()
            self._db.execute(
                "UPDATE sangyan_api_keys SET revoked_at=? WHERE id=? AND organization_id=?",
                (now, key_id, self.organization_id),
            )
            key.revoked_at = now
        return key

    def update_api_key_last_used(self, key_id: str, timestamp: float) -> None:
        self._db.execute(
            "UPDATE sangyan_api_keys SET last_used_at=? WHERE id=? AND organization_id=?",
            (timestamp, key_id, self.organization_id),
        )

    # -----------------------------------------------------------------------
    # Asynchronous Tasks (Tenant-Scoped Outbox)
    # -----------------------------------------------------------------------

    def save_async_task(self, task: Any) -> str:
        self._require_permission("investigation:create", write=True)
        if task.organization_id != self.organization_id:
            raise PermissionDeniedError("task tenant does not match active organization")
        return self._task_repo.save_task(task)

    def get_async_task(self, task_id: str) -> Any:
        self._require_permission("investigation:read")
        return self._task_repo.get_task(task_id, organization_id=self.organization_id)

    def list_async_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Any]:
        self._require_permission("investigation:read")
        return self._task_repo.list_tasks(
            organization_id=self.organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def retry_dead_letter_task(self, task_id: str) -> Any:
        self._require_permission("investigation:create", write=True)
        return self._task_repo.retry_dead_letter_task(task_id, organization_id=self.organization_id)

    def cancel_async_task(self, task_id: str, reason: str = "") -> Any:
        self._require_permission("investigation:create", write=True)
        return self._task_repo.cancel_task(task_id, organization_id=self.organization_id, reason=reason)



