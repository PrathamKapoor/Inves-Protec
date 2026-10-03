"""Unit tests for TrustService and ML-DSA-65 post-quantum verification receipts."""
import tempfile
from pathlib import Path

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.trust.receipt import TrustReceipt
from sangyan.trust.service import TrustService


@pytest.fixture
def trust_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "trust_test.db"
        key_dir = Path(tmpdir) / "keys"
        engine = SQLiteDatabaseEngine(db_path)
        runner = MigrationRunner(engine)
        runner.migrate()
        svc = TrustService(engine, key_dir=key_dir)
        yield {"svc": svc, "engine": engine, "key_dir": key_dir}
        engine.close()


class TestTrustService:
    def test_keypair_persistence(self, trust_env):
        svc = trust_env["svc"]
        key_dir = trust_env["key_dir"]
        pk1 = svc.public_key
        assert len(pk1) > 0

        # Creating a second service pointing to the same key_dir must load the same keypair
        svc2 = TrustService(trust_env["engine"], key_dir=key_dir)
        assert svc2.public_key == pk1

    def test_sign_and_verify_document(self, trust_env):
        svc = trust_env["svc"]
        investigation_payload = {
            "id": "inv_001",
            "claims": [
                {"statement": "40% monthly returns guaranteed", "status": "CONTRADICTED"}
            ],
            "signals": ["GUARANTEED_RETURN", "URGENCY"],
            "review": {"action": "CONFIRM", "reviewer": "supervisor_1"},
        }

        receipt = svc.sign_document("investigation", "inv_001", investigation_payload)
        assert receipt.subject_id == "inv_001"
        assert receipt.algorithm_id == "ML-DSA-65"
        assert len(receipt.signature) > 0

        # Successful verification
        assert svc.verify_document(receipt, investigation_payload) is True

        # Tampered document fails verification
        tampered_payload = dict(investigation_payload)
        tampered_payload["claims"] = [
            {"statement": "40% monthly returns guaranteed", "status": "SUPPORTED"}  # Tampered!
        ]
        assert svc.verify_document(receipt, tampered_payload) is False
