"""Trust service generating and verifying post-quantum signatures for SANGYAN records."""
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sangyan.core.errors import CryptoError
from sangyan.crypto.hashing import digest_document
from sangyan.crypto.providers import get_signature_provider
from sangyan.crypto.signing_provider import SigningProvider, SoftwareSigningProvider
from sangyan.database.engine import DatabaseEngine
from sangyan.trust.receipt import TrustReceipt

DEFAULT_ALGORITHM = "ML-DSA-65"


class TrustService:
    """Manages post-quantum signing keypairs, generates receipts, and verifies integrity."""

    def __init__(
        self,
        engine: DatabaseEngine,
        key_dir: Optional[Path | str] = None,
        algorithm_id: str = DEFAULT_ALGORITHM,
        signing_provider: Optional[SigningProvider] = None,
    ) -> None:
        self._db = engine
        self._algorithm_id = algorithm_id
        if signing_provider is not None:
            self._signing_provider = signing_provider
        else:
            self._signing_provider = SoftwareSigningProvider(
                key_dir=key_dir,
                algorithm_id=algorithm_id,
            )

    @property
    def public_key(self) -> bytes:
        return self._signing_provider.public_key

    @property
    def key_identifier(self) -> str:
        return self._signing_provider.key_identifier

    @property
    def signing_provider(self) -> SigningProvider:
        return self._signing_provider

    def sign_document(self, subject_type: str, subject_id: str, document: Any) -> TrustReceipt:
        """Compute canonical SHA3-256 digest of document and sign via signing provider."""
        digest = digest_document(document)
        sig = self._signing_provider.sign(digest.encode("utf-8"))
        receipt = TrustReceipt(
            subject_type=subject_type,
            subject_id=subject_id,
            algorithm_id=self._signing_provider.algorithm_id,
            public_key=self._signing_provider.public_key,
            content_digest=digest,
            signature=sig,
            created_at=time.time(),
            signing_key_id=self._signing_provider.key_identifier,
        )
        self.save_receipt(receipt)
        return receipt

    def save_receipt(self, receipt: TrustReceipt) -> None:
        """Persist trust receipt to database."""
        self._db.execute(
            """
            INSERT INTO sangyan_trust_receipts
            (id, subject_type, subject_id, algorithm_id, public_key_b64, content_digest, signature_b64, created_at, signing_key_id)
            VALUES (?,?,?,?,?,?,?,?,?)
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
                receipt.signing_key_id,
            ),
        )

    def get_receipt(self, receipt_id: str) -> Optional[TrustReceipt]:
        """Retrieve trust receipt from database by ID."""
        row = self._db.query_one("SELECT * FROM sangyan_trust_receipts WHERE id=?", (receipt_id,))
        if not row:
            return None
        return TrustReceipt.from_dict(row)

    def verify_document(self, receipt: TrustReceipt, document: Any) -> bool:
        """Verify receipt against current document content using ML-DSA-65."""
        current_digest = digest_document(document)
        if current_digest != receipt.content_digest:
            return False
        return self._signing_provider.verify(
            receipt.content_digest.encode("utf-8"),
            receipt.signature,
            public_key=receipt.public_key,
        )

    def rotate_key(self, new_key_id: str) -> None:
        """Rotate active signing key in the underlying provider."""
        self._signing_provider.rotate_key(new_key_id)

    def health(self) -> Dict[str, Any]:
        """Query cryptographic provider health status."""
        return self._signing_provider.health()
