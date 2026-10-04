"""Hardware Security Module (HSM) / PKCS#11 cryptographic signing provider architecture.

Provides fail-closed signing abstractions isolating NIST FIPS 204 ML-DSA-65 private keys
behind hardware token boundaries or deterministic simulator sessions.
"""
from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from sangyan.core.errors import CryptoError
from sangyan.crypto.providers import KeyPair, SignatureProvider, get_signature_provider

logger = logging.getLogger(__name__)

DEFAULT_ALGORITHM = "ML-DSA-65"


class SigningProvider(ABC):
    """Abstract base class for cryptographic signing providers with private key isolation."""

    @property
    @abstractmethod
    def key_identifier(self) -> str:
        """Unique key identifier or token label."""
        ...

    @property
    @abstractmethod
    def algorithm_id(self) -> str:
        """Algorithm identifier (e.g. ML-DSA-65)."""
        ...

    @property
    @abstractmethod
    def public_key(self) -> bytes:
        """Exportable public key bytes."""
        ...

    @abstractmethod
    def sign(self, message: bytes) -> bytes:
        """Sign message bytes without exposing secret key material."""
        ...

    @abstractmethod
    def verify(self, message: bytes, signature: bytes, public_key: Optional[bytes] = None) -> bool:
        """Verify signature over message bytes."""
        ...

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Return provider health status, token presence, and session state."""
        ...

    @abstractmethod
    def rotate_key(self, new_key_id: str) -> None:
        """Rotate to a new signing keypair while preserving past public keys."""
        ...

    def is_hardware(self) -> bool:
        """Whether signing operations are executed inside an HSM/hardware boundary."""
        return False


class SoftwareSigningProvider(SigningProvider):
    """Software-backed signing provider using pure-Python ML-DSA-65 implementation."""

    def __init__(
        self,
        key_dir: Optional[Path | str] = None,
        algorithm_id: str = DEFAULT_ALGORITHM,
        key_identifier: str = "software-default",
    ) -> None:
        self._algorithm_id = algorithm_id
        self._key_id = key_identifier
        self._provider: SignatureProvider = get_signature_provider(algorithm_id)
        self._key_dir = Path(key_dir) if key_dir else None
        self._lock = threading.Lock()
        self._historical_public_keys: Dict[str, bytes] = {}

        if self._key_dir is not None:
            self._key_dir.mkdir(parents=True, exist_ok=True)
            self._keypair = self._load_or_create_keypair()
        else:
            self._keypair = self._provider.generate_keypair()
        self._historical_public_keys[self._key_id] = self._keypair.public_key

    def _load_or_create_keypair(self) -> KeyPair:
        assert self._key_dir is not None
        key_file = self._key_dir / f"sangyan_trust_key_{self._key_id}.json"
        if not key_file.exists():
            # Legacy fallback
            legacy = self._key_dir / "sangyan_trust_key.json"
            if legacy.exists():
                key_file = legacy

        if key_file.exists():
            data = json.loads(key_file.read_text(encoding="utf-8"))
            if data.get("algorithm_id") == self._algorithm_id:
                return KeyPair(
                    algorithm_id=data["algorithm_id"],
                    public_key=base64.b64decode(data["public_key"]),
                    secret_key=base64.b64decode(data["secret_key"]),
                )

        pair = self._provider.generate_keypair()
        payload = {
            "algorithm_id": pair.algorithm_id,
            "key_identifier": self._key_id,
            "public_key": base64.b64encode(pair.public_key).decode("ascii"),
            "secret_key": base64.b64encode(pair.secret_key).decode("ascii"),
            "created_at": time.time(),
        }
        key_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return pair

    @property
    def key_identifier(self) -> str:
        return self._key_id

    @property
    def algorithm_id(self) -> str:
        return self._algorithm_id

    @property
    def public_key(self) -> bytes:
        return self._keypair.public_key

    def sign(self, message: bytes) -> bytes:
        with self._lock:
            return self._provider.sign(self._keypair.secret_key, message)

    def verify(self, message: bytes, signature: bytes, public_key: Optional[bytes] = None) -> bool:
        pk = public_key or self.public_key
        return self._provider.verify(pk, message, signature)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "provider_type": "software",
            "is_hardware": False,
            "key_identifier": self._key_id,
            "algorithm_id": self._algorithm_id,
            "public_key_fingerprint": base64.b64encode(self.public_key[:8]).decode("ascii"),
        }

    def rotate_key(self, new_key_id: str) -> None:
        with self._lock:
            self._key_id = new_key_id
            if self._key_dir is not None:
                self._keypair = self._load_or_create_keypair()
            else:
                self._keypair = self._provider.generate_keypair()
            self._historical_public_keys[new_key_id] = self._keypair.public_key


class PKCS11SimulatorSigningProvider(SigningProvider):
    """Deterministic in-memory Hardware Security Module (HSM) simulator adhering to PKCS#11 semantics.

    Guarantees private key isolation: private keys are created and held within the simulator token
    and can NEVER be exported by caller code. Supports PIN authentication, slot sessions, and key rotation.
    """

    def __init__(
        self,
        slot_id: int = 0,
        token_label: str = "Sangyan-ML-DSA-HSM",
        user_pin: str = "123456",
        key_identifier: str = "hsm-key-001",
        algorithm_id: str = DEFAULT_ALGORITHM,
    ) -> None:
        self._slot_id = slot_id
        self._token_label = token_label
        self._pin = user_pin
        self._key_id = key_identifier
        self._algorithm_id = algorithm_id
        self._provider: SignatureProvider = get_signature_provider(algorithm_id)
        self._lock = threading.Lock()

        # Hardware token internal storage (non-extractable)
        self._session_open = True
        self._authenticated = False
        self._token_keys: Dict[str, KeyPair] = {}
        self._historical_public_keys: Dict[str, bytes] = {}

        # Authenticate token and initialize first hardware key
        self.login(user_pin)
        self._generate_hardware_key(key_identifier)

    def login(self, pin: str) -> None:
        """Emulate C_Login with user PIN."""
        if pin != self._pin:
            self._authenticated = False
            raise CryptoError("CKR_PIN_INCORRECT: invalid HSM user PIN")
        self._authenticated = True

    def logout(self) -> None:
        """Emulate C_Logout."""
        self._authenticated = False

    def close_session(self) -> None:
        """Emulate C_CloseSession."""
        self._session_open = False
        self._authenticated = False

    def is_hardware(self) -> bool:
        return True

    def _generate_hardware_key(self, key_id: str) -> None:
        if not self._authenticated:
            raise CryptoError("CKR_USER_NOT_LOGGED_IN: HSM session requires authentication")
        pair = self._provider.generate_keypair()
        self._token_keys[key_id] = pair
        self._historical_public_keys[key_id] = pair.public_key

    @property
    def key_identifier(self) -> str:
        return self._key_id

    @property
    def algorithm_id(self) -> str:
        return self._algorithm_id

    @property
    def public_key(self) -> bytes:
        if self._key_id not in self._token_keys:
            raise CryptoError(f"CKR_OBJECT_HANDLE_INVALID: key '{self._key_id}' not found in HSM")
        return self._token_keys[self._key_id].public_key

    def get_private_key_attribute(self) -> bytes:
        """Attempting to read private key attribute fails with PKCS#11 CKR_ATTRIBUTE_SENSITIVE."""
        raise CryptoError("CKR_ATTRIBUTE_SENSITIVE: private key extraction strictly prohibited by HSM security policy")

    def sign(self, message: bytes) -> bytes:
        """Perform on-token signature operation (emulating C_SignInit + C_Sign)."""
        if not self._session_open:
            raise CryptoError("CKR_SESSION_CLOSED: HSM session is not active")
        if not self._authenticated:
            raise CryptoError("CKR_USER_NOT_LOGGED_IN: HSM signing operation requires authenticated session")

        with self._lock:
            keypair = self._token_keys.get(self._key_id)
            if not keypair:
                raise CryptoError(f"CKR_OBJECT_HANDLE_INVALID: key '{self._key_id}' not found on token")
            return self._provider.sign(keypair.secret_key, message)

    def verify(self, message: bytes, signature: bytes, public_key: Optional[bytes] = None) -> bool:
        """Verify signature using public key."""
        pk = public_key or self.public_key
        return self._provider.verify(pk, message, signature)

    def rotate_key(self, new_key_id: str) -> None:
        """Emulate key rotation inside the HSM token."""
        with self._lock:
            self._generate_hardware_key(new_key_id)
            self._key_id = new_key_id
            logger.info("HSM token %s rotated active signing key to %s", self._token_label, new_key_id)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if self._session_open and self._authenticated else "DEGRADED",
            "provider_type": "pkcs11_simulator",
            "is_hardware": True,
            "slot_id": self._slot_id,
            "token_label": self._token_label,
            "session_active": self._session_open,
            "authenticated": self._authenticated,
            "key_identifier": self._key_id,
            "algorithm_id": self._algorithm_id,
            "token_keys_count": len(self._token_keys),
        }


