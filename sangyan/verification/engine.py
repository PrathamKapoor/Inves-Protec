"""Authoritative Claim Verification Engine coordinating multi-source verification and conflict resolution."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.crypto.hashing import digest_document, sha3_256_text
from sangyan.domain.models import (
    AUTHORITY_TIERS,
    CLAIM_STATUSES,
    Claim,
    ConfidenceVector,
    ContentItem,
    Entity,
    Evidence,
    Finding,
    Source,
)
from sangyan.tenancy.repository import TenantRepository
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.adapters.circulars import CircularsVerificationAdapter
from sangyan.verification.adapters.mca import MCAVerificationAdapter
from sangyan.verification.adapters.official_domains import OfficialDomainsVerificationAdapter
from sangyan.verification.adapters.sebi import SEBIVerificationAdapter
from sangyan.verification.cache import RateLimiter, VerificationCache
from sangyan.verification.snapshots import SnapshotManager
from sangyan.verification.sources import AuthoritativeSourceRegistry
from sangyan.verification.trust_binding import TrustBindingService


@dataclass
class VerificationOutcome:
    """Consolidated verification result for a single claim across all authoritative sources."""

    claim_id: str
    status: str  # SUPPORTED, CONTRADICTED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE
    finding: Finding
    evidence_items: list[Evidence] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    trust_receipt_id: Optional[str] = None
    adapter_results: list[AdapterResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "finding": self.finding.to_dict(),
            "evidence_count": len(self.evidence_items),
            "evidence": [e.to_dict() for e in self.evidence_items],
            "sources": [s.to_dict() for s in self.sources],
            "trust_receipt_id": self.trust_receipt_id,
        }


class ClaimVerificationEngine:
    """Orchestrates authoritative verification, conflict resolution, evidence synthesis, and trust binding."""

    def __init__(
        self,
        source_registry: Optional[AuthoritativeSourceRegistry] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        trust_binding: Optional[TrustBindingService] = None,
        cache: Optional[VerificationCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.registry = source_registry or AuthoritativeSourceRegistry()
        self.snapshots = snapshot_manager or SnapshotManager()
        self.trust_binding = trust_binding
        self.cache = cache or VerificationCache()
        self.rate_limiter = rate_limiter or RateLimiter()

        # Register default authoritative adapters
        self.adapters: list[VerificationAdapter] = [
            SEBIVerificationAdapter(self.snapshots),
            MCAVerificationAdapter(self.snapshots),
            CircularsVerificationAdapter(self.snapshots),
            OfficialDomainsVerificationAdapter(self.snapshots),
        ]

    def add_adapter(self, adapter: VerificationAdapter) -> None:
        """Register custom or specialized verification adapter."""
        self.adapters.append(adapter)

    def verify_claim(
        self,
        claim: Claim,
        entities: Optional[list[Entity]] = None,
        repository: Optional[TenantRepository] = None,
    ) -> VerificationOutcome:
        """Verify an individual claim against all supporting authoritative adapters."""
        candidate_entities = entities or []
        applicable_adapters = [a for a in self.adapters if a.supports(claim)]

        if not applicable_adapters:
            # No adapter claims authority for this claim type
            finding = Finding(
                claim_id=claim.id,
                statement=claim.statement,
                status="INSUFFICIENT_EVIDENCE",
                confidence=ConfidenceVector(analytical_support=0.5, evidence_completeness=0.0, source_authority_weight=0.0),
                rationale="No authoritative source adapter is configured to evaluate claims of this type.",
                limitations="Absence of authoritative source adapter.",
            )
            claim.status = "INSUFFICIENT_EVIDENCE"
            return VerificationOutcome(claim_id=claim.id, status="INSUFFICIENT_EVIDENCE", finding=finding)

        results: list[AdapterResult] = []
        for adapter in applicable_adapters:
            # Check rate limiter
            if not self.rate_limiter.allow_request(adapter.source_id):
                continue

            # Attempt matching against associated entities first, or fallback to standalone claim
            matched_entity = self._find_relevant_entity(claim, candidate_entities)
            res = adapter.verify(claim, matched_entity)
            results.append(res)

        # Epistemic stance determination and conflict resolution
        status, rationale, confidence_vector = self._resolve_stances(results)
        claim.status = status

        # Build Evidence domain objects
        evidence_items: list[Evidence] = []
        source_refs: list[str] = []
        for res in results:
            if res.status in {"verified", "not_found"}:
                source_meta = self.registry.get_source(res.source_id)
                src_domain = source_meta.to_domain_source() if source_meta else Source(
                    id=res.source_id,
                    name=res.source_id,
                    authority_tier="T0_REGULATOR",
                )
                if repository:
                    try:
                        repository.save_source(src_domain)
                    except Exception:
                        pass  # Source may already exist

                source_refs.append(src_domain.id)
                evidence_stance = "SUPPORTS" if res.stance == "SUPPORTED" else (
                    "CONTRADICTS" if res.stance in {"CONTRADICTED", "OUTDATED"} else "NEUTRAL"
                )
                evid = Evidence(
                    source_id=src_domain.id,
                    claim_id=claim.id,
                    excerpt=res.excerpt,
                    structured_fact=res.structured_fact,
                    stance=evidence_stance,
                    relevance=res.confidence_score,
                    content_hash=sha3_256_text(res.excerpt),
                    retrieved_at=res.retrieved_at,
                    published_at=res.retrieved_at,
                    metadata={"adapter_id": res.adapter_id, "rationale": res.rationale},
                )
                evidence_items.append(evid)

        evidence_refs = [e.id for e in evidence_items]

        # Construct authoritative Finding
        finding = Finding(
            claim_id=claim.id,
            statement=claim.statement,
            status=status,
            confidence=confidence_vector,
            evidence_refs=evidence_refs,
            source_refs=list(set(source_refs)),
            rationale=rationale,
            limitations="" if status in {"SUPPORTED", "CONTRADICTED"} else "Verification subject to snapshot freshness.",
        )

        # Cryptographic Trust Binding
        trust_receipt_id: Optional[str] = None
        if self.trust_binding:
            try:
                receipt = self.trust_binding.bind_finding(finding, claim, evidence_items)
                trust_receipt_id = receipt.id
            except Exception:
                trust_receipt_id = None

        # Persist through TenantRepository if provided
        if repository:
            for ev in evidence_items:
                repository.save_evidence(ev)
            repository.save_finding(finding)

        return VerificationOutcome(
            claim_id=claim.id,
            status=status,
            finding=finding,
            evidence_items=evidence_items,
            trust_receipt_id=trust_receipt_id,
            adapter_results=results,
        )

    def verify_all_claims(
        self,
        claims: list[Claim],
        entities: Optional[list[Entity]] = None,
        repository: Optional[TenantRepository] = None,
    ) -> list[VerificationOutcome]:
        """Verify all decomposed claims in an investigation batch."""
        return [self.verify_claim(claim, entities, repository) for claim in claims]

    def _resolve_stances(
        self, results: list[AdapterResult]
    ) -> tuple[str, str, ConfidenceVector]:
        """Multi-source conflict resolution determining final stance, rationale, and confidence."""
        if not results:
            return (
                "INSUFFICIENT_EVIDENCE",
                "No authoritative results were obtained.",
                ConfidenceVector(analytical_support=0.5, evidence_completeness=0.0, source_authority_weight=0.0),
            )

        stances = [r.stance for r in results]
        has_supported = "SUPPORTED" in stances
        has_contradicted = "CONTRADICTED" in stances
        has_outdated = "OUTDATED" in stances
        has_insufficient = "INSUFFICIENT_EVIDENCE" in stances

        # Conflict Resolution Rule:
        # If authoritative sources provide diametrically opposed findings (e.g. one active, one cancelled)
        if has_supported and (has_contradicted or has_outdated):
            competing = [f"{r.source_id}: {r.stance} ({r.excerpt})" for r in results if r.stance in {"SUPPORTED", "CONTRADICTED", "OUTDATED"}]
            rationale = "CONFLICTING: Authoritative sources provided incompatible evidence. Discrepancy details: " + " | ".join(competing)
            conf = ConfidenceVector(analytical_support=0.5, evidence_completeness=0.9, source_authority_weight=0.9)
            return "CONFLICTING", rationale, conf

        # Temporal Expiration Rule:
        if has_outdated:
            outdated_res = [r for r in results if r.stance == "OUTDATED"][0]
            rationale = f"OUTDATED: {outdated_res.rationale}"
            conf = ConfidenceVector(analytical_support=0.9, evidence_completeness=0.85, source_authority_weight=0.95)
            return "OUTDATED", rationale, conf

        # Contradicted Rule:
        if has_contradicted:
            contra_res = [r for r in results if r.stance == "CONTRADICTED"][0]
            rationale = f"CONTRADICTED: {contra_res.rationale}"
            conf = ConfidenceVector(analytical_support=0.95, evidence_completeness=0.9, source_authority_weight=0.95)
            return "CONTRADICTED", rationale, conf

        # Supported Rule:
        if has_supported:
            sup_res = [r for r in results if r.stance == "SUPPORTED"][0]
            rationale = f"SUPPORTED: {sup_res.rationale}"
            conf = ConfidenceVector(analytical_support=0.95, evidence_completeness=0.9, source_authority_weight=0.95)
            return "SUPPORTED", rationale, conf

        # Default Insufficient Evidence:
        rationale = "INSUFFICIENT_EVIDENCE: Available authoritative sources do not contain sufficient evidence to substantiate or refute the claim."
        conf = ConfidenceVector(analytical_support=0.5, evidence_completeness=0.3, source_authority_weight=0.5)
        return "INSUFFICIENT_EVIDENCE", rationale, conf

    def _find_relevant_entity(self, claim: Claim, entities: list[Entity]) -> Optional[Entity]:
        """Find entity associated with the claim via identifier or name overlap."""
        stmt = claim.statement.lower()
        for ent in entities:
            if ent.registration_number and ent.registration_number.lower() in stmt:
                return ent
            if ent.name.lower() in stmt:
                return ent
        return entities[0] if entities else None
