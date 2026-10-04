"""Node implementations for the LangGraph investigation StateGraph.

Orchestrates deterministic SANGYAN domain services without duplicating business logic.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from langgraph.types import interrupt

from sangyan.correlation.correlator import InvestigationCorrelator
from sangyan.correlation.explainer import InvestigationExplainer
from sangyan.correlation.grievance import GrievanceRouter
from sangyan.correlation.guidance import GuidanceEngine
from sangyan.correlation.scam_chains import ScamChainReconstructor
from sangyan.correlation.taxonomy import ScamTaxonomyClassifier
from sangyan.domain.models import (
    ActionGuidance,
    Claim,
    ContentItem,
    CorrelationEdge,
    Entity,
    Evidence,
    Finding,
    Investigation,
    InvestigationStage,
    Review,
    Signal,
)
from sangyan.intelligence.pipeline import ContentIntelligenceEngine
from sangyan.tenancy.repository import TenantRepository
from sangyan.verification.engine import ClaimVerificationEngine, VerificationOutcome
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.errors import RetryableWorkflowError
from sangyan.workflow.state import InvestigationWorkflowState


class WorkflowNodeSuite:
    """Suite of LangGraph workflow node functions coordinating underlying SANGYAN domain engines."""

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
        repository_factory: Optional[Callable[[str], TenantRepository]] = None,
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
        self.repository_factory = repository_factory

    def _get_repository(self, organization_id: str, user_id: Optional[str] = None) -> Optional[TenantRepository]:
        if self.repository_factory is None:
            return None
        import inspect
        sig = inspect.signature(self.repository_factory)
        if len(sig.parameters) >= 2 or any(p.name == "user_id" for p in sig.parameters.values()):
            return self.repository_factory(organization_id, user_id=user_id) if "user_id" in sig.parameters else self.repository_factory(organization_id, user_id)
        repo = self.repository_factory(organization_id)
        if user_id and hasattr(repo, "user_id") and repo.user_id != user_id:
            return TenantRepository(repo._db, organization_id, user_id)
        return repo

    # -----------------------------------------------------------------------
    # Node 1: Intake
    # -----------------------------------------------------------------------
    def intake_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Validate input content items and persist them within tenant scope."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        user_id = state["user_id"]
        raw_items = state.get("content_items", [])
        if not raw_items:
            return {
                "errors": state.get("errors", []) + ["No content items provided in workflow state."],
                "status": "FAILED",
                "current_stage": "intake_node",
                "updated_at": time.time(),
            }

        repo = self._get_repository(org_id, state.get("user_id"))
        content_items = [ContentItem.from_dict(d) for d in raw_items]

        if repo is not None:
            for item in content_items:
                try:
                    repo.save_content_item(item)
                except Exception:
                    pass  # Item already persisted

            # Create or update investigation record in repository
            try:
                existing_inv = repo.get_investigation(inv_id)
            except Exception:
                existing_inv = None

            if existing_inv is None:
                new_inv = Investigation(
                    id=inv_id,
                    organization_id=org_id,
                    user_id=user_id,
                    content_item_id=content_items[0].id,
                    status="INTAKE",
                    summary=f"Investigation initiated for {len(content_items)} content item(s).",
                    created_at=state.get("created_at", time.time()),
                )
                try:
                    repo.save_investigation(new_inv)
                except Exception:
                    pass

        return {
            "content_item_ids": [c.id for c in content_items],
            "status": "INTAKE",
            "current_stage": "intake_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 2: Content Intelligence
    # -----------------------------------------------------------------------
    def intelligence_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Decompose atomic claims, resolve financial entities, and extract observable signals."""
        org_id = state["organization_id"]
        repo = self._get_repository(org_id, state.get("user_id"))
        raw_items = state.get("content_items", [])
        content_items = [ContentItem.from_dict(d) for d in raw_items]

        all_claims: list[Claim] = []
        all_entities: list[Entity] = []
        all_signals: list[Signal] = []
        is_educational_warning = False

        for ci in content_items:
            analysis = self.intelligence_engine.analyze(ci)

            if repo is not None:
                for clm in analysis.claims:
                    try:
                        repo.save_claim(clm)
                    except Exception:
                        pass
                for ent in analysis.entities:
                    try:
                        repo.save_entity(ent)
                    except Exception:
                        pass
                for sig in analysis.signals:
                    try:
                        repo.save_signal(sig)
                    except Exception:
                        pass

            for ent in analysis.entities:
                ent.metadata["content_item_id"] = ci.id

            all_claims.extend(analysis.claims)
            all_entities.extend(analysis.entities)
            all_signals.extend(analysis.signals)

            text_lower = ci.raw_content.lower()
            if any(term in text_lower for term in [
                "sebi warns", "warning to investors", "advisory for investors",
                "do not trust guaranteed returns", "never share otp", "educational alert"
            ]) and not any(term in text_lower for term in ["guarantee 40%", "deposit today", "pay fee"]):
                is_educational_warning = True

        if repo is not None:
            try:
                repo.update_investigation(
                    state["investigation_id"],
                    status="ANALYZING",
                    claim_ids=[c.id for c in all_claims],
                    entity_ids=[e.id for e in all_entities],
                    signal_ids=[s.id for s in all_signals],
                )
            except Exception:
                pass

        return {
            "claims": [c.to_dict() for c in all_claims],
            "claim_ids": [c.id for c in all_claims],
            "entities": [e.to_dict() for e in all_entities],
            "entity_ids": [e.id for e in all_entities],
            "signals": [s.to_dict() for s in all_signals],
            "signal_ids": [s.id for s in all_signals],
            "is_educational_warning": is_educational_warning,
            "status": "ANALYZING",
            "current_stage": "intelligence_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 3: Authoritative Verification
    # -----------------------------------------------------------------------
    def verification_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Verify atomic claims against authoritative regulatory adapters."""
        org_id = state["organization_id"]
        repo = self._get_repository(org_id, state.get("user_id"))
        claims = [Claim.from_dict(d) for d in state.get("claims", [])]
        entities = [Entity.from_dict(d) for d in state.get("entities", [])]

        all_findings: list[Finding] = []
        all_evidence: list[Evidence] = []

        for claim in claims:
            max_retries = 3
            backoff_base = 0.01
            for attempt in range(max_retries):
                try:
                    outcome = self.verification_engine.verify_claim(
                        claim=claim,
                        entities=entities,
                        repository=repo,
                    )
                    all_findings.append(outcome.finding)
                    all_evidence.extend(outcome.evidence_items)
                    if attempt > 0 and repo is not None:
                        repo.record_audit_event(
                            action="verification_retry_success",
                            resource=f"claim:{claim.id}",
                            result="RETRY_SUCCESS",
                            metadata={"attempt": attempt + 1, "max_retries": max_retries},
                        )
                    break
                except RetryableWorkflowError as rwe:
                    if repo is not None:
                        repo.record_audit_event(
                            action="verification_transient_failure",
                            resource=f"claim:{claim.id}",
                            result="RETRYING",
                            metadata={"attempt": attempt + 1, "error": str(rwe)},
                        )
                    if attempt < max_retries - 1:
                        time.sleep(backoff_base * (2 ** attempt))
                    else:
                        raise

        if repo is not None:
            try:
                repo.update_investigation(
                    state["investigation_id"],
                    status="VERIFYING",
                    finding_ids=[f.id for f in all_findings],
                )
            except Exception:
                pass

        return {
            "findings": [f.to_dict() for f in all_findings],
            "finding_ids": [f.id for f in all_findings],
            "evidence_items": [e.to_dict() for e in all_evidence],
            "evidence_ids": [e.id for e in all_evidence],
            "status": "VERIFYING",
            "current_stage": "verification_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 4: Investigation Correlation
    # -----------------------------------------------------------------------
    def correlation_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Construct multi-content entity/claim/payment correlation graph."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))

        content_items = [ContentItem.from_dict(d) for d in state.get("content_items", [])]
        claims = [Claim.from_dict(d) for d in state.get("claims", [])]
        entities = [Entity.from_dict(d) for d in state.get("entities", [])]
        signals = [Signal.from_dict(d) for d in state.get("signals", [])]
        findings = [Finding.from_dict(d) for d in state.get("findings", [])]
        evidence = [Evidence.from_dict(d) for d in state.get("evidence_items", [])]

        correlations = self.correlator.correlate_investigation(
            organization_id=org_id,
            investigation_id=inv_id,
            content_items=content_items,
            claims=claims,
            entities=entities,
            signals=signals,
            findings=findings,
            evidence_items=evidence,
            repository=repo,
        )

        return {
            "correlations": [c.to_dict() for c in correlations],
            "correlation_ids": [c.id for c in correlations],
            "status": "CORRELATING",
            "current_stage": "correlation_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 5: Scam Chain & Taxonomy
    # -----------------------------------------------------------------------
    def scam_chain_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Reconstruct 12-stage scam lifecycle and classify controlled scam patterns."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))

        signals = [Signal.from_dict(d) for d in state.get("signals", [])]
        claims = [Claim.from_dict(d) for d in state.get("claims", [])]
        findings = [Finding.from_dict(d) for d in state.get("findings", [])]
        evidence = [Evidence.from_dict(d) for d in state.get("evidence_items", [])]
        is_educational = state.get("is_educational_warning", False)

        scam_chain = self.reconstructor.reconstruct(
            organization_id=org_id,
            investigation_id=inv_id,
            signals=signals,
            claims=claims,
            findings=findings,
            evidence_items=evidence,
            is_educational_or_warning=is_educational,
            repository=repo,
        )

        if not is_educational:
            scam_patterns = self.classifier.classify(signals, claims, findings)
        else:
            scam_patterns = []

        # Risk posture synthesis
        finding_statuses = {f.status for f in findings}
        signal_types = {s.signal_type for s in signals}

        high_risk_signals = {
            "GUARANTEED_RETURN", "WITHDRAWAL_FEE", "OTP_REQUEST",
            "CREDENTIAL_REQUEST", "THIRD_PARTY_PAYMENT", "UPI_MISMATCH"
        }
        warning_signals = {
            "URGENCY", "SCARCITY", "SOCIAL_MEDIA_SOLICITATION", "UNVERIFIED_APP", "PRESSURE_LANGUAGE"
        }

        if is_educational:
            risk_posture = "SAFE"
        elif "CONTRADICTED" in finding_statuses or bool(signal_types & high_risk_signals) or (
            len(scam_patterns) > 0 and "INVESTMENT_SCAM" in scam_patterns
        ):
            risk_posture = "HIGH_RISK"
        elif "CONFLICTING" in finding_statuses or "OUTDATED" in finding_statuses or bool(signal_types & warning_signals):
            risk_posture = "SUSPICIOUS"
        elif "SUPPORTED" in finding_statuses and all(s in {"SUPPORTED", "INSUFFICIENT_EVIDENCE"} for s in finding_statuses) and not signal_types:
            risk_posture = "SAFE"
        else:
            risk_posture = "UNVERIFIED"

        # Determine if human review is required
        review_required = state.get("review_required", False)
        review_reason = state.get("review_reason", "")
        if not review_required:
            if "CONFLICTING" in finding_statuses or ("CONTRADICTED" in finding_statuses and "SUPPORTED" in finding_statuses):
                review_required = True
                review_reason = "Conflicting authoritative evidence detected across regulatory registries."
            elif risk_posture == "SUSPICIOUS":
                review_required = True
                review_reason = "Suspicious behavioral signals or outdated regulatory credentials require human validation."

        return {
            "scam_chain": [s.to_dict() for s in scam_chain],
            "scam_patterns": scam_patterns,
            "risk_posture": risk_posture,
            "review_required": review_required,
            "review_reason": review_reason,
            "current_stage": "scam_chain_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 6: Guidance & Grievance Routing
    # -----------------------------------------------------------------------
    def guidance_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Generate safe, non-investment guidance and statutory grievance routing dossiers."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))

        signals = [Signal.from_dict(d) for d in state.get("signals", [])]
        findings = [Finding.from_dict(d) for d in state.get("findings", [])]
        scam_patterns = state.get("scam_patterns", [])
        content_items = [ContentItem.from_dict(d) for d in state.get("content_items", [])]

        guidance = self.guidance_engine.generate_guidance(
            signals=signals,
            findings=findings,
            scam_patterns=scam_patterns,
            repository=repo,
        )

        combined_text = " ".join(ci.raw_content for ci in content_items)
        grievance = self.grievance_router.classify_and_route(
            organization_id=org_id,
            investigation_id=inv_id,
            content_text=combined_text,
            signals=signals,
            findings=findings,
            scam_patterns=scam_patterns,
            repository=repo,
        )

        if repo is not None:
            try:
                repo.update_investigation(
                    inv_id,
                    guidance_ids=[g.id for g in guidance],
                )
            except Exception:
                pass

        return {
            "guidance": [g.to_dict() for g in guidance],
            "guidance_ids": [g.id for g in guidance],
            "grievance": grievance.to_dict(),
            "current_stage": "guidance_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 7: Explanation
    # -----------------------------------------------------------------------
    def explanation_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Generate human-readable explainability report with mandatory uncertainty disclosures."""
        signals = [Signal.from_dict(d) for d in state.get("signals", [])]
        claims = [Claim.from_dict(d) for d in state.get("claims", [])]
        entities = [Entity.from_dict(d) for d in state.get("entities", [])]
        findings = [Finding.from_dict(d) for d in state.get("findings", [])]
        scam_chain = [InvestigationStage.from_dict(d) for d in state.get("scam_chain", [])]
        scam_patterns = state.get("scam_patterns", [])
        overall_status = state.get("risk_posture", "UNVERIFIED")

        explanation = self.explainer.explain(
            signals=signals,
            claims=claims,
            entities=entities,
            findings=findings,
            stages=scam_chain,
            scam_patterns=scam_patterns,
            overall_status=overall_status,
        )

        return {
            "explanation": explanation.to_dict(),
            "current_stage": "explanation_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 8: Human Review Gate (Durable LangGraph Interrupt)
    # -----------------------------------------------------------------------
    def review_gate_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Durable review gate pausing execution via interrupt() if supervisory review is required."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))

        # If already reviewed in state, pass through
        if state.get("review_decision"):
            return {
                "status": "FINALIZING",
                "current_stage": "review_gate_node",
                "updated_at": time.time(),
            }

        if state.get("review_required", False):
            # Update investigation status in repository to AWAITING_REVIEW
            if repo is not None:
                try:
                    repo.update_investigation(inv_id, status="AWAITING_REVIEW")
                    repo.record_audit_event(
                        action="workflow_review_requested",
                        resource=f"investigation:{inv_id}",
                        result="AWAITING_REVIEW",
                        metadata={
                            "investigation_id": inv_id,
                            "reason": state.get("review_reason", ""),
                            "posture": state.get("risk_posture", "UNVERIFIED"),
                        },
                    )
                except Exception:
                    pass

            # Physical durable pause in LangGraph
            decision_payload = interrupt({
                "investigation_id": inv_id,
                "organization_id": org_id,
                "reason": state.get("review_reason", "Supervisory review required."),
                "risk_posture": state.get("risk_posture", "UNVERIFIED"),
                "status": "AWAITING_REVIEW",
            })

            # Resumed with decision
            decision_dict: dict[str, Any] = {}
            if isinstance(decision_payload, dict):
                decision_dict = decision_payload
            elif isinstance(decision_payload, str):
                decision_dict = {"action": decision_payload, "reason": "Provided via string resume"}

            # Record review domain entity
            if repo is not None:
                rev = Review(
                    investigation_id=inv_id,
                    reviewer_id=decision_dict.get("reviewer_id", state.get("user_id", "usr_analyst")),
                    action=decision_dict.get("action", "CONFIRM"),
                    reason=decision_dict.get("reason", "Resumed through supervisory gate."),
                    finding_id=decision_dict.get("finding_id"),
                )
                try:
                    repo.record_review(rev)
                    repo.update_investigation(inv_id, status="FINALIZING")
                    repo.record_audit_event(
                        action="workflow_review_submitted",
                        resource=f"investigation:{inv_id}",
                        result=rev.action,
                        metadata={
                            "investigation_id": inv_id,
                            "action": rev.action,
                            "reviewer_id": rev.reviewer_id,
                        },
                    )
                except Exception:
                    pass

            return {
                "review_decision": decision_dict,
                "status": "FINALIZING",
                "current_stage": "review_gate_node",
                "updated_at": time.time(),
            }

        return {
            "status": "FINALIZING",
            "current_stage": "review_gate_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 9: Post-Quantum Trust Finalization
    # -----------------------------------------------------------------------
    def trust_finalization_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Sign completed investigation dossier using NIST FIPS 204 ML-DSA-65 post-quantum cryptography."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))

        # Idempotency check: if already signed and receipt exists, reuse
        existing_receipt_id = state.get("trust_receipt_id")
        if existing_receipt_id:
            return {
                "trust_status": "FINALIZED",
                "current_stage": "trust_finalization_node",
                "updated_at": time.time(),
            }

        trust_receipt_id: Optional[str] = None
        trust_status = "FINALIZED"
        now = time.time()

        if self.trust_binding:
            finding_ids = state.get("finding_ids", [])
            evidence_items = state.get("evidence_items", [])
            evidence_hashes = [e.get("content_hash", "") for e in evidence_items]
            scam_patterns = state.get("scam_patterns", [])
            overall_status = state.get("risk_posture", "UNVERIFIED")

            try:
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

                if repo is not None:
                    try:
                        repo.record_audit_event(
                            action="workflow_trust_finalized",
                            resource=f"investigation:{inv_id}",
                            result="FINALIZED",
                            metadata={
                                "investigation_id": inv_id,
                                "trust_receipt_id": trust_receipt_id,
                                "algorithm": "ML-DSA-65",
                            },
                        )
                    except Exception:
                        pass
            except Exception as e:
                trust_status = "FAILED"
                trust_receipt_id = None
                if repo is not None:
                    try:
                        repo.record_audit_event(
                            action="workflow_trust_failed",
                            resource=f"investigation:{inv_id}",
                            result="FAILED",
                            metadata={"investigation_id": inv_id, "error": str(e)},
                        )
                    except Exception:
                        pass

        return {
            "trust_receipt_id": trust_receipt_id,
            "trust_status": trust_status,
            "current_stage": "trust_finalization_node",
            "updated_at": time.time(),
        }

    # -----------------------------------------------------------------------
    # Node 10: Completion
    # -----------------------------------------------------------------------
    def completion_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Atomically mark investigation as completed in repository and finalize metrics."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        user_id = state["user_id"]
        repo = self._get_repository(org_id, state.get("user_id"))
        now = time.time()

        content_items = state.get("content_items", [])
        claims = state.get("claims", [])
        entities = state.get("entities", [])
        signals = state.get("signals", [])
        correlations = state.get("correlations", [])
        scam_patterns = state.get("scam_patterns", [])
        overall_status = state.get("risk_posture", "UNVERIFIED")
        trust_receipt_id = state.get("trust_receipt_id")

        summary = (
            f"Investigation {inv_id}: Posture={overall_status}. "
            f"Analyzed {len(content_items)} content items, {len(claims)} claims, "
            f"{len(entities)} entities, {len(signals)} signals, {len(correlations)} correlations. "
            f"Identified patterns: {', '.join(scam_patterns) if scam_patterns else 'None'}."
        )

        if repo is not None:
            try:
                repo.update_investigation(
                    inv_id,
                    status="COMPLETED",
                    summary=summary,
                    completed=True,
                    trust_receipt_id=trust_receipt_id,
                )
                repo.record_audit_event(
                    action="workflow_completed",
                    resource=f"investigation:{inv_id}",
                    result=overall_status,
                    metadata={
                        "investigation_id": inv_id,
                        "overall_status": overall_status,
                        "trust_receipt_id": trust_receipt_id,
                        "trust_status": state.get("trust_status", "FINALIZED"),
                    },
                )
            except Exception:
                pass

        return {
            "status": "COMPLETED",
            "current_stage": "completion_node",
            "updated_at": now,
        }

    # -----------------------------------------------------------------------
    # Node 11: Failure Handling
    # -----------------------------------------------------------------------
    def failure_node(self, state: InvestigationWorkflowState) -> dict[str, Any]:
        """Handle unrecoverable node errors while preserving all valid prior evidence."""
        org_id = state["organization_id"]
        inv_id = state["investigation_id"]
        repo = self._get_repository(org_id, state.get("user_id"))
        now = time.time()

        errors = state.get("errors", ["Unknown workflow failure."])
        status = "PARTIALLY_COMPLETED" if state.get("claims") or state.get("entities") else "FAILED"

        if repo is not None:
            try:
                repo.update_investigation(
                    inv_id,
                    status=status,
                    summary=f"Investigation halted due to error: {errors[-1]}",
                )
                repo.record_audit_event(
                    action="workflow_failed",
                    resource=f"investigation:{inv_id}",
                    result=status,
                    metadata={"investigation_id": inv_id, "errors": errors},
                )
            except Exception:
                pass

        return {
            "status": status,
            "current_stage": "failure_node",
            "updated_at": now,
        }

    # -----------------------------------------------------------------------
    # Conditional Routing Functions
    # -----------------------------------------------------------------------
    @staticmethod
    def should_review_condition(state: InvestigationWorkflowState) -> str:
        """Route to review_gate_node if review is required, otherwise route to trust_finalization_node."""
        if state.get("review_required", False) and not state.get("review_decision"):
            return "review_gate_node"
        return "trust_finalization_node"
