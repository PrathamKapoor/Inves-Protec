"""Tenancy models, roles, and permissions for SANGYAN."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sangyan.domain.base import CURRENT_SCHEMA_VERSION, new_id

SANGYAN_ROLES = ("sangyan_admin", "sangyan_analyst", "sangyan_viewer")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "sangyan_admin": {
        "tenant:manage",
        "api_key:manage",
        "investigation:create",
        "investigation:read",
        "investigation:review",
        "investigation:export",
        "trust:sign",
        "trust:verify",
    },
    "sangyan_analyst": {
        "investigation:create",
        "investigation:read",
        "investigation:review",
        "investigation:export",
        "trust:verify",
    },
    "sangyan_viewer": {
        "investigation:read",
        "trust:verify",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Check whether a role possesses a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


@dataclass
class Organization:
    name: str
    id: str = field(default_factory=lambda: new_id("org"))
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }


@dataclass
class User:
    email: str
    name: str
    id: str = field(default_factory=lambda: new_id("usr"))
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }


@dataclass
class Membership:
    organization_id: str
    user_id: str
    role: str
    id: str = field(default_factory=lambda: new_id("mem"))
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }
