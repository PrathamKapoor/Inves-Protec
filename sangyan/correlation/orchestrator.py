"""Unified Investigation Orchestration Pipeline for SANGYAN.

Coordinates Content Intelligence, Authoritative Verification, Graph Correlation,
Scam-Chain Reconstruction, Taxonomy Classification, Safe Guidance, and Post-Quantum Trust Binding.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.correlation.correlator import InvestigationCorrelator
from sangyan.correlation.explainer import InvestigationExplainer
from sangyan.correlation.grievance import GrievanceRouter
from sangyan.correlation.guidance import GuidanceEngine
from sangyan.correlation.scam_chains import ScamChainReconstructor
from sangyan.correlation.taxonomy import ScamTaxonomyClassifier
from sangyan.domain.base import new_id
from sangyan.domain.models import (
    ActionGuidance,
    Claim,
    ContentItem,
    CorrelationEdge,
    Entity,
    Evidence,
    Finding,
    GrievanceRecord,
    Investigation,
    InvestigationExplanation,
    InvestigationStage,
    Signal,
)
from sangyan.intelligence.pipeline import ContentIntelligenceEngine
from sangyan.tenancy.repository import TenantRepository
from sangyan.verification.engine import ClaimVerificationEngine, VerificationOutcome
from sangyan.verification.trust_binding import TrustBindingService


@dataclass
class CorrelatedInvestigationReport:
    """Comprehensive investigation report combining cross-content correlation, scam chains, and PQC trust."""

    investigation: Investigation
    content_items: list[ContentItem]
    claims: list[Claim]
    entities: list[Entity]
    signals: list[Signal]
    findings: list[Finding]
    evidence_items: list[Evidence]
    correlations: list[CorrelationEdge]
    scam_chain: list[InvestigationStage]
    scam_patterns: list[str]
    guidance: list[ActionGuidance]
    grievance: GrievanceRecord
    explanation: InvestigationExplanation
    overall_status: str
    trust_receipt_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation.id,
            "overall_status": self.overall_status,
            "content_count": len(self.content_items),
            "claims_count": len(self.claims),
            "entities_count": len(self.entities),
            "signals_count": len(self.signals),
            "findings_count": len(self.findings),
            "correlations_count": len(self.correlations),
            "scam_patterns": self.scam_patterns,
            "trust_receipt_id": self.trust_receipt_id,
            "investigation": self.investigation.to_dict(),
            "explanation": self.explanation.to_dict(),
            "scam_chain": [s.to_dict() for s in self.scam_chain],
            "correlations": [c.to_dict() for c in self.correlations],
            "guidance": [g.to_dict() for g in self.guidance],
            "grievance": self.grievance.to_dict(),
        }


class InvestigationOrchestrator:
    """End-to-end investigation engine orchestrating intelligence, verification, correlation, and guidance."""

    def __init__(
        self,
        intelligence_engine: Optional[ContentIntelligenceEngine] = None,
        verification_engine: Optional[ClaimVerificationEngine] = None,
        correlator: Optional[InvestigationCorrelator] = None,
        reconstructor: Optional[ScamChainReconstructor] = None,
        classifier: Optional[ScamTaxonomyClassifier] = None,
        guidance_engine: Optional[GuidanceEngine] = None,
        grievance_router: Optional[GrievanceRouter] = None,
        explainer: Optional[InvestigationExplainer] = None,
        trust_binding: Optional[TrustBindingService] = None,
    ) -> None:
        self.intelligence_engine = intelligence_engine or ContentIntelligenceEngine()
        self.verification_engine = verification_engine or ClaimVerificationEngine(trust_binding=trust_binding)
        self.correlator = correlator or InvestigationCorrelator()
        self.reconstructor = reconstructor or ScamChainReconstructor()
        self.classifier = classifier or ScamTaxonomyClassifier()
        self.guidance_engine = guidance_engine or GuidanceEngine()
        self.grievance_router = grievance_router or GrievanceRouter()
        self.explainer = explainer or InvestigationExplainer()
        self.trust_binding = trust_binding or self.verification_engine.trust_binding

    def investigate(
        self,
        content_items: list[ContentItem],
        repository: Optional[TenantRepository] = None,
        user_id: str = "usr_analyst",
    ) -> CorrelatedInvestigationReport:
        """Execute holistic investigation across one or more content items within a tenant boundary."""
        if not content_items:
            raise ValueError("At least one ContentItem is required for investigation.")

        org_id = content_items[0].organization_id
        inv_id = new_id("inv")

        all_claims: list[Claim] = []
        all_entities: list[Entity] = []
        all_signals: list[Signal] = []
        all_findings: list[Finding] = []
        all_evidence: list[Evidence] = []
        all_outcomes: list[VerificationOutcome] = []

        is_educational_warning = False

        # -------------------------------------------------------------------
        # 1. Intake & Content Intelligence per ContentItem
        # -------------------------------------------------------------------
        for ci in content_items:
            analysis = self.intelligence_engine.analyze(ci)
            if repository:
                for clm in analysis.claims:
                    try:
                        repository.save_claim(clm)
                    except Exception:
                        pass
                for ent in analysis.entities:
                    try:
                        repository.save_entity(ent)
                    except Exception:
                        pass
                for sig in analysis.signals:
                    try:
                        repository.save_signal(sig)
                    except Exception:
                        pass

            # Tag metadata on entities so correlator knows which content item it came from
            for ent in analysis.entities:
                ent.metadata["content_item_id"] = ci.id

            all_claims.extend(analysis.claims)
            all_entities.extend(analysis.entities)
            all_signals.extend(analysis.signals)

            # Check if text is a hard-negative educational/warning advisory
            text_lower = ci.raw_content.lower()
            if any(term in text_lower for term in [
                "sebi warns", "warning to investors", "advisory for investors",
                "do not trust guaranteed returns", "never share otp", "educational alert"
            ]) and not any(term in text_lower for term in ["guarantee 40%", "deposit today", "pay fee"]):
                is_educational_warning = True

        # -------------------------------------------------------------------
        # 2. Authoritative Claim Verification
        # -------------------------------------------------------------------
        for claim in all_claims:
            outcome = self.verification_engine.verify_claim(
                claim=claim,
                entities=all_entities,
                repository=repository,
            )
            all_outcomes.append(outcome)
            all_findings.append(outcome.finding)
            all_evidence.extend(outcome.evidence_items)

        # -------------------------------------------------------------------
        # 3. Investigation Correlation & Relationship Graph
        # -------------------------------------------------------------------
        correlations = self.correlator.correlate_investigation(
            organization_id=org_id,
            investigation_id=inv_id,
            content_items=content_items,
            claims=all_claims,
            entities=all_entities,
            signals=all_signals,
            findings=all_findings,
            evidence_items=all_evidence,
            repository=repository,
        )

        # -------------------------------------------------------------------
        # 4. Scam-Chain Reconstruction & Pattern Taxonomy
        # -------------------------------------------------------------------
        scam_chain = self.reconstructor.reconstruct(
            organization_id=org_id,
            investigation_id=inv_id,
            signals=all_signals,
            claims=all_claims,
            findings=all_findings,
            evidence_items=all_evidence,
            is_educational_or_warning=is_educational_warning,
            repository=repository,
        )

        if not is_educational_warning:
            scam_patterns = self.classifier.classify(all_signals, all_claims, all_findings)
        else:
            scam_patterns = []

        # -------------------------------------------------------------------
        # 5. Risk Posture Synthesis
        # -------------------------------------------------------------------
        finding_statuses = {f.status for f in all_findings}
        signal_types = {s.signal_type for s in all_signals}

        high_risk_signals = {
            "GUARANTEED_RETURN", "WITHDRAWAL_FEE", "OTP_REQUEST",
            "CREDENTIAL_REQUEST", "THIRD_PARTY_PAYMENT", "UPI_MISMATCH"
        }
        warning_signals = {
            "URGENCY", "SCARCITY", "SOCIAL_MEDIA_SOLICITATION", "UNVERIFIED_APP", "PRESSURE_LANGUAGE"
        }

        if is_educational_warning:
            overall_status = "SAFE"
        elif "CONTRADICTED" in finding_statuses or bool(signal_types & high_risk_signals) or (
            len(scam_patterns) > 0 and "INVESTMENT_SCAM" in scam_patterns
        ):
            overall_status = "HIGH_RISK"
        elif "CONFLICTING" in finding_statuses or "OUTDATED" in finding_statuses or bool(signal_types & warning_signals):
            overall_status = "SUSPICIOUS"
        elif "SUPPORTED" in finding_statuses and all(s in {"SUPPORTED", "INSUFFICIENT_EVIDENCE"} for s in finding_statuses) and not signal_types:
            overall_status = "SAFE"
        else:
            overall_status = "UNVERIFIED"

        # -------------------------------------------------------------------
        # 6. Action Guidance & Grievance Routing
        # -------------------------------------------------------------------
        guidance = self.guidance_engine.generate_guidance(
            signals=all_signals,
            findings=all_findings,
            scam_patterns=scam_patterns,
            repository=repository,
        )

        combined_text = " ".join(ci.raw_content for ci in content_items)
        grievance = self.grievance_router.classify_and_route(
            organization_id=org_id,
            investigation_id=inv_id,
            content_text=combined_text,
            signals=all_signals,
            findings=all_findings,
            scam_patterns=scam_patterns,
            repository=repository,
        )

        # -------------------------------------------------------------------
        # 7. Investigation Explainability
        # -------------------------------------------------------------------
        explanation = self.explainer.explain(
            signals=all_signals,
            claims=all_claims,
            entities=all_entities,
            findings=all_findings,
            stages=scam_chain,
            scam_patterns=scam_patterns,
            overall_status=overall_status,
        )

        # -------------------------------------------------------------------
        # 8. Post-Quantum Trust Binding
        # -------------------------------------------------------------------
        trust_receipt_id: Optional[str] = None
        now = time.time()
        if self.trust_binding:
            finding_ids = [f.id for f in all_findings]
            evidence_hashes = [e.content_hash for e in all_evidence]
            receipt = self.trust_binding.bind_investigation(
                investigation_id=inv_id,
                overall_status=overall_status,
                finding_ids=finding_ids,
                evidence_hashes=evidence_hashes,
                scam_patterns=scam_patterns,
                organization_id=org_id,
                completed_at=now,
            )
            trust_receipt_id = receipt.id

        # -------------------------------------------------------------------
        # 9. Investigation Record & Persistence
        # -------------------------------------------------------------------
        summary = (
            f"Investigation {inv_id}: Posture={overall_status}. "
            f"Analyzed {len(content_items)} content items, {len(all_claims)} claims, "
            f"{len(all_entities)} entities, {len(all_signals)} signals, {len(correlations)} correlations. "
            f"Identified patterns: {', '.join(scam_patterns) if scam_patterns else 'None'}."
        )

        inv = Investigation(
            id=inv_id,
            organization_id=org_id,
            user_id=user_id,
            content_item_id=content_items[0].id,
            claim_ids=[c.id for c in all_claims],
            entity_ids=[e.id for e in all_entities],
            signal_ids=[s.id for s in all_signals],
            finding_ids=[f.id for f in all_findings],
            guidance_ids=[g.id for g in guidance],
            status="COMPLETED",
            summary=summary,
            created_at=now,
            completed_at=now,
            trust_receipt_id=trust_receipt_id,
            metadata={
                "overall_status": overall_status,
                "scam_patterns": scam_patterns,
                "correlations_count": len(correlations),
                "is_educational_warning": is_educational_warning,
            },
        )

        if repository is not None:
            repository.save_investigation(inv)
            repository.record_audit_event(
                action="investigate_content",
                resource=f"investigation:{inv.id}",
                result=overall_status,
                metadata={
                    "investigation_id": inv.id,
                    "content_count": len(content_items),
                    "claims_count": len(all_claims),
                    "correlations_count": len(correlations),
                    "overall_status": overall_status,
                    "scam_patterns": scam_patterns,
                    "trust_receipt_id": trust_receipt_id,
                },
            )

        return CorrelatedInvestigationReport(
            investigation=inv,
            content_items=content_items,
            claims=all_claims,
            entities=all_entities,
            signals=all_signals,
            findings=all_findings,
            evidence_items=all_evidence,
            correlations=correlations,
            scam_chain=scam_chain,
            scam_patterns=scam_patterns,
            guidance=guidance,
            grievance=grievance,
            explanation=explanation,
            overall_status=overall_status,
            trust_receipt_id=trust_receipt_id,
        )
