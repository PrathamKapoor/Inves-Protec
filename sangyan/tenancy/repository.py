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
    ConfidenceVector,
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
        self._require_permission("investigation:create")
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
        self._require_permission("investigation:create")
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
        self._require_permission("investigation:create")
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
        self._require_permission("investigation:create")
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
        self._require_permission("investigation:create")
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
