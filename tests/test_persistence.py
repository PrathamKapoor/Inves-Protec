"""Unit tests for TenantRepository, administration, and tenant isolation."""
import tempfile
from pathlib import Path

import pytest

from sangyan.core.errors import NotFoundError, PermissionDeniedError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Claim, ContentItem, Investigation, Review, Signal
from sangyan.tenancy.repository import TenantAdministration, TenantRepository


@pytest.fixture
def db_with_schema():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sangyan_persistence.db"
        engine = SQLiteDatabaseEngine(db_path)
        runner = MigrationRunner(engine)
        runner.migrate()
        yield engine
        engine.close()


@pytest.fixture
def seeded_tenancy(db_with_schema):
    admin = TenantAdministration(db_with_schema)
    org1 = admin.create_organization("Bharat Retail Investors Org")
    org2 = admin.create_organization("Independent Watchdog Org")

    user1 = admin.create_user("analyst1@bharat.in", "Analyst One")
    user2 = admin.create_user("analyst2@watchdog.in", "Analyst Two")
    viewer = admin.create_user("viewer@bharat.in", "Viewer User")

    admin.add_membership(org1, user1, "sangyan_analyst")
    admin.add_membership(org2, user2, "sangyan_analyst")
    admin.add_membership(org1, viewer, "sangyan_viewer")

    return {
        "engine": db_with_schema,
        "org1": org1,
        "org2": org2,
        "user1": user1,
        "user2": user2,
        "viewer": viewer,
    }


class TestTenantRepository:
    def test_tenant_isolation(self, seeded_tenancy):
        repo1 = TenantRepository(seeded_tenancy["engine"], seeded_tenancy["org1"], seeded_tenancy["user1"])
        repo2 = TenantRepository(seeded_tenancy["engine"], seeded_tenancy["org2"], seeded_tenancy["user2"])

        # Org1 saves a content item
        item = ContentItem(
            content_type="text",
            raw_content="Suspicious WhatsApp investment offer promising 50% ROI",
            organization_id=seeded_tenancy["org1"],
        )
        item_id = repo1.save_content_item(item)

        # Org1 can read it
        fetched = repo1.get_content_item(item_id)
        assert fetched.id == item_id

        # Org2 cannot read Org1's content item
        with pytest.raises(NotFoundError):
            repo2.get_content_item(item_id)

    def test_permission_enforcement(self, seeded_tenancy):
        # Viewer role does not have investigation:create permission
        viewer_repo = TenantRepository(seeded_tenancy["engine"], seeded_tenancy["org1"], seeded_tenancy["viewer"])
        item = ContentItem(
            content_type="text",
            raw_content="Attempt by viewer",
            organization_id=seeded_tenancy["org1"],
        )
        with pytest.raises(PermissionDeniedError):
            viewer_repo.save_content_item(item)

    def test_investigation_and_review_lifecycle(self, seeded_tenancy):
        repo = TenantRepository(seeded_tenancy["engine"], seeded_tenancy["org1"], seeded_tenancy["user1"])

        item = ContentItem(
            content_type="text",
            raw_content="SEBI registered ABC Wealth guarantees 40% returns. Pay ₹10,000 today.",
            organization_id=seeded_tenancy["org1"],
        )
        item_id = repo.save_content_item(item)

        claim1 = Claim(
            content_item_id=item_id,
            statement="ABC Wealth is SEBI registered",
            claim_type="regulatory",
            status="UNVERIFIED",
        )
        claim2 = Claim(
            content_item_id=item_id,
            statement="Guaranteed 40% returns",
            claim_type="return",
            status="CONTRADICTED",
        )
        c1_id = repo.save_claim(claim1)
        c2_id = repo.save_claim(claim2)

        sig = Signal(
            content_item_id=item_id,
            signal_type="GUARANTEED_RETURN",
            excerpt="Guaranteed 40% returns",
            detection_basis="Explicit promise of guaranteed return",
        )
        sig_id = repo.save_signal(sig)

        inv = Investigation(
            organization_id=seeded_tenancy["org1"],
            user_id=seeded_tenancy["user1"],
            content_item_id=item_id,
            claim_ids=[c1_id, c2_id],
            signal_ids=[sig_id],
            status="AWAITING_REVIEW",
        )
        inv_id = repo.save_investigation(inv)

        # Read investigation
        fetched_inv = repo.get_investigation(inv_id)
        assert fetched_inv.id == inv_id
        assert fetched_inv.status == "AWAITING_REVIEW"
        assert len(fetched_inv.claim_ids) == 2

        # Record human review decision
        rev = Review(
            investigation_id=inv_id,
            reviewer_id=seeded_tenancy["user1"],
            action="CONFIRM",
            reason="Confirmed high-risk guaranteed return violation and unregistered entity.",
        )
        rev_id = repo.record_review(rev)
        assert rev_id.startswith("rev_")

        # List reviews for investigation
        reviews = repo.list_reviews_for_investigation(inv_id)
        assert len(reviews) == 1
        assert reviews[0].id == rev_id

        # Update investigation
        repo.update_investigation(inv_id, status="COMPLETED", summary="Investigation completed", completed=True)
        updated_inv = repo.get_investigation(inv_id)
        assert updated_inv.status == "COMPLETED"
        assert updated_inv.summary == "Investigation completed"
        assert updated_inv.completed_at is not None

        # List investigations
        all_invs = repo.list_investigations()
        assert len(all_invs) == 1
        assert all_invs[0].id == inv_id

    def test_full_repository_crud(self, seeded_tenancy):
        repo = TenantRepository(seeded_tenancy["engine"], seeded_tenancy["org1"], seeded_tenancy["user1"])

        # Content item and claims
        item = ContentItem(
            content_type="text",
            raw_content="Invest with ABC Trading, SEBI reg INZ000123456, 100% guarantee",
            organization_id=seeded_tenancy["org1"],
        )
        item_id = repo.save_content_item(item)
        c1 = Claim(content_item_id=item_id, statement="ABC Trading is SEBI registered", claim_type="regulatory")
        c2 = Claim(content_item_id=item_id, statement="100% guarantee", claim_type="return")
        c1_id = repo.save_claim(c1)
        c2_id = repo.save_claim(c2)

        claims = repo.list_claims_for_content(item_id)
        assert len(claims) == 2

        # Signals
        s1 = Signal(content_item_id=item_id, signal_type="GUARANTEED_RETURN", excerpt="100% guarantee")
        s1_id = repo.save_signal(s1)
        fetched_s = repo.get_signal(s1_id)
        assert fetched_s.id == s1_id
        signals = repo.list_signals_for_content(item_id)
        assert len(signals) == 1

        # Entities
        from sangyan.domain.models import Entity, Source, Evidence, Finding, ActionGuidance
        ent = Entity(name="ABC Trading", entity_type="BROKER", registration_number="INZ000123456")
        ent_id = repo.save_entity(ent)
        fetched_ent = repo.get_entity(ent_id)
        assert fetched_ent.name == "ABC Trading"
        assert len(repo.list_entities()) == 1

        # Sources
        src = Source(name="SEBI Registered Brokers Directory", authority_tier="T0_REGULATOR", url="https://www.sebi.gov.in")
        src_id = repo.save_source(src)
        fetched_src = repo.get_source(src_id)
        assert fetched_src.name == "SEBI Registered Brokers Directory"
        assert len(repo.list_sources()) == 1

        # Evidence
        evi = Evidence(source_id=src_id, claim_id=c1_id, excerpt="No such registration found", stance="CONTRADICTS")
        evi_id = repo.save_evidence(evi)
        fetched_evi = repo.get_evidence(evi_id)
        assert fetched_evi.claim_id == c1_id
        assert len(repo.list_evidence_for_claim(c1_id)) == 1

        # Findings
        fnd = Finding(
            claim_id=c1_id,
            statement="Entity is not registered with SEBI",
            status="CONTRADICTED",
            evidence_refs=[evi_id],
            rationale="Registration number does not exist in SEBI directory",
        )
        fnd_id = repo.save_finding(fnd)
        fetched_fnd = repo.get_finding(fnd_id)
        assert fetched_fnd.status == "CONTRADICTED"
        assert len(repo.list_findings_for_claim(c1_id)) == 1

        # Action Guidance
        gd = ActionGuidance(category="GRIEVANCE_SCORES", title="File SCORES Complaint", description="Report unauthorized broker to SEBI SCORES portal", official_url="https://scores.sebi.gov.in")
        gd_id = repo.save_guidance(gd)
        fetched_gd = repo.get_guidance(gd_id)
        assert fetched_gd.category == "GRIEVANCE_SCORES"
        assert len(repo.list_guidance("GRIEVANCE_SCORES")) == 1

