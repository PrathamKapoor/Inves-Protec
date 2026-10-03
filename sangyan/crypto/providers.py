"""Post-quantum cryptographic primitive providers (ML-DSA / Dilithium).

Provides agile signature verification and keypair generation wrapped with a
thread-safe lock for multi-threaded safety.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass

from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87

from sangyan.core.errors import CryptoError

# Pure-Python ML-DSA implementations have shared internal state;
# serialize operations across threads to guarantee verification reliability.
_PQC_LOCK = threading.RLock()


@dataclass(frozen=True)
class KeyPair:
    algorithm_id: str
    public_key: bytes
    secret_key: bytes


class SignatureProvider(ABC):
    algorithm_id: str = ""
    security_level: int = 0

    @abstractmethod
    def generate_keypair(self) -> KeyPair:
        """Generate a public/private keypair."""
        ...

    @abstractmethod
    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        """Sign bytes using the private key."""
        ...

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify signature over message bytes using the public key."""
        ...


def _sig_provider(ml_dsa_cls, alg_id: str, level: int) -> type[SignatureProvider]:
    class _MLDSA(SignatureProvider):
        algorithm_id = alg_id
        security_level = level

        def generate_keypair(self) -> KeyPair:
            with _PQC_LOCK:
                pk, sk = ml_dsa_cls.keygen()
            return KeyPair(alg_id, bytes(pk), bytes(sk))

        def sign(self, secret_key: bytes, message: bytes) -> bytes:
            try:
                with _PQC_LOCK:
                    return bytes(ml_dsa_cls.sign(secret_key, message))
            except Exception as exc:
                raise CryptoError(f"{alg_id} signing failed: {exc}") from exc

        def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
            try:
                with _PQC_LOCK:
                    return bool(ml_dsa_cls.verify(public_key, message, signature))
            except Exception:
                return False

    _MLDSA.__name__ = f"{alg_id.replace('-', '_')}_Provider"
    return _MLDSA


MLDSA44Provider = _sig_provider(ML_DSA_44, "ML-DSA-44", 2)
MLDSA65Provider = _sig_provider(ML_DSA_65, "ML-DSA-65", 3)
MLDSA87Provider = _sig_provider(ML_DSA_87, "ML-DSA-87", 5)

SIGNATURE_PROVIDERS: dict[str, SignatureProvider] = {
    "ML-DSA-44": MLDSA44Provider(),
    "ML-DSA-65": MLDSA65Provider(),
    "ML-DSA-87": MLDSA87Provider(),
}


def get_signature_provider(algorithm_id: str = "ML-DSA-65") -> SignatureProvider:
    """Retrieve signature provider by algorithm identifier."""
    if algorithm_id not in SIGNATURE_PROVIDERS:
        raise CryptoError(f"unsupported signature algorithm: {algorithm_id}")
    return SIGNATURE_PROVIDERS[algorithm_id]
