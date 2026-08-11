"""Canonical authenticated Principal and workspace AuthorizationContext."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rightjob.identity.domain.entities import Membership, Workspace


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    external_subject: str
    workspace_id: UUID
    membership_id: UUID
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    authentication_provider: str


@dataclass(frozen=True)
class AuthorizationContext:
    principal: Principal
    workspace: Workspace
    membership: Membership
