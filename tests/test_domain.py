"""Unit tests for SANGYAN 10-object investor-safety domain model."""
import pytest

from sangyan.domain.models import (
    AUTHORITY_TIERS,
    CLAIM_STATUSES,
    ENTITY_TYPES,
    EVIDENCE_STANCES,
    GUIDANCE_CATEGORIES,
    INVESTIGATION_STATUSES,
    REVIEW_ACTIONS,
    SIGNAL_TYPES,
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


class TestConfidenceVector:
    def test_valid_confidence(self):
        cv = ConfidenceVector(
            analytical_support=0.9,
            evidence_completeness=0.8,
            source_authority_weight=1.0,
            peer_agreement=0.85,
        )
        assert not cv.validate()
        assert cv.overall == 0.8
        d = cv.to_dict()
        cv2 = ConfidenceVector.from_dict(d)
        assert cv2.overall == cv.overall

    def test_invalid_range(self):
        cv = ConfidenceVector(
            analytical_support=1.5,
            evidence_completeness=-0.1,
            source_authority_weight=0.5,
        )
        errors = cv.validate()
        assert len(errors) == 2


class TestContentItem:
    def test_valid_text_item(self):
        item = ContentItem(
            content_type="text",
            raw_content="SEBI registered ABC Wealth guarantees 30% monthly profit.",
            organization_id="org_test",
        )
        assert not item.validate()
        d = item.to_dict()
        assert d["content_type"] == "text"
        item2 = ContentItem.from_dict(d)
        assert item2.raw_content == item.raw_content

    def test_invalid_content_type(self):
        item = ContentItem(
            content_type="video_stream",
            raw_content="sample",
            organization_id="org_test",
        )
        errors = item.validate()
        assert any("content_type" in e for e in errors)

    def test_empty_raw_content(self):
        item = ContentItem(
            content_type="text",
            raw_content="",
            organization_id="org_test",
        )
        assert any("raw_content cannot be empty" in e for e in item.validate())


class TestClaim:
    def test_valid_claim(self):
        claim = Claim(
            content_item_id="content_123",
            statement="ABC Wealth is approved by SEBI.",
            claim_type="regulatory",
            status="UNVERIFIED",
        )
        assert not claim.validate()

    def test_reject_binary_status(self):
        claim = Claim(
            content_item_id="content_123",
            statement="ABC Wealth is approved by SEBI.",
            status="TRUE",  # Invalid! Must be one of CLAIM_STATUSES
        )
        errors = claim.validate()
        assert any("status" in e for e in errors)

    def test_all_official_statuses(self):
        for st in CLAIM_STATUSES:
            c = Claim(content_item_id="c1", statement="statement", status=st)
            assert not c.validate()


class TestEntity:
    def test_valid_broker_entity(self):
        ent = Entity(
            name="Zerodha Broking Limited",
            entity_type="BROKER",
            aliases=["Zerodha"],
            registration_number="INZ000031633",
        )
        assert not ent.validate()
        d = ent.to_dict()
        ent2 = Entity.from_dict(d)
        assert ent2.name == ent.name

    def test_invalid_entity_type(self):
        ent = Entity(name="Unknown", entity_type="CRYPTOCURRENCY_COIN")
        assert any("entity_type" in e for e in ent.validate())


class TestSource:
    def test_valid_source_t0(self):
        src = Source(
            name="Securities and Exchange Board of India",
            authority_tier="T0_REGULATOR",
            url="https://www.sebi.gov.in",
            publisher="SEBI",
            published_at=1704067200.0,
            valid_until=1735689600.0,
        )
        assert not src.validate()

    def test_invalid_freshness_dates(self):
        src = Source(
            name="SEBI",
            authority_tier="T0_REGULATOR",
            published_at=1735689600.0,
            valid_until=1704067200.0,  # invalid: expired before published!
        )
        assert any("valid_until cannot be earlier than published_at" in e for e in src.validate())


class TestEvidence:
    def test_valid_evidence(self):
        ev = Evidence(
            source_id="src_sebi",
            claim_id="claim_001",
            excerpt="SEBI circular SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/01 prohibits guaranteed returns.",
            stance="CONTRADICTS",
            relevance=0.95,
        )
        assert not ev.validate()

    def test_invalid_stance(self):
        ev = Evidence(
            source_id="src_1",
            claim_id="cl_1",
            excerpt="sample",
            stance="ABSOLUTELY_FALSE",  # invalid
        )
        assert any("stance" in e for e in ev.validate())


class TestSignal:
    def test_valid_guaranteed_return_signal(self):
        sig = Signal(
            content_item_id="c_1",
            signal_type="GUARANTEED_RETURN",
            excerpt="100% risk free guaranteed 40% monthly returns",
            detection_basis="Explicit promise of guaranteed profit without market risk",
            confidence=0.98,
        )
        assert not sig.validate()

    def test_all_20_signal_types_valid(self):
        assert len(SIGNAL_TYPES) >= 20
        for st in SIGNAL_TYPES:
            sig = Signal(content_item_id="c_1", signal_type=st, excerpt="sample text")
            assert not sig.validate()


class TestFinding:
    def test_finding_requires_evidence_for_contradicted(self):
        f = Finding(
            claim_id="cl_1",
            statement="ABC Wealth is registered with SEBI",
            status="CONTRADICTED",
            evidence_refs=[],  # Missing evidence!
        )
        errors = f.validate()
        assert any("requires at least one evidence_ref" in e for e in errors)

    def test_valid_finding_with_evidence(self):
        f = Finding(
            claim_id="cl_1",
            statement="ABC Wealth is registered with SEBI",
            status="CONTRADICTED",
            evidence_refs=["evid_001"],
            source_refs=["src_sebi"],
            rationale="Query against SEBI recognized intermediary database returned zero records.",
        )
        assert not f.validate()


class TestActionGuidance:
    def test_valid_action_guidance(self):
        guidance = ActionGuidance(
            category="GRIEVANCE_SCORES",
            title="Lodge complaint on SEBI SCORES portal",
            description="If your registered intermediary fails to resolve your grievance within 30 days, escalate to SCORES.",
            official_url="https://scores.sebi.gov.in",
            priority=1,
            urgency=True,
        )
        assert not guidance.validate()
        d = guidance.to_dict()
        g2 = ActionGuidance.from_dict(d)
        assert g2.title == guidance.title


class TestInvestigation:
    def test_valid_investigation(self):
        inv = Investigation(
            organization_id="org_retail",
            user_id="usr_001",
            content_item_id="c_001",
            claim_ids=["claim_001", "claim_002"],
            signal_ids=["sig_001"],
            finding_ids=["find_001"],
            guidance_ids=["act_001"],
            status="ANALYZING",
        )
        assert not inv.validate()


class TestReview:
    def test_valid_review(self):
        rev = Review(
            investigation_id="inv_001",
            reviewer_id="usr_supervisor",
            action="CONFIRM",
            reason="Verified SEBI public database manually; entity non-existent.",
        )
        assert not rev.validate()

    def test_invalid_action(self):
        rev = Review(
            investigation_id="inv_001",
            reviewer_id="usr_1",
            action="AUTO_APPROVE",  # Invalid action
        )
        assert any("action" in e for e in rev.validate())
