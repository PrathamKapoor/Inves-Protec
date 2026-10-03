"""Unit and integration tests for sangyan.intelligence engine."""
import tempfile
from pathlib import Path

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import ContentItem
from sangyan.intelligence.claims import ClaimExtractor
from sangyan.intelligence.entities import EntityResolver
from sangyan.intelligence.language import LanguageDetector
from sangyan.intelligence.pipeline import ContentIntelligenceEngine
from sangyan.intelligence.signals import SignalDetector
from sangyan.tenancy.repository import TenantAdministration, TenantRepository


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_intel.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Intelligence Test Org")
        user_id = admin.create_user("analyst@intel.test", "Intel Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        yield TenantRepository(engine, org_id, user_id)
        engine.close()


class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_english(self):
        text = "This is a legitimate stock market advisory newsletter for retail investors."
        res = self.detector.detect(text)
        assert res.primary_language == "en"
        assert res.script == "Latn"
        assert res.confidence > 0.7

    def test_detect_hindi_devanagari(self):
        text = "शेयर बाजार में निवेश करने के लिए यह सबसे बेहतरीन योजना है। आपको अच्छा मुनाफा मिलेगा।"
        res = self.detector.detect(text)
        assert res.primary_language == "hi"
        assert res.script == "Deva"
        assert res.confidence > 0.7

    def test_detect_marathi_devanagari(self):
        text = "शेअर बाजारात गुंतवणूक करण्यासाठी ही सर्वात उत्तम योजना आहे. तुम्हाला चांगला नफा मिळेल आणि पैसे सुरक्षित राहतील."
        res = self.detector.detect(text)
        assert res.primary_language == "mr"
        assert res.script == "Deva"
        assert res.confidence > 0.6

    def test_detect_hinglish(self):
        text = "Aapko guaranteed 50% profit milega. Jaldi se join karo dosto, aaj hi apna khata kholo aur paisa kamao."
        res = self.detector.detect(text)
        assert res.primary_language == "hinglish"
        assert res.is_multilingual is True

    def test_detect_indic_scripts(self):
        # Gujarati
        gu_text = "શેરબજારમાં રોકાણ માટે શ્રેષ્ઠ યોજના."
        assert self.detector.detect(gu_text).primary_language == "gu"

        # Bengali
        bn_text = "শেয়ার বাজারে বিনিয়োগের জন্য সেরা পরিকল্পনা।"
        assert self.detector.detect(bn_text).primary_language == "bn"

        # Tamil
        ta_text = "பங்குச் சந்தையில் முதலீடு செய்வதற்கான சிறந்த திட்டம்."
        assert self.detector.detect(ta_text).primary_language == "ta"

    def test_empty_input(self):
        res = self.detector.detect("")
        assert res.primary_language == "unknown"
        assert res.confidence == 0.0


class TestClaimExtractor:
    def setup_method(self):
        self.extractor = ClaimExtractor()

    def test_decompose_compound_claims(self):
        text = (
            "Apex Wealth is a SEBI registered entity. "
            "We offer 100% guaranteed monthly returns of 35%. "
            "Hurry up, only 5 slots left for today. "
            "Pay ₹5,000 registration fee via UPI."
        )
        claims = self.extractor.extract_claims(text, "item_123")
        assert len(claims) >= 3

        types = [c.claim_type for c in claims]
        assert "regulatory" in types
        assert "return" in types
        assert "urgency" in types or "payment" in types

        for c in claims:
            assert c.status == "UNVERIFIED"
            assert c.content_item_id == "item_123"
            assert c.metadata["context_pointers"]["excerpt"] in text


class TestEntityResolver:
    def setup_method(self):
        self.resolver = EntityResolver()

    def test_resolve_sebi_registration_numbers(self):
        text = "Our broker registration is INZ000123456 and adviser registration is INA000009876."
        entities = self.resolver.resolve_entities(text)
        assert len(entities) == 2

        reg_nos = [e.registration_number for e in entities]
        assert "INZ000123456" in reg_nos
        assert "INA000009876" in reg_nos

    def test_resolve_cin(self):
        text = "Registered under MCA with CIN U74999MH2016PTC288123 in Mumbai."
        entities = self.resolver.resolve_entities(text)
        assert len(entities) == 2  # CIN entity + MCA regulator
        cin_entities = [e for e in entities if e.entity_type == "COMPANY"]
        assert len(cin_entities) == 1
        assert cin_entities[0].registration_number == "U74999MH2016PTC288123"

    def test_resolve_upi_vpa(self):
        text = "Send fees to trade.advisory@okhdfcbank or support@paytm immediately."
        entities = self.resolver.resolve_entities(text)
        vpas = [e.name for e in entities if e.entity_type == "UPI"]
        assert "trade.advisory@okhdfcbank" in vpas
        assert "support@paytm" in vpas

    def test_resolve_channels_and_regulators(self):
        text = "Join our VIP group at https://t.me/super_stock_tips. Verified by SEBI and listed on NSE."
        entities = self.resolver.resolve_entities(text)
        types = [e.entity_type for e in entities]
        assert "APP" in types       # Telegram link
        assert "REGULATOR" in types # SEBI
        assert "EXCHANGE" in types  # NSE


class TestSignalDetector:
    def setup_method(self):
        self.detector = SignalDetector()

    def test_detect_predatory_signals(self):
        text = (
            "Guaranteed 100% returns in 7 days! "
            "Pay ₹2,000 withdrawal fee to unlock your profits. "
            "Share your OTP with our executive to activate the bot. "
            "Hurry, only 3 seats left!"
        )
        signals = self.detector.detect_signals(text, "item_456")
        detected_types = {s.signal_type for s in signals}

        assert "GUARANTEED_RETURN" in detected_types
        assert "WITHDRAWAL_FEE" in detected_types
        assert "OTP_REQUEST" in detected_types
        assert "URGENCY" in detected_types

    def test_hard_negatives_regulatory_warnings(self):
        """Regulatory warnings must NOT trigger false positives for predatory signals."""
        warning_text = (
            "SEBI warns investors: Never invest in schemes promising guaranteed returns. "
            "Securities investments are subject to market risks."
        )
        signals = self.detector.detect_signals(warning_text, "item_warn")
        assert len(signals) == 0, f"False positive signals generated on regulatory warning: {[s.signal_type for s in signals]}"

    def test_hard_negatives_otp_safety_advice(self):
        """Investor education advising never to share OTP must NOT trigger OTP_REQUEST signal."""
        advice_text = "Never share your OTP or password with anyone calling from the bank."
        signals = self.detector.detect_signals(advice_text, "item_advice")
        assert len(signals) == 0, f"False positive signal generated on safety advice: {[s.signal_type for s in signals]}"

    def test_hard_negatives_statutory_disclaimers(self):
        """Standard mutual fund / broker statutory disclaimer must NOT trigger guaranteed return signal."""
        disclaimer_text = "Investments are subject to market risks. Past returns are not guaranteed."
        signals = self.detector.detect_signals(disclaimer_text, "item_disc")
        assert len(signals) == 0, f"False positive signal generated on disclaimer: {[s.signal_type for s in signals]}"


class TestContentIntelligenceEngine:
    def test_end_to_end_analysis_and_persistence(self, repo):
        engine = ContentIntelligenceEngine()

        item = ContentItem(
            organization_id=repo.organization_id,
            content_type="text",
            raw_content=(
                "Join our VIP trading circle at https://t.me/vip_calls. "
                "SEBI certified tipster guarantees 50% monthly profit with zero risk. "
                "Pay on advisor@okhdfcbank to claim your slot today."
            ),
        )
        item_id = repo.save_content_item(item)
        item.id = item_id

        analysis = engine.analyze(item)

        assert analysis.language.primary_language in {"en", "hinglish"}
        assert len(analysis.claims) >= 2
        assert len(analysis.signals) >= 2
        assert analysis.risk_score > 0.70
        assert "zero risk" in analysis.summary.lower() or "guaranteed" in analysis.summary.lower() or "risk score" in analysis.summary.lower()

        # Persist analysis
        persisted = engine.persist_analysis(analysis, repo)
        assert len(persisted["claim_ids"]) == len(analysis.claims)
        assert len(persisted["signal_ids"]) == len(analysis.signals)
        assert len(persisted["entity_ids"]) == len(analysis.entities)

        # Verify from repo
        saved_claims = repo.list_claims_for_content(item_id)
        assert len(saved_claims) == len(analysis.claims)

        saved_signals = repo.list_signals_for_content(item_id)
        assert len(saved_signals) == len(analysis.signals)

    def test_adversarial_evasion_countermeasures(self):
        """Zero-width spaces and fullwidth Unicode characters must not evade detection."""
        from sangyan.ingest.cleaner import clean_text
        engine = ContentIntelligenceEngine()

        # Scammer tries to evade keyword filter with zero-width spaces: g​u​a​r​a​n​t​e​e​d
        evasive_text = "Join our ＶＩＰ circle. We give g\u200bu\u200ca\u200dr\u200ea\u200fn\u200bt\u200be\u200ce\u200dd returns!"
        cleaned = clean_text(evasive_text)

        item = ContentItem(
            organization_id="org_test",
            content_type="text",
            raw_content=evasive_text,
            normalized_text=cleaned,
        )
        analysis = engine.analyze(item)
        detected_signals = {s.signal_type for s in analysis.signals}
        assert "GUARANTEED_RETURN" in detected_signals or "SCARCITY" in detected_signals

    def test_hard_negative_personal_savings_warning(self):
        """Advisories warning NOT to transfer to personal accounts must not be flagged as payment solicitations."""
        detector = SignalDetector()
        warning = "Advisory: Do not pay or transfer money to personal savings accounts of unregistered individuals."
        signals = detector.detect_signals(warning, "item_adv")
        assert len(signals) == 0, f"False positive signal on advisory: {[s.signal_type for s in signals]}"

    def test_large_content_resilience(self):
        """Engine should process large multi-paragraph text cleanly without degradation."""
        engine = ContentIntelligenceEngine()
        repeated = "Claim number {i}: ABC Corp offers investment services. "
        large_text = " ".join(repeated.format(i=i) for i in range(100))

        item = ContentItem(
            organization_id="org_test",
            content_type="text",
            raw_content=large_text,
            normalized_text=large_text,
        )
        analysis = engine.analyze(item)
        assert len(analysis.claims) > 0
        assert analysis.risk_score >= 0.0

