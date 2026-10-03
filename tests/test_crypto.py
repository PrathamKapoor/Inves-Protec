"""Unit tests for SHA3-256 and ML-DSA-65 post-quantum cryptography."""
import pytest

from sangyan.crypto.hashing import canonical_json, digest_document, sha3_hex
from sangyan.crypto.providers import get_signature_provider


class TestHashing:
    def test_canonical_json_sorting(self):
        doc1 = {"z": 1, "a": 2, "m": {"b": 3, "a": 4}}
        doc2 = {"a": 2, "m": {"a": 4, "b": 3}, "z": 1}
        # Keys must sort deterministically producing identical byte strings
        assert canonical_json(doc1) == canonical_json(doc2)
        assert digest_document(doc1) == digest_document(doc2)

    def test_sha3_hex(self):
        digest = sha3_hex(b"SANGYAN INVESTOR SAFETY")
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA3-256 is 32 bytes = 64 hex characters


class TestMLDSA65:
    def test_keygen_sign_verify(self):
        provider = get_signature_provider("ML-DSA-65")
        keypair = provider.generate_keypair()
        assert keypair.algorithm_id == "ML-DSA-65"
        assert len(keypair.public_key) > 0
        assert len(keypair.secret_key) > 0

        msg = b"Evidence record 42 digest: a94f..."
        signature = provider.sign(keypair.secret_key, msg)
        assert len(signature) > 0

        # Successful verification
        assert provider.verify(keypair.public_key, msg, signature) is True

        # Tampered message must fail verification
        tampered_msg = b"Evidence record 42 digest: a94f...MODIFIED"
        assert provider.verify(keypair.public_key, tampered_msg, signature) is False

        # Wrong public key must fail verification
        other_keypair = provider.generate_keypair()
        assert provider.verify(other_keypair.public_key, msg, signature) is False
