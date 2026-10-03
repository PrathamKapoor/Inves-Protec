"""Base utilities, schema versions, and identifier generators for SANGYAN domain models."""
from __future__ import annotations

import uuid
from typing import Any

CURRENT_SCHEMA_VERSION = 1


def new_id(prefix: str) -> str:
    """Generate a prefixed opaque UUID, e.g. 'claim_3f9c...'."""
    return f"{prefix}_{uuid.uuid4().hex}"


def require(condition: bool, message: str, errors: list[str]) -> None:
    """Append message to errors if condition is False."""
    if not condition:
        errors.append(message)


def validate_enum(value: Any, allowed: tuple[str, ...], field_name: str, errors: list[str]) -> None:
    """Check that value is in allowed collection."""
    if value not in allowed:
        errors.append(f"{field_name} '{value}' must be one of {allowed}")