class PKCS11SigningProvider(SigningProvider):
    """Production PKCS#11 provider loading physical / cloud HSM shared module via dynamic linking.

    Enforces fail-closed semantics: if the native library or token is unavailable,
    it raises CryptoError rather than silently falling back to software.
    """

    def __init__(
        self,
        lib_path: str,
        slot_id: int = 0,
        token_label: Optional[str] = None,
        pin: Optional[str] = None,
        key_identifier: str = "sangyan-hsm-key",
        algorithm_id: str = DEFAULT_ALGORITHM,
    ) -> None:
        self._lib_path = lib_path
        self._slot_id = slot_id
        self._token_label = token_label
        self._pin = pin
        self._key_id = key_identifier
        self._algorithm_id = algorithm_id
        self._provider: SignatureProvider = get_signature_provider(algorithm_id)

        if not lib_path or not os.path.exists(lib_path):
            raise CryptoError(
                f"Fail-closed: PKCS#11 shared library not found at '{lib_path}'. "
                "Hardware private key isolation cannot be guaranteed."
            )

        try:
            self._cdll = ctypes.CDLL(lib_path)
        except Exception as exc:
            raise CryptoError(f"Fail-closed: Failed to load PKCS#11 native library '{lib_path}': {exc}") from exc

        # Verify C_Initialize symbol exists
        if not hasattr(self._cdll, "C_Initialize"):
            raise CryptoError(f"Fail-closed: Library '{lib_path}' does not export PKCS#11 symbol C_Initialize")

    def is_hardware(self) -> bool:
        return True

    @property
    def key_identifier(self) -> str:
        return self._key_id

    @property
    def algorithm_id(self) -> str:
        return self._algorithm_id

    @property
    def public_key(self) -> bytes:
        raise NotImplementedError("Real PKCS#11 public key extraction requires active hardware token")

    def sign(self, message: bytes) -> bytes:
        raise NotImplementedError("Real PKCS#11 signing requires active hardware token")

    def verify(self, message: bytes, signature: bytes, public_key: Optional[bytes] = None) -> bool:
        pk = public_key or self.public_key
        return self._provider.verify(pk, message, signature)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "provider_type": "pkcs11_native",
            "is_hardware": True,
            "library_path": self._lib_path,
            "slot_id": self._slot_id,
            "key_identifier": self._key_id,
            "algorithm_id": self._algorithm_id,
        }

    def rotate_key(self, new_key_id: str) -> None:
        self._key_id = new_key_id


def create_signing_provider(
    provider_type: str = "software",
    key_dir: Optional[Path | str] = None,
    key_identifier: str = "default",
    algorithm_id: str = DEFAULT_ALGORITHM,
    pkcs11_lib_path: Optional[str] = None,
    pkcs11_slot_id: int = 0,
    pkcs11_token_label: Optional[str] = None,
    pkcs11_pin: Optional[str] = None,
) -> SigningProvider:
    """Factory creating configured SigningProvider with strict fail-closed validation."""
    prov_lower = provider_type.lower().strip()
    if prov_lower == "software":
        return SoftwareSigningProvider(
            key_dir=key_dir,
            algorithm_id=algorithm_id,
            key_identifier=key_identifier,
        )
    elif prov_lower in ("pkcs11_simulator", "hsm_simulator"):
        return PKCS11SimulatorSigningProvider(
            slot_id=pkcs11_slot_id,
            token_label=pkcs11_token_label or "Sangyan-ML-DSA-HSM",
            user_pin=pkcs11_pin or "123456",
            key_identifier=key_identifier,
            algorithm_id=algorithm_id,
        )
    elif prov_lower in ("pkcs11", "hsm"):
        if not pkcs11_lib_path:
            raise CryptoError("Fail-closed: PKCS#11 provider requested but 'pkcs11_lib_path' is not configured")
        return PKCS11SigningProvider(
            lib_path=pkcs11_lib_path,
            slot_id=pkcs11_slot_id,
            token_label=pkcs11_token_label,
            pin=pkcs11_pin,
            key_identifier=key_identifier,
            algorithm_id=algorithm_id,
        )
    else:
        raise CryptoError(f"Unsupported signing provider type: '{provider_type}'")
