"""Cryptographic JSON Web Token (JWT) issuance, verification, and claim validation."""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import jwt

from sangyan.security.models import (
    ExpiredTokenError,
    InvalidTokenError,
    Principal,
    SecurityConfig,
)

ALLOWED_JWT_ALGORITHMS = ("HS256", "RS256", "ES256", "EdDSA")


def create_jwt_token(
    payload: dict[str, Any],
    secret_or_key: str,
    algorithm: str = "HS256",
    expires_in_seconds: int = 3600,
    issuer: str = "sangyan-auth",
    audience: str = "sangyan-api",
) -> str:
    """Mint a cryptographically signed JWT with strict RFC 7519 standard claims."""
    if algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise ValueError(f"Algorithm '{algorithm}' is not permitted; allowed: {ALLOWED_JWT_ALGORITHMS}")

    now = time.time()
    claims = dict(payload)
    claims.setdefault("iss", issuer)
    claims.setdefault("aud", audience)
    claims.setdefault("iat", int(now))
    claims.setdefault("nbf", int(now - 1))
    claims.setdefault("exp", int(now + expires_in_seconds))
    claims.setdefault("jti", f"jti_{uuid.uuid4().hex}")

    return jwt.encode(claims, secret_or_key, algorithm=algorithm)


class JwtValidator:
    """Strict cryptographic validator for incoming external JWT bearer tokens."""

    def __init__(self, config: Optional[SecurityConfig] = None) -> None:
        self.config = config or SecurityConfig()
        # Ensure configured algorithms are strictly within allowlist
        for alg in self.config.jwt_algorithms:
            if alg not in ALLOWED_JWT_ALGORITHMS:
                raise ValueError(f"Insecure or unsupported JWT algorithm configured: {alg}")

    def decode_and_validate(self, token: str) -> Principal:
        """Decode, verify signature, validate standard and custom claims, returning Principal."""
        token = token.strip()
        if not token:
            raise InvalidTokenError("Empty bearer token provided")

        # Inspect unverified header first to reject 'none' or forbidden algorithms immediately
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise InvalidTokenError(f"Malformed JWT header: {e}") from e

        alg = unverified_header.get("alg")
        if not alg or alg not in self.config.jwt_algorithms:
            raise InvalidTokenError(f"Unsupported algorithm '{alg}'; allowed: {self.config.jwt_algorithms}")

        # Choose appropriate verification key
        key: str = self.config.jwt_public_key or self.config.jwt_secret

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=self.config.jwt_algorithms,
                issuer=self.config.jwt_issuer,
                audience=self.config.jwt_audience,
                leeway=self.config.jwt_leeway,
                options={
                    "verify_signature": True,
                    "require": ["exp", "iat", "iss", "aud", "sub", "org_id"],
                },
            )
        except jwt.ExpiredSignatureError as e:
            raise ExpiredTokenError(f"JWT token has expired: {e}") from e
        except jwt.ImmatureSignatureError as e:
            raise InvalidTokenError(f"JWT token not yet valid (nbf): {e}") from e
        except jwt.InvalidIssuerError as e:
            raise InvalidTokenError(f"JWT issuer mismatch: {e}") from e
        except jwt.InvalidAudienceError as e:
            raise InvalidTokenError(f"JWT audience mismatch: {e}") from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"JWT signature or claims invalid: {e}") from e
        except Exception as e:
            raise InvalidTokenError(f"Unexpected error validating JWT: {e}") from e

        # Validate mandatory tenant & subject identifiers
        user_id = str(payload.get("sub", "")).strip()
        org_id = str(payload.get("org_id", "")).strip()
        if not user_id or not org_id:
            raise InvalidTokenError("JWT missing non-empty 'sub' or 'org_id' claims")

        # Parse roles
        raw_roles = payload.get("roles")
        if isinstance(raw_roles, list):
            roles = tuple(str(r) for r in raw_roles if str(r).strip())
        elif isinstance(raw_roles, str) and raw_roles.strip():
            roles = (raw_roles.strip(),)
        else:
            single_role = payload.get("role")
            if isinstance(single_role, str) and single_role.strip():
                roles = (single_role.strip(),)
            else:
                roles = ("sangyan_viewer",)

        # Parse scopes
        raw_scopes = payload.get("scopes", [])
        scopes = tuple(str(s) for s in raw_scopes if str(s).strip()) if isinstance(raw_scopes, list) else ()

        return Principal(
            principal_id=user_id,
            organization_id=org_id,
            roles=roles,
            scopes=scopes,
            auth_method="jwt",
            credential_id=payload.get("jti"),
            issued_at=payload.get("iat"),
            expires_at=payload.get("exp"),
        )
