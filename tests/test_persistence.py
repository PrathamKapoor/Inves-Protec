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
