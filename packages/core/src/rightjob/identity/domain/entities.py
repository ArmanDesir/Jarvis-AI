"""Identity/Tenancy entities without persistence or provider behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from rightjob.identity.domain.values import (
    MembershipRole,
    RecordStatus,
    new_uuid7,
    normalize_email,
    normalize_provider,
    normalize_slug,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Workspace:
    name: str
    slug: str
    timezone: str = "UTC"
    locale: str = "en"
    settings: dict[str, Any] = field(default_factory=dict)
    status: RecordStatus = RecordStatus.ACTIVE
    id: UUID = field(default_factory=new_uuid7)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", normalize_slug(self.slug))


@dataclass(frozen=True)
class User:
    external_identity_provider: str
    external_subject: str
    email: str
    display_name: str
    status: RecordStatus = RecordStatus.ACTIVE
    id: UUID = field(default_factory=new_uuid7)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "external_identity_provider", normalize_provider(self.external_identity_provider)
        )
        object.__setattr__(self, "email", normalize_email(self.email))
        if not self.external_subject.strip():
            raise ValueError("external subject is required")


@dataclass(frozen=True)
class Membership:
    workspace_id: UUID
    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER
    status: RecordStatus = RecordStatus.ACTIVE
    id: UUID = field(default_factory=new_uuid7)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 1
