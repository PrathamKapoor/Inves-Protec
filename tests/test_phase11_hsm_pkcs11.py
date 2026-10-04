"""Phase 11: Hardware Security Module (HSM) / PKCS#11 signing provider test suite.

Validates:
1. Provider abstraction (`SigningProvider` ABC contract).
2. Simulator authentication: PIN validation and rejection of invalid PIN.
3. Key isolation: private key attributes are sensitive and cannot be extracted.
4. Signing and verification using NIST FIPS 204 ML-DSA-65.
5. Key rotation inside the HSM token while retaining historical public key verification.
6. Fail-closed production behavior when PKCS#11 native library is unavailable.
7. TrustService integration with HSM provider and receipt `signing_key_id` tracking.
"""
import base64
import pytest

from sangyan.core.errors import CryptoError
from sangyan.crypto.signing_provider import (
    PKCS11SimulatorSigningProvider,
    PKCS11SigningProvider,
    SoftwareSigningProvider,
    create_signing_provider,
)
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.trust.service import TrustService


@pytest.fixture
def db_engine(tmp_path):
    eng = SQLiteDatabaseEngine(tmp_path / "hsm_trust.db")
    runner = MigrationRunner(eng)
    runner.migrate()
    yield eng
    eng.close()


def test_hsm_simulator_authentication():
    # Correct PIN
    provider = PKCS11SimulatorSigningProvider(
        slot_id=0,
        token_label="Test-HSM",
        user_pin="correct-pin-99",
        key_identifier="hsm-key-01",
    )
    health = provider.health()
    assert health["status"] == "HEALTHY"
    assert health["authenticated"] is True
    assert health["token_label"] == "Test-HSM"
    assert provider.is_hardware() is True

    # Invalid PIN rejection
    with pytest.raises(CryptoError, match="CKR_PIN_INCORRECT"):
        provider.login("wrong-pin")
    assert provider.health()["authenticated"] is False

    # Re-authentication with correct PIN
    provider.login("correct-pin-99")
    assert provider.health()["authenticated"] is True

    # Logout
    provider.logout()
    with pytest.raises(CryptoError, match="CKR_USER_NOT_LOGGED_IN"):
        provider.sign(b"data")

    # Session closed
    provider.close_session()
    with pytest.raises(CryptoError, match="CKR_SESSION_CLOSED"):
        provider.sign(b"data")


def test_hsm_key_isolation_invariants():
    provider = PKCS11SimulatorSigningProvider(
        slot_id=0,
        token_label="Secured-HSM",
        user_pin="123456",
        key_identifier="key-isolated",
    )

    # Public key is accessible
    pk = provider.public_key
    assert len(pk) > 0

    # Secret key extraction attempt is strictly prohibited by security policy
    with pytest.raises(CryptoError, match="CKR_ATTRIBUTE_SENSITIVE"):
        provider.get_private_key_attribute()


def test_hsm_signing_and_verification():
    provider = PKCS11SimulatorSigningProvider(
        slot_id=0,
        user_pin="123456",
        key_identifier="hsm-sig-key",
    )

    message = b"authoritative regulatory finding: safe certified deposit"
    sig = provider.sign(message)
    assert len(sig) > 0

    # Valid signature
    assert provider.verify(message, sig) is True

    # Tampered message
    assert provider.verify(b"tampered content", sig) is False


def test_hsm_key_rotation_and_historical_receipt_verification():
    provider = PKCS11SimulatorSigningProvider(
        slot_id=0,
        user_pin="123456",
        key_identifier="generation-1",
    )

    doc_v1 = b"investigation report gen 1"
    sig_v1 = provider.sign(doc_v1)
    pk_v1 = provider.public_key
    assert provider.key_identifier == "generation-1"

    # Rotate to generation-2 inside HSM
    provider.rotate_key("generation-2")
    assert provider.key_identifier == "generation-2"
    pk_v2 = provider.public_key
    assert pk_v1 != pk_v2

    # Sign new doc with generation-2
    doc_v2 = b"investigation report gen 2"
    sig_v2 = provider.sign(doc_v2)
    assert provider.verify(doc_v2, sig_v2) is True

    # Crucial: verify historical doc signed under generation-1 using pk_v1 still succeeds
    assert provider.verify(doc_v1, sig_v1, public_key=pk_v1) is True


def test_fail_closed_native_pkcs11():
    # If native library does not exist, fail-closed immediately
    with pytest.raises(CryptoError, match="Fail-closed: PKCS#11 shared library not found"):
        PKCS11SigningProvider(lib_path="/nonexistent/libsofthsm2.so")


def test_factory_create_signing_provider():
    # Software
    sw = create_signing_provider("software")
    assert isinstance(sw, SoftwareSigningProvider)
    assert sw.is_hardware() is False

    # Simulator
    sim = create_signing_provider("pkcs11_simulator", pkcs11_pin="secret-pin")
    assert isinstance(sim, PKCS11SimulatorSigningProvider)
    assert sim.is_hardware() is True

    # Unsupported
    with pytest.raises(CryptoError, match="Unsupported signing provider type"):
        create_signing_provider("quantum_entanglement_device")

    # Native without path
    with pytest.raises(CryptoError, match="Fail-closed"):
        create_signing_provider("pkcs11")


def test_trust_service_with_hsm_provider(db_engine):
    hsm = PKCS11SimulatorSigningProvider(
        slot_id=0,
        token_label="Audit-HSM",
        user_pin="123456",
        key_identifier="hsm-prod-2026",
    )

    service = TrustService(engine=db_engine, signing_provider=hsm)
    assert service.public_key == hsm.public_key

    # Sign document
    receipt = service.sign_document(
        subject_type="investigation",
        subject_id="inv-hsm-001",
        document={"finding": "VERIFIED_SAFE", "evidence_count": 3},
    )

    assert receipt.signing_key_id == "hsm-prod-2026"
    assert len(receipt.signature) > 0

    # Verify document
    assert service.verify_document(receipt, {"finding": "VERIFIED_SAFE", "evidence_count": 3}) is True
    assert service.verify_document(receipt, {"finding": "TAMPERED"}) is False

    # Check persistence in database
    row = db_engine.query_one("SELECT * FROM sangyan_trust_receipts WHERE id=?", (receipt.id,))
    assert row is not None
    assert row["signing_key_id"] == "hsm-prod-2026"
