"""Typed HTTP contracts for the Identity/Tenancy application API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from rightjob.identity.application.context import Principal
from rightjob.identity.domain.entities import Membership, Workspace
from rightjob.identity.domain.values import MembershipRole, RecordStatus

TrimmedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
TrimmedTimezone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
TrimmedLocale = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=35)
]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurrentPrincipalResponse(ApiModel):
    user_id: UUID
    workspace_id: UUID
    membership_id: UUID
    role: MembershipRole
    authentication_provider: str
    permissions: tuple[str, ...]

    @classmethod
    def from_principal(cls, principal: Principal) -> "CurrentPrincipalResponse":
        return cls(
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
            membership_id=principal.membership_id,
            role=MembershipRole(principal.roles[0]),
            authentication_provider=principal.authentication_provider,
            permissions=principal.permissions,
        )


class WorkspaceResponse(ApiModel):
    id: UUID
    name: str
    slug: str
    status: RecordStatus
    timezone: str
    locale: str
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_workspace(cls, workspace: Workspace) -> "WorkspaceResponse":
        return cls.model_validate(workspace, from_attributes=True)


class MembershipResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: MembershipRole
    status: RecordStatus
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_membership(cls, membership: Membership) -> "MembershipResponse":
        return cls.model_validate(membership, from_attributes=True)


class WorkspacePatchRequest(ApiModel):
    expected_version: int = Field(ge=1)
    name: TrimmedName | None = None
    timezone: TrimmedTimezone | None = None
    locale: TrimmedLocale | None = None

    @model_validator(mode="after")
    def require_change(self) -> "WorkspacePatchRequest":
        if self.name is None and self.timezone is None and self.locale is None:
            raise ValueError("at least one mutable Workspace field is required")
        return self


class ErrorItem(ApiModel):
    field: str
    message: str
    kind: str


class ProblemDetail(ApiModel):
    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str
    correlation_id: str
    errors: tuple[ErrorItem, ...] = ()
