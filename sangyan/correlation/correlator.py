"""Deterministic Investigation Correlation Engine for SANGYAN.

Correlates entities, claims, signals, evidence, and content items across
single-content and multi-content scopes within tenant isolation boundaries.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sangyan.domain.models import (
    Claim,
    ContentItem,
    CorrelationEdge,
    Entity,
    Evidence,
    Finding,
    Signal,
)
from sangyan.tenancy.repository import TenantRepository


# Bounded graph safety limits
MAX_GRAPH_DEPTH = 5
MAX_EDGES_PER_INVESTIGATION = 200
MAX_RELATED_CONTENTS = 25


def normalize_phone(phone: str) -> str:
    """Normalize Indian and international phone numbers to standard canonical form."""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("+91") and len(cleaned) == 13:
        return cleaned[3:]
    if cleaned.startswith("91") and len(cleaned) == 12:
        return cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) == 11:
        return cleaned[1:]
    return cleaned


def normalize_upi(vpa: str) -> str:
    """Normalize UPI VPA handle to lowercase canonical form."""
    return vpa.strip().lower()


def normalize_registration(reg: str) -> str:
    """Normalize registration identifiers (SEBI, CIN, DP) by removing spaces and hyphens."""
    return re.sub(r"[\s\-_/]", "", reg.strip().upper())


def normalize_domain(domain: str) -> str:
    """Normalize domain/hostname to lowercase stripped of www."""
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d


class InvestigationCorrelator:
    """Correlates entities, claims, evidence, and content items into an explainable graph."""

    def __init__(
        self,
        max_depth: int = MAX_GRAPH_DEPTH,
        max_edges: int = MAX_EDGES_PER_INVESTIGATION,
        max_contents: int = MAX_RELATED_CONTENTS,
    ) -> None:
        self.max_depth = max_depth
        self.max_edges = max_edges
        self.max_contents = max_contents

    def correlate_investigation(
        self,
        organization_id: str,
        investigation_id: str,
        content_items: list[ContentItem],
        claims: list[Claim],
        entities: list[Entity],
        signals: list[Signal],
        findings: list[Finding],
        evidence_items: list[Evidence],
        repository: Optional[TenantRepository] = None,
    ) -> list[CorrelationEdge]:
        """Build deterministic, deduplicated, and bounded correlation edges for an investigation."""
        edges: list[CorrelationEdge] = []
        edge_keys: set[tuple[str, str, str]] = set()

        def add_edge(
            source_id: str,
            source_type: str,
            target_id: str,
            target_type: str,
            rel_type: str,
            strength: str,
            rationale: str,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            if len(edges) >= self.max_edges:
                return
            if source_id == target_id:
                return
            key = (source_id, target_id, rel_type)
            reverse_key = (target_id, source_id, rel_type)
            if key in edge_keys or reverse_key in edge_keys:
                return
            edge_keys.add(key)
            edge = CorrelationEdge(
                organization_id=organization_id,
                investigation_id=investigation_id,
                source_id=source_id,
                source_type=source_type,
                target_id=target_id,
                target_type=target_type,
                relationship_type=rel_type,
                strength=strength,
                rationale=rationale,
                metadata=metadata or {},
            )
            edges.append(edge)

        # -------------------------------------------------------------------
        # 1. Entity-to-Entity Correlation
        # -------------------------------------------------------------------
        for i in range(len(entities)):
            ent_a = entities[i]
            for j in range(i + 1, len(entities)):
                ent_b = entities[j]

                # Match on exact registration number (STRONG)
                if ent_a.registration_number and ent_b.registration_number:
                    reg_a = normalize_registration(ent_a.registration_number)
                    reg_b = normalize_registration(ent_b.registration_number)
                    if reg_a and reg_a == reg_b:
                        add_edge(
                            ent_a.id, "entity", ent_b.id, "entity",
                            "SAME_REGISTRATION", "STRONG",
                            f"Exact registration number match: {reg_a}",
                        )
                        continue

                # Match on UPI VPA (STRONG)
                if ent_a.entity_type == "UPI" and ent_b.entity_type == "UPI":
                    upi_a = normalize_upi(ent_a.name)
                    upi_b = normalize_upi(ent_b.name)
                    if upi_a and upi_a == upi_b:
                        add_edge(
                            ent_a.id, "entity", ent_b.id, "entity",
                            "SAME_UPI", "STRONG",
                            f"Exact normalized UPI handle match: {upi_a}",
                        )
                        continue

                # Match on Domain/Website (STRONG)
                if (ent_a.official_url and ent_b.official_url) or (
                    ent_a.entity_type == "WEBSITE" and ent_b.entity_type == "WEBSITE"
                ):
                    dom_a = normalize_domain(ent_a.official_url or ent_a.name)
                    dom_b = normalize_domain(ent_b.official_url or ent_b.name)
                    if dom_a and dom_b and dom_a == dom_b:
                        add_edge(
                            ent_a.id, "entity", ent_b.id, "entity",
                            "SAME_DOMAIN", "STRONG",
                            f"Exact canonical hostname match: {dom_a}",
                        )
                        continue

                # Match on exact normalized Name (MEDIUM)
                name_a = ent_a.name.strip().lower()
                name_b = ent_b.name.strip().lower()
                if name_a and name_b and name_a == name_b and len(name_a) >= 4:
                    add_edge(
                        ent_a.id, "entity", ent_b.id, "entity",
                        "SAME_ENTITY", "MEDIUM",
                        f"Exact normalized entity name match: {ent_a.name}",
                    )

        # -------------------------------------------------------------------
        # 2. Claim-to-Entity Links
        # -------------------------------------------------------------------
        for claim in claims:
            stmt_lower = claim.statement.lower()
            for ent in entities:
                ent_name_clean = ent.name.strip().lower()
                matched = False
                rationale = ""
                strength = "MEDIUM"

                if ent.registration_number:
                    reg_norm = normalize_registration(ent.registration_number)
                    if reg_norm and reg_norm.lower() in normalize_registration(claim.statement).lower():
                        matched = True
                        strength = "STRONG"
                        rationale = f"Claim references registration number: {ent.registration_number}"

                if not matched and ent.entity_type == "UPI":
                    upi_norm = normalize_upi(ent.name)
                    if upi_norm and upi_norm in stmt_lower:
                        matched = True
                        strength = "STRONG"
                        rationale = f"Claim references UPI handle: {ent.name}"

                if not matched and ent_name_clean and len(ent_name_clean) >= 3 and ent_name_clean in stmt_lower:
                    matched = True
                    strength = "MEDIUM"
                    rationale = f"Claim mentions financial entity: {ent.name}"

                if matched:
                    add_edge(
                        claim.id, "claim", ent.id, "entity",
                        "CLAIM_DEPENDENCY", strength, rationale,
                    )

        # -------------------------------------------------------------------
        # 3. Evidence-to-Claim / Finding Links
        # -------------------------------------------------------------------
        finding_by_claim = {f.claim_id: f for f in findings}
        for evid in evidence_items:
            rel = "EVIDENCE_SUPPORTS" if evid.stance == "SUPPORTS" else (
                "EVIDENCE_CONTRADICTS" if evid.stance == "CONTRADICTS" else "CLAIM_DEPENDENCY"
            )
            add_edge(
                evid.id, "evidence", evid.claim_id, "claim",
                rel, "STRONG",
                f"Authoritative evidence from {evid.source_id}: stance {evid.stance}",
            )
            if evid.claim_id in finding_by_claim:
                fnd = finding_by_claim[evid.claim_id]
                add_edge(
                    evid.id, "evidence", fnd.id, "finding",
                    rel, "STRONG",
                    f"Evidence anchored to finding statement: {fnd.statement[:80]}",
                )

        # -------------------------------------------------------------------
        # 4. Multi-Content Item Temporal and Correlation Links
        # -------------------------------------------------------------------
        if len(content_items) > 1:
            # Sort content items deterministically by timestamp
            sorted_items = sorted(
                content_items[:self.max_contents],
                key=lambda x: (x.created_at, x.id),
            )
            for k in range(len(sorted_items) - 1):
                cur = sorted_items[k]
                nxt = sorted_items[k + 1]
                add_edge(
                    cur.id, "content_item", nxt.id, "content_item",
                    "TEMPORALLY_FOLLOWS", "STRONG",
                    f"Temporal sequence: {cur.created_at:.2f} -> {nxt.created_at:.2f}",
                )

        # -------------------------------------------------------------------
        # 5. Cross-Content Shared Entity Links
        # -------------------------------------------------------------------
        if len(content_items) > 1:
            for i in range(len(content_items)):
                ci_a = content_items[i]
                ents_a = [e for e in entities if e.metadata.get("content_item_id") == ci_a.id]
                for j in range(i + 1, len(content_items)):
                    ci_b = content_items[j]
                    ents_b = [e for e in entities if e.metadata.get("content_item_id") == ci_b.id]

                    shared_identifiers: list[str] = []
                    for ea in ents_a:
                        for eb in ents_b:
                            if ea.registration_number and eb.registration_number:
                                if normalize_registration(ea.registration_number) == normalize_registration(eb.registration_number):
                                    shared_identifiers.append(f"Reg:{ea.registration_number}")
                            if ea.entity_type == "UPI" and eb.entity_type == "UPI":
                                if normalize_upi(ea.name) == normalize_upi(eb.name):
                                    shared_identifiers.append(f"UPI:{ea.name}")
                            if (ea.official_url and eb.official_url) or (ea.entity_type == "WEBSITE" and eb.entity_type == "WEBSITE"):
                                if normalize_domain(ea.official_url or ea.name) == normalize_domain(eb.official_url or eb.name):
                                    shared_identifiers.append(f"Domain:{ea.name}")

                    if shared_identifiers:
                        add_edge(
                            ci_a.id, "content_item", ci_b.id, "content_item",
                            "SHARED_INFRASTRUCTURE", "STRONG",
                            f"Shared cross-content identifiers: {', '.join(set(shared_identifiers))}",
                        )

        # Deterministic sorting of edges
        edges.sort(key=lambda e: (e.relationship_type, e.strength, e.source_id, e.target_id))

        # Optional persistence
        if repository is not None:
            for edge in edges:
                repository.save_correlation(edge)

        return edges

    def correlate_cross_tenant_probe(
        self,
        target_org_id: str,
        investigation_id: str,
        repository: TenantRepository,
    ) -> list[CorrelationEdge]:
        """Security validation: confirm that cross-tenant correlation queries are strictly blocked."""
        # TenantRepository will raise PermissionDeniedError or return empty results for foreign orgs
        return repository.list_correlations_for_investigation(investigation_id)
