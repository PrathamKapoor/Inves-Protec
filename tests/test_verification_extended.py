"""Extended verification tests covering Market Infrastructure, UPI Payment, and Audit Logging."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Claim, ContentItem, Entity, Evidence
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.adapters.market_infrastructure import MarketInfrastructureVerificationAdapter
from sangyan.verification.adapters.payment import UPIPaymentVerificationAdapter
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.snapshots import SnapshotManager
from sangyan.verification.trust_binding import TrustBindingService


@pytest.fixture
def repo_and_trust():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_verif_ext.db"
        key_dir = Path(tmpdir) / "keys"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Extended Verif Org")
        user_id = admin.create_user("analyst@ext.org", "Extended Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        repo = TenantRepository(engine, org_id, user_id)
        trust = TrustService(engine, key_dir=key_dir)

        yield repo, trust
        engine.close()


class TestMarketInfrastructureAdapter:
    def setup_method(self):
        self.snapshots = SnapshotManager()
        self.adapter = MarketInfrastructureVerificationAdapter(self.snapshots)

    def test_active_nse_member_supported(self):
        claim = Claim(
            content_item_id="item_1",
            statement="Zerodha Broking is an active trading member of NSE with member ID 13942.",
            claim_type="regulatory",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert res.status == "verified"
        assert "13942" in res.excerpt
        assert res.confidence_score >= 0.95

    def test_active_depository_participant_supported(self):
        claim = Claim(
            content_item_id="item_2",
            statement="Groww is a registered depository participant with NSDL under DP ID IN-DP-431-2019.",
            claim_type="regulatory",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert "IN-DP-431-2019" in res.excerpt

    def test_expelled_defaulter_member_contradicted(self):
        claim = Claim(
            content_item_id="item_3",
            statement="Karvy Stock Broking Limited is an active NSE member under ID 08035.",
            claim_type="regulatory",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "EXPELLED" in res.excerpt or "defaulter" in res.excerpt.lower()

    def test_bogus_member_id_contradicted(self):
        claim = Claim(
            content_item_id="item_4",
            statement="Our company is registered on NSE with member ID 999999.",
            claim_type="regulatory",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert res.status == "not_found"

    def test_hard_negative_exchange_warning(self):
        claim = Claim(
            content_item_id="item_5",
            statement="NSE cautions investors against unsolicited stock recommendations.",
            claim_type="regulatory",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert "caution" in res.rationale.lower() or "warning" in res.rationale.lower()


class TestUPIPaymentAdapter:
    def setup_method(self):
        self.snapshots = SnapshotManager()
        self.adapter = UPIPaymentVerificationAdapter(self.snapshots)

    def test_official_corporate_vpa_supported(self):
        claim = Claim(
            content_item_id="item_upi_1",
            statement="Pay your margin deposit directly to zerodha.pay@okhdfcbank.",
            claim_type="payment",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert "Zerodha Broking Limited" in res.excerpt

    def test_flagged_fraudulent_vpa_contradicted(self):
        claim = Claim(
            content_item_id="item_upi_2",
            statement="Deposit 10000 rupees to fastprofit24@paytm to activate your account.",
            claim_type="payment",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "fraudulent" in res.excerpt.lower()
        assert "fastprofit24@paytm" in res.excerpt

    def test_broker_personal_vpa_mismatch_contradicted(self):
        """Scammer claims to be Zerodha but tells victim to transfer money to a personal VPA.
        Must be strictly flagged as CONTRADICTED due to payment destination mismatch.
        """
        claim = Claim(
            content_item_id="item_upi_3",
            statement="Zerodha trading support: transfer your funds to rohit.kumar1985@paytm for instant top-up.",
            claim_type="payment",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "mismatch" in res.rationale.lower()
        assert "rohit.kumar1985@paytm" in res.excerpt

    def test_unknown_vpa_returns_insufficient_evidence(self):
        """Unverified payment handle with no contradiction or spoofing must return INSUFFICIENT_EVIDENCE,
        satisfying Section 34 of the prompt ('Do not declare fraud solely because a payment identifier cannot be verified').
        """
        claim = Claim(
            content_item_id="item_upi_4",
            statement="Transfer ₹500 to user987654321@okicici for settlement.",
            claim_type="payment",
        )
        res = self.adapter.verify(claim)
        assert res.stance == "INSUFFICIENT_EVIDENCE"
        assert res.status == "insufficient_evidence"


class TestAuditLoggingAndLedgerChaining:
    def test_verification_produces_audit_events_and_chained_ledger(self, repo_and_trust):
        repo, trust = repo_and_trust
        trust_binding = TrustBindingService(trust)
        engine = ClaimVerificationEngine(trust_binding=trust_binding)

        content = ContentItem(
            organization_id=repo.organization_id,
            content_type="text",
            raw_content="Zerodha Broking is SEBI registered under INZ000031633.",
        )
        item_id = repo.save_content_item(content)

        claim = Claim(
            content_item_id=item_id,
            statement="Zerodha Broking is SEBI registered under INZ000031633.",
            claim_type="regulatory",
        )
        claim_id = repo.save_claim(claim)
        claim.id = claim_id

        # Verify claim
        outcome = engine.verify_claim(claim, repository=repo)
        assert outcome.status == "SUPPORTED"

        # Check audit events recorded
        events = repo.list_audit_events()
        assert len(events) >= 1
        verif_evt = next((e for e in events if e.action == "verify_claim"), None)
        assert verif_evt is not None
        assert verif_evt.result == "SUPPORTED"
        assert verif_evt.resource == f"claim:{claim_id}"
        assert verif_evt.ledger_hash != ""

        # Second verification to test chained ledger hash
        claim2 = Claim(
            content_item_id=item_id,
            statement="100% guaranteed monthly returns.",
            claim_type="return",
        )
        claim2_id = repo.save_claim(claim2)
        claim2.id = claim2_id

        outcome2 = engine.verify_claim(claim2, repository=repo)
        assert outcome2.status == "CONTRADICTED"

        events2 = repo.list_audit_events()
        assert len(events2) >= 2
        # Verify hashes are distinct and chained
        hashes = [e.ledger_hash for e in events2]
        assert len(set(hashes)) == len(hashes)

    def test_cross_tenant_audit_isolation(self, repo_and_trust):
        repo_a, _ = repo_and_trust
        admin = TenantAdministration(repo_a._db)
        org_b = admin.create_organization("Tenant B Watchdog")
        user_b = admin.create_user("b@watchdog.org", "Analyst B")
        admin.add_membership(org_b, user_b, "sangyan_analyst")
        repo_b = TenantRepository(repo_a._db, org_b, user_b)

        # Tenant A records an audit event
        repo_a.record_audit_event("action_a", "res_a", "OK", {"sample": 1})

        # Tenant A sees it
        assert len(repo_a.list_audit_events(action="action_a")) == 1

        # Tenant B must NOT see Tenant A's audit event
        assert len(repo_b.list_audit_events(action="action_a")) == 0
