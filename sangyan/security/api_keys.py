"""Hashed API Key lifecycle, generation, constant-time validation, and parsing."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from typing import Any, Optional

from sangyan.security.models import (
    ApiKey,
    ExpiredTokenError,
    InvalidApiKeyError,
    Principal,
    RevokedApiKeyError,
)

API_KEY_REGEX = re.compile(r"^sgy_([0-9a-fA-F]{8})_([0-9a-fA-F]{32})$")


def hash_api_key(prefix: str, secret: str) -> str:
    """Compute constant-time verifiable SHA-256 digest of API key secret keyed with prefix."""
    payload = f"{prefix.lower()}:{secret}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_raw_api_key(raw_key: str) -> tuple[str, str]:
    """Parse and validate format of raw API key, returning (prefix, secret)."""
    raw_key = raw_key.strip()
    match = API_KEY_REGEX.match(raw_key)
    if not match:
        raise InvalidApiKeyError("Malformed API key format; expected 'sgy_<8_hex>_<32_hex>'")
    prefix, secret = match.groups()
    return prefix.lower(), secret


def generate_api_key(
    organization_id: str,
    user_id: str,
    name: str,
    role: str = "sangyan_analyst",
    scopes: Optional[list[str]] = None,
    expires_in_days: Optional[int] = None,
) -> tuple[str, ApiKey]:
    """Generate a new secure API key with high-entropy secret and hashed persistence model."""
    prefix = secrets.token_hex(4).lower()  # 8 hex characters
    secret = secrets.token_hex(16).lower()  # 32 hex characters
    raw_key = f"sgy_{prefix}_{secret}"
    digest = hash_api_key(prefix, secret)

    now = time.time()
    expires_at = (now + expires_in_days * 86400.0) if expires_in_days else None

    api_key = ApiKey(
        organization_id=organization_id,
        user_id=user_id,
        name=name.strip(),
        key_prefix=prefix,
        key_hash=digest,
        role=role,
        scopes=scopes or [],
        expires_at=expires_at,
        created_at=now,
    )
    return raw_key, api_key


import json


def verify_api_key(raw_key: str, repo_or_engine: Any) -> Principal:
    """Validate a raw API key against the repository or database engine in constant time."""
    prefix, secret = parse_raw_api_key(raw_key)
    api_key: Optional[ApiKey] = None

    if hasattr(repo_or_engine, "get_api_key_by_prefix"):
        api_key = repo_or_engine.get_api_key_by_prefix(prefix)
    elif hasattr(repo_or_engine, "query_one"):
        row = repo_or_engine.query_one(
            "SELECT * FROM sangyan_api_keys WHERE key_prefix=?",
            (prefix,),
        )
        if row is not None:
            api_key = ApiKey(
                id=row["id"],
                organization_id=row["organization_id"],
                user_id=row["user_id"],
                name=row["name"],
                key_prefix=row["key_prefix"],
                key_hash=row["key_hash"],
                role=row["role"],
                scopes=json.loads(row["scopes"] or "[]"),
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
                last_used_at=row["last_used_at"],
                created_at=row["created_at"],
                schema_version=int(row["schema_version"]),
            )

    if api_key is None:
        raise InvalidApiKeyError("API key not found")

    if api_key.revoked_at is not None:
        raise RevokedApiKeyError(f"API key '{api_key.name}' was revoked at {api_key.revoked_at}")

    now = time.time()
    if api_key.expires_at is not None and now >= api_key.expires_at:
        raise ExpiredTokenError(f"API key '{api_key.name}' expired at {api_key.expires_at}")

    computed_hash = hash_api_key(prefix, secret)
    if not hmac.compare_digest(computed_hash, api_key.key_hash):
        raise InvalidApiKeyError("Invalid API key secret")

    # Update last_used_at asynchronously/atomically
    try:
        if hasattr(repo_or_engine, "update_api_key_last_used"):
            repo_or_engine.update_api_key_last_used(api_key.id, now)
        elif hasattr(repo_or_engine, "execute"):
            repo_or_engine.execute(
                "UPDATE sangyan_api_keys SET last_used_at=? WHERE id=?",
                (now, api_key.id),
            )
    except Exception:
        pass

    return Principal(
        principal_id=api_key.user_id,
        organization_id=api_key.organization_id,
        roles=(api_key.role,),
        scopes=tuple(api_key.scopes),
        auth_method="api_key",
        credential_id=api_key.id,
        issued_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )

