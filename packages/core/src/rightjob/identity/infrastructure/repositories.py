"""SQLAlchemy repositories with explicit Workspace scope."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Sequence, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.identity.domain.entities import Membership, User, Workspace
from rightjob.identity.domain.values import MembershipRole, RecordStatus
from rightjob.identity.infrastructure.models import MembershipRecord, UserRecord, WorkspaceRecord


def _set_workspace_context(session: Session, workspace_id: UUID) -> None:
    session.execute(select(func.set_config("app.current_workspace_id", str(workspace_id), True)))


def _workspace(record: WorkspaceRecord) -> Workspace:
    values = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    values["status"] = RecordStatus(values["status"])
    return Workspace(**values)


def _user(record: UserRecord) -> User:
    values = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    values["status"] = RecordStatus(values["status"])
    return User(**values)


def _membership(record: MembershipRecord) -> Membership:
    values = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    values["role"] = MembershipRole(values["role"])
    values["status"] = RecordStatus(values["status"])
    return Membership(**values)


def _updated_at() -> datetime:
    return datetime.now(timezone.utc)


def _require_updated(result: Any) -> None:
    cursor = cast(CursorResult[Any], result)
    if cursor.rowcount != 1:
        raise ConcurrentUpdateError("aggregate was changed or removed")


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace: Workspace) -> None:
        self._session.add(WorkspaceRecord(**workspace.__dict__))

    def get(self, workspace_id: UUID) -> Workspace | None:
        _set_workspace_context(self._session, workspace_id)
        record = self._session.scalar(
            select(WorkspaceRecord).where(WorkspaceRecord.id == workspace_id)
        )
        return _workspace(record) if record else None

    def save(self, workspace: Workspace) -> Workspace:
        updated = replace(workspace, updated_at=_updated_at(), version=workspace.version + 1)
        result = self._session.execute(
            update(WorkspaceRecord)
            .where(WorkspaceRecord.id == workspace.id, WorkspaceRecord.version == workspace.version)
            .values(
                name=updated.name,
                slug=updated.slug,
                status=updated.status.value,
                timezone=updated.timezone,
                locale=updated.locale,
                settings=updated.settings,
                updated_at=updated.updated_at,
                version=updated.version,
            )
        )
        _require_updated(result)
        return updated


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> None:
        values = user.__dict__ | {"status": user.status.value}
        self._session.add(UserRecord(**values))

    def get_by_external_identity(self, provider: str, subject: str) -> User | None:
        record = self._session.scalar(
            select(UserRecord).where(
                UserRecord.external_identity_provider == provider.lower(),
                UserRecord.external_subject == subject,
            )
        )
        return _user(record) if record else None

    def save(self, user: User) -> User:
        updated = replace(user, updated_at=_updated_at(), version=user.version + 1)
        result = self._session.execute(
            update(UserRecord)
            .where(UserRecord.id == user.id, UserRecord.version == user.version)
            .values(
                external_identity_provider=updated.external_identity_provider,
                external_subject=updated.external_subject,
                email=updated.email,
                display_name=updated.display_name,
                status=updated.status.value,
                updated_at=updated.updated_at,
                version=updated.version,
            )
        )
        _require_updated(result)
        return updated


class SqlAlchemyMembershipRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, membership: Membership) -> None:
        if membership.workspace_id != workspace_id:
            raise ValueError("membership workspace must match repository scope")
        _set_workspace_context(self._session, workspace_id)
        values = membership.__dict__ | {
            "role": membership.role.value,
            "status": membership.status.value,
        }
        self._session.add(MembershipRecord(**values))

    def list_for_workspace(self, workspace_id: UUID) -> Sequence[Membership]:
        _set_workspace_context(self._session, workspace_id)
        records = self._session.scalars(
            select(MembershipRecord).where(MembershipRecord.workspace_id == workspace_id)
        )
        return [_membership(record) for record in records]

    def get_for_user(self, workspace_id: UUID, user_id: UUID) -> Membership | None:
        _set_workspace_context(self._session, workspace_id)
        record = self._session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.workspace_id == workspace_id,
                MembershipRecord.user_id == user_id,
            )
        )
        return _membership(record) if record else None

    def save(self, workspace_id: UUID, membership: Membership) -> Membership:
        if membership.workspace_id != workspace_id:
            raise ValueError("membership workspace must match repository scope")
        _set_workspace_context(self._session, workspace_id)
        updated = replace(membership, updated_at=_updated_at(), version=membership.version + 1)
        result = self._session.execute(
            update(MembershipRecord)
            .where(
                MembershipRecord.id == membership.id,
                MembershipRecord.workspace_id == workspace_id,
                MembershipRecord.version == membership.version,
            )
            .values(
                user_id=updated.user_id,
                role=updated.role.value,
                status=updated.status.value,
                updated_at=updated.updated_at,
                version=updated.version,
            )
        )
        _require_updated(result)
        return updated
