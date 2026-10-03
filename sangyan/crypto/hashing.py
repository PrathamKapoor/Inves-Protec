"""Post-quantum hashing utilities (SHA-3 family) and canonical serialization."""
from __future__ import annotations

import hashlib
import json
from typing import Any

HASH_ALGORITHM = "sha3-256"


def sha3_hex(data: bytes) -> str:
    """SHA3-256 hex digest of raw bytes."""
    return hashlib.sha3_256(data).hexdigest()


def sha3_digest(data: bytes) -> bytes:
    """SHA3-256 binary digest of raw bytes."""
    return hashlib.sha3_256(data).digest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON encoding: sorted keys, compact separators, UTF-8.

    Any two structurally equal documents produce identical bytes, ensuring
    reproducible digests and cryptographic signatures.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_document(doc: Any) -> str:
    """SHA3-256 digest over the canonical JSON representation of a document."""
    return sha3_hex(canonical_json(doc))


def digest_dict_mapping(items: dict[str, str]) -> dict[str, str]:
    """Digest each value in a mapping of name -> serializable content."""
    return {k: sha3_hex(canonical_json(v)) for k, v in items.items()}
