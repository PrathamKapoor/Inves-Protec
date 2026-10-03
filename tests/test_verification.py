"""Unit, integration, and security tests for SANGYAN authoritative verification and trust binding."""
import tempfile
import time
from pathlib import Path

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Claim, ContentItem, Entity
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.adapters.circulars import CircularsVerificationAdapter
from sangyan.verification.adapters.mca import MCAVerificationAdapter
from sangyan.verification.adapters.official_domains import OfficialDomainsVerificationAdapter
from sangyan.verification.adapters.sebi import SEBIVerificationAdapter
from sangyan.verification.cache import RateLimiter, VerificationCache
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.snapshots import SnapshotManager, create_snapshot
from sangyan.verification.sources import AuthoritativeSourceRegistry
from sangyan.verification.trust_binding import TrustBindingService


@pytest.fixture
def repo_and_trust():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_verif.db"
        key_dir = Path(tmpdir) / "keys"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Verification Test Org")
        user_id = admin.create_user("verif@test.org", "Verification Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        repo = TenantRepository(engine, org_id, user_id)
        trust = TrustService(engine, key_dir=key_dir)

        yield repo, trust
        engine.close()


class TestSourceRegistryAndSnapshots:
    def test_registry_lookups_and_domain_allowlist(self):
        reg = AuthoritativeSourceRegistry()
        sebi_src = reg.get_source("src_sebi_intermediaries")
        assert sebi_src is not None
        assert sebi_src.authority_tier == "T0_REGULATOR"
        assert reg.is_domain_allowed("src_sebi_intermediaries", "sebi.gov.in")
        assert reg.is_domain_allowed("src_sebi_intermediaries", "www.sebi.gov.in")
        assert not reg.is_domain_allowed("src_sebi_intermediaries", "fake-sebi.xyz")

    def test_snapshot_integrity_verification(self):
        mgr = SnapshotManager()
        snap = mgr.get_snapshot("src_sebi_intermediaries")
        assert snap is not None
        assert snap.verify_integrity() is True

        # Tampering with snapshot records must cause integrity check to fail
        snap.records[0]["entity_name"] = "Tampered Name"
        assert snap.verify_integrity() is False

    def test_cache_and_rate_limiter(self):
        cache = VerificationCache(default_ttl_sec=1)
        key = cache.make_key("src_test", "INZ123456")
        cache.set(key, {"verified": True}, "src_test", ttl_sec=1)

        assert cache.get(key) == {"verified": True}
        time.sleep(1.1)
        # Entry must expire
        assert cache.get(key) is None

        limiter = RateLimiter(default_requests_per_sec=2)
        assert limiter.allow_request("src_test", max_rate=2) is True
        assert limiter.allow_request("src_test", max_rate=2) is True
        assert limiter.allow_request("src_test", max_rate=2) is False


class TestAuthoritativeAdapters:
    def setup_method(self):
        self.snapshots = SnapshotManager()
        self.sebi_adapter = SEBIVerificationAdapter(self.snapshots)
        self.mca_adapter = MCAVerificationAdapter(self.snapshots)
        self.circulars_adapter = CircularsVerificationAdapter(self.snapshots)
        self.domains_adapter = OfficialDomainsVerificationAdapter(self.snapshots)

    def test_sebi_active_broker_supported(self):
        claim = Claim(
            content_item_id="item_1",
            statement="Zerodha Broking Limited is SEBI registered under INZ000031633.",
            claim_type="regulatory",
        )
        res = self.sebi_adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert res.status == "verified"
        assert "INZ000031633" in res.excerpt
        assert res.confidence_score >= 0.95

    def test_sebi_expired_outdated(self):
        claim = Claim(
            content_item_id="item_2",
            statement="Fraudulent Wealth Management is registered with SEBI under INZ000999999.",
            claim_type="regulatory",
        )
        res = self.sebi_adapter.verify(claim)
        assert res.stance == "OUTDATED"
        assert "expired" in res.rationale.lower()

    def test_sebi_suspended_contradicted(self):
        claim = Claim(
            content_item_id="item_3",
            statement="Shady Trades India Limited is an active SEBI broker under INZ000888888.",
            claim_type="regulatory",
        )
        res = self.sebi_adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "suspended" in res.excerpt.lower()

    def test_sebi_bogus_reg_no_contradicted(self):
        claim = Claim(
            content_item_id="item_4",
            statement="Invest with ABC Trading, verified SEBI license INZ000111222.",
            claim_type="regulatory",
        )
        res = self.sebi_adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert res.status == "not_found"

    def test_sebi_unidentified_insufficient_evidence(self):
        claim = Claim(
            content_item_id="item_5",
            statement="Random Unnamed Advisory is authorized to provide stock tips.",
            claim_type="regulatory",
        )
        res = self.sebi_adapter.verify(claim)
        assert res.stance == "INSUFFICIENT_EVIDENCE"

    def test_mca_active_cin_supported(self):
        claim = Claim(
            content_item_id="item_6",
            statement="Registered under MCA with CIN U74999MH2016PTC288123 in Maharashtra.",
            claim_type="regulatory",
        )
        res = self.mca_adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert "APEX CAPITAL" in res.excerpt

    def test_mca_struck_off_outdated(self):
        claim = Claim(
            content_item_id="item_7",
            statement="Bogus Multi Trading is active under CIN U12345DL2010PTC999999.",
            claim_type="regulatory",
        )
        res = self.mca_adapter.verify(claim)
        assert res.stance == "OUTDATED"
        assert "struck_off" in res.excerpt.lower()

    def test_circulars_guaranteed_return_contradicted(self):
        claim = Claim(
            content_item_id="item_8",
            statement="We guarantee 40% monthly returns with zero risk on all investments.",
            claim_type="return",
        )
        res = self.circulars_adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "SEBI/HO/MIRSD" in res.excerpt

    def test_circulars_otp_sharing_contradicted(self):
        claim = Claim(
            content_item_id="item_9",
            statement="Share your OTP with our adviser to activate algorithm trading.",
            claim_type="payment",
        )
        res = self.circulars_adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "SEBI/HO/ISD" in res.excerpt

    def test_domains_official_supported(self):
        claim = Claim(
            content_item_id="item_10",
            statement="Access your trading account at https://zerodha.com/login.",
            claim_type="other",
        )
        res = self.domains_adapter.verify(claim)
        assert res.stance == "SUPPORTED"
        assert "official domain" in res.excerpt.lower()

    def test_domains_phishing_lookalike_contradicted(self):
        claim = Claim(
            content_item_id="item_11",
            statement="Download official profit terminal at http://zerodha-profit.cc/app.",
            claim_type="other",
        )
        res = self.domains_adapter.verify(claim)
        assert res.stance == "CONTRADICTED"
        assert "lookalike" in res.excerpt.lower()


class TestConflictResolutionAndTrust:
    def test_conflict_resolution_opposing_authoritative_sources(self):
        """When two authoritative sources disagree, engine must emit CONFLICTING with dual evidence."""
        engine = ClaimVerificationEngine()

        # Mock Adapter A saying SUPPORTED
        class MockAdapterA(VerificationAdapter):
            def __init__(self):
                super().__init__("adapter_a", "src_a")
            def supports(self, claim): return True
            def verify(self, claim, entity=None, context=None):
                return AdapterResult("adapter_a", "src_a", "verified", "SUPPORTED", "Source A: Active registration", "Active according to Exchange")

        # Mock Adapter B saying CONTRADICTED
        class MockAdapterB(VerificationAdapter):
            def __init__(self):
                super().__init__("adapter_b", "src_b")
            def supports(self, claim): return True
            def verify(self, claim, entity=None, context=None):
                return AdapterResult("adapter_b", "src_b", "verified", "CONTRADICTED", "Source B: Registration cancelled", "Cancelled under regulatory enquiry")

        engine.adapters = [MockAdapterA(), MockAdapterB()]

        claim = Claim(content_item_id="item_conflict", statement="Entity X is authorized to trade.", claim_type="regulatory")
        outcome = engine.verify_claim(claim)

        assert outcome.status == "CONFLICTING"
        assert outcome.finding.status == "CONFLICTING"
        assert "CONFLICTING" in outcome.finding.rationale
        assert len(outcome.evidence_items) == 2
        stances = {e.stance for e in outcome.evidence_items}
        assert "SUPPORTS" in stances
        assert "CONTRADICTS" in stances

    def test_end_to_end_verification_with_trust_receipt(self, repo_and_trust):
        repo, trust = repo_and_trust
        trust_binding = TrustBindingService(trust)
        engine = ClaimVerificationEngine(trust_binding=trust_binding)

        # 1. Ingest content item
        item = ContentItem(
            organization_id=repo.organization_id,
            content_type="text",
            raw_content="Invest with Zerodha Broking Limited, SEBI reg INZ000031633. 100% guaranteed monthly returns.",
        )
        item_id = repo.save_content_item(item)
        item.id = item_id

        # 2. Decompose claims
        c1 = Claim(content_item_id=item_id, statement="Zerodha Broking Limited is SEBI registered under INZ000031633.", claim_type="regulatory")
        c2 = Claim(content_item_id=item_id, statement="100% guaranteed monthly returns.", claim_type="return")
        c1_id = repo.save_claim(c1)
        c2_id = repo.save_claim(c2)
        c1.id = c1_id
        c2.id = c2_id

        # 3. Verify Claim 1 (SEBI registered)
        outcome1 = engine.verify_claim(c1, repository=repo)
        assert outcome1.status == "SUPPORTED"
        assert outcome1.trust_receipt_id is not None
        assert outcome1.finding.status == "SUPPORTED"
        assert len(outcome1.evidence_items) >= 1

        # 4. Verify Claim 2 (Guaranteed returns)
        outcome2 = engine.verify_claim(c2, repository=repo)
        assert outcome2.status == "CONTRADICTED"
        assert outcome2.trust_receipt_id is not None
        assert outcome2.finding.status == "CONTRADICTED"
        assert "SEBI/HO/MIRSD" in outcome2.finding.rationale

        # 5. Verify cryptographic integrity via ML-DSA-65 post-quantum signature
        from sangyan.trust.receipt import TrustReceipt
        row = repo._db.query_one("SELECT * FROM sangyan_trust_receipts WHERE id=?", (outcome1.trust_receipt_id,))
        receipt = TrustReceipt.from_dict(row)

        is_valid = trust_binding.verify_finding_integrity(
            receipt, outcome1.finding, c1, outcome1.evidence_items
        )
        assert is_valid is True

        # 6. Tamper check: altering finding statement must cause verification to fail
        outcome1.finding.statement = "Tampered Statement"
        is_tampered_valid = trust_binding.verify_finding_integrity(
            receipt, outcome1.finding, c1, outcome1.evidence_items
        )
        assert is_tampered_valid is False

    def test_cross_tenant_evidence_isolation(self, repo_and_trust):
        """Tenant B must not be able to read or query Tenant A's evidence or findings."""
        from sangyan.core.errors import NotFoundError
        repo_a, _ = repo_and_trust

        # Create Tenant B
        admin = TenantAdministration(repo_a._db)
        org_b = admin.create_organization("Tenant B Watchdog")
        user_b = admin.create_user("analyst_b@watchdog.org", "Analyst B")
        admin.add_membership(org_b, user_b, "sangyan_analyst")
        repo_b = TenantRepository(repo_a._db, org_b, user_b)

        # Tenant A ingests and verifies
        engine = ClaimVerificationEngine()
        item = ContentItem(organization_id=repo_a.organization_id, content_type="text", raw_content="Advisory claim")
        item_id = repo_a.save_content_item(item)
        c = Claim(content_item_id=item_id, statement="INZ000031633 registration", claim_type="regulatory")
        c_id = repo_a.save_claim(c)
        c.id = c_id

        outcome = engine.verify_claim(c, repository=repo_a)
        assert len(outcome.evidence_items) >= 1
        ev_id = outcome.evidence_items[0].id
        fnd_id = outcome.finding.id

        # Tenant A can read
        assert repo_a.get_evidence(ev_id).id == ev_id
        assert repo_a.get_finding(fnd_id).id == fnd_id

        # Tenant B must be denied with NotFoundError
        with pytest.raises(NotFoundError):
            repo_b.get_evidence(ev_id)
        with pytest.raises(NotFoundError):
            repo_b.get_finding(fnd_id)

    def test_adversarial_name_spoofing_does_not_override_contradictory_reg_no(self):
        """Scammer uses real broker name 'Zerodha' with a fake registration number 'INZ000000000'.
        The exact contradictory registration number must take precedence and flag CONTRADICTED.
        """
        snapshots = SnapshotManager()
        adapter = SEBIVerificationAdapter(snapshots)

        spoofed_claim = Claim(
            content_item_id="item_spoof",
            statement="Zerodha Broking is licensed under registration number INZ000000000.",
            claim_type="regulatory",
        )
        res = adapter.verify(spoofed_claim)
        assert res.stance == "CONTRADICTED"
        assert res.status == "not_found"
        assert "INZ000000000" in res.excerpt

