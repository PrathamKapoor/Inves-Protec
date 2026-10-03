"""Trust service generating and verifying post-quantum signatures for SANGYAN records."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Optional

from sangyan.core.errors import CryptoError
from sangyan.crypto.hashing import digest_document
from sangyan.crypto.providers import KeyPair, SignatureProvider, get_signature_provider
from sangyan.database.engine import DatabaseEngine
from sangyan.trust.receipt import TrustReceipt

DEFAULT_ALGORITHM = "ML-DSA-65"


class TrustService:
    """Manages ML-DSA-65 post-quantum signing keypairs, generates receipts, and verifies integrity."""

    def __init__(
        self,
        engine: DatabaseEngine,
        key_dir: Optional[Path | str] = None,
        algorithm_id: str = DEFAULT_ALGORITHM,
    ) -> None:
        self._db = engine
        self._algorithm_id = algorithm_id
        self._provider: SignatureProvider = get_signature_provider(algorithm_id)
        self._keypair: Optional[KeyPair] = None

        if key_dir is not None:
            self._key_dir = Path(key_dir)
            self._key_dir.mkdir(parents=True, exist_ok=True)
            self._keypair = self._load_or_create_keypair()

    def _load_or_create_keypair(self) -> KeyPair:
        assert self._key_dir is not None
        key_file = self._key_dir / "sangyan_trust_key.json"
        if key_file.exists():
            data = json.loads(key_file.read_text(encoding="utf-8"))
            if data.get("algorithm_id") == self._algorithm_id:
                return KeyPair(
                    algorithm_id=data["algorithm_id"],
                    public_key=base64.b64decode(data["public_key"]),
                    secret_key=base64.b64decode(data["secret_key"]),
                )
        # Generate new keypair and persist
        pair = self._provider.generate_keypair()
        payload = {
            "algorithm_id": pair.algorithm_id,
            "public_key": base64.b64encode(pair.public_key).decode("ascii"),
            "secret_key": base64.b64encode(pair.secret_key).decode("ascii"),
            "created_at": time.time(),
        }
        key_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return pair

    @property
    def public_key(self) -> bytes:
        if self._keypair is None:
            raise CryptoError("trust service has no keypair loaded")
        return self._keypair.public_key

    def sign_document(self, subject_type: str, subject_id: str, document: Any) -> TrustReceipt:
        """Compute canonical SHA3-256 digest of document and sign with ML-DSA-65."""
        if self._keypair is None:
            raise CryptoError("signing requires a configured key directory")
        digest = digest_document(document)
        sig = self._provider.sign(self._keypair.secret_key, digest.encode("utf-8"))
        receipt = TrustReceipt(
            subject_type=subject_type,
            subject_id=subject_id,
            algorithm_id=self._algorithm_id,
            public_key=self._keypair.public_key,
            content_digest=digest,
            signature=sig,
            created_at=time.time(),
        )
        self.save_receipt(receipt)
        return receipt

    def save_receipt(self, receipt: TrustReceipt) -> None:
        """Persist trust receipt to database."""
        self._db.execute(
            """
            INSERT INTO sangyan_trust_receipts
            (id, subject_type, subject_id, algorithm_id, public_key_b64, content_digest, signature_b64, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                receipt.id,
                receipt.subject_type,
                receipt.subject_id,
                receipt.algorithm_id,
                base64.b64encode(receipt.public_key).decode("ascii"),
                receipt.content_digest,
                base64.b64encode(receipt.signature).decode("ascii"),
                receipt.created_at,
            ),
        )

    def verify_document(self, receipt: TrustReceipt, document: Any) -> bool:
        """Verify receipt against current document content using ML-DSA-65."""
        current_digest = digest_document(document)
        if current_digest != receipt.content_digest:
            return False
        provider = get_signature_provider(receipt.algorithm_id)
        return provider.verify(
            receipt.public_key,
            receipt.content_digest.encode("utf-8"),
            receipt.signature,
        )
