from dataclasses import replace
from uuid import UUID

import pytest
from rightjob.identity.application.authentication import ExternalIdentity
from rightjob.identity.application.service import (
    IdentityResolutionCode,
    IdentityResolutionError,
    IdentityService,
)
from rightjob.identity.domain.entities import Membership, User, Workspace
from rightjob.identity.domain.values import MembershipRole, RecordStatus

WORKSPACE_A = Workspace(
    id=UUID("0198ff00-0000-7000-8000-000000000101"), name="A", slug="workspace-a"
)
WORKSPACE_B = Workspace(
    id=UUID("0198ff00-0000-7000-8000-000000000102"), name="B", slug="workspace-b"
)
USER = User(
    id=UUID("0198ff00-0000-7000-8000-000000000111"),
    external_identity_provider="test-oidc",
    external_subject="subject-1",
    email="user@example.test",
    display_name="User",
)
MEMBERSHIP_A = Membership(
    id=UUID("0198ff00-0000-7000-8000-000000000121"),
    workspace_id=WORKSPACE_A.id,
    user_id=USER.id,
    role=MembershipRole.OWNER,
)
MEMBERSHIP_B = Membership(
    id=UUID("0198ff00-0000-7000-8000-000000000122"),
    workspace_id=WORKSPACE_B.id,
    user_id=USER.id,
    role=MembershipRole.MEMBER,
)
IDENTITY = ExternalIdentity("test-oidc", "subject-1")


class Users:
    def __init__(self, user: User | None = USER) -> None:
        self.user = user

    def add(self, user: User) -> None:
        raise AssertionError("read-only test")

    def get_by_external_identity(self, provider: str, subject: str) -> User | None:
        if self.user and (provider, subject) == (
            self.user.external_identity_provider,
            self.user.external_subject,
        ):
            return self.user
        return None


class Memberships:
    def __init__(self, memberships: tuple[Membership, ...]) -> None:
        self.memberships = memberships

    def add(self, workspace_id: UUID, membership: Membership) -> None:
        raise AssertionError("read-only test")

    def list_for_workspace(self, workspace_id: UUID) -> tuple[Membership, ...]:
        return tuple(item for item in self.memberships if item.workspace_id == workspace_id)

    def get_for_user(self, workspace_id: UUID, user_id: UUID) -> Membership | None:
        return next(
            (
                item
                for item in self.memberships
                if item.workspace_id == workspace_id and item.user_id == user_id
            ),
            None,
        )


class Workspaces:
    def __init__(self, workspaces: tuple[Workspace, ...]) -> None:
        self.workspaces = workspaces

    def add(self, workspace: Workspace) -> None:
        raise AssertionError("read-only test")

    def get(self, workspace_id: UUID) -> Workspace | None:
        return next((item for item in self.workspaces if item.id == workspace_id), None)


def _service(
    memberships: tuple[Membership, ...] = (MEMBERSHIP_A, MEMBERSHIP_B),
    user: User | None = USER,
) -> IdentityService:
    return IdentityService(
        Users(user), Memberships(memberships), Workspaces((WORKSPACE_A, WORKSPACE_B))
    )


def test_user_in_workspace_builds_minimal_principal() -> None:
    context = _service().resolve(IDENTITY, WORKSPACE_A.id)
    assert context.principal.user_id == USER.id
    assert context.principal.workspace_id == WORKSPACE_A.id
    assert context.principal.roles == ("owner",)
    assert context.principal.permissions == ()


def test_multiple_memberships_resolve_only_requested_workspace() -> None:
    context = _service().resolve(IDENTITY, WORKSPACE_B.id)
    assert context.membership.id == MEMBERSHIP_B.id
    assert context.principal.roles == ("member",)


def test_user_not_in_workspace_is_denied() -> None:
    with pytest.raises(IdentityResolutionError) as caught:
        _service((MEMBERSHIP_A,)).resolve(IDENTITY, WORKSPACE_B.id)
    assert caught.value.code is IdentityResolutionCode.NOT_A_MEMBER


def test_inactive_membership_is_denied() -> None:
    inactive = replace(MEMBERSHIP_A, status=RecordStatus.SUSPENDED)
    with pytest.raises(IdentityResolutionError) as caught:
        _service((inactive,)).resolve(IDENTITY, WORKSPACE_A.id)
    assert caught.value.code is IdentityResolutionCode.MEMBERSHIP_INACTIVE


def test_inactive_user_is_denied() -> None:
    with pytest.raises(IdentityResolutionError) as caught:
        _service(user=replace(USER, status=RecordStatus.SUSPENDED)).resolve(
            IDENTITY, WORKSPACE_A.id
        )
    assert caught.value.code is IdentityResolutionCode.USER_INACTIVE


def test_inactive_workspace_is_denied() -> None:
    service = IdentityService(
        Users(),
        Memberships((MEMBERSHIP_A,)),
        Workspaces((replace(WORKSPACE_A, status=RecordStatus.SUSPENDED),)),
    )
    with pytest.raises(IdentityResolutionError) as caught:
        service.resolve(IDENTITY, WORKSPACE_A.id)
    assert caught.value.code is IdentityResolutionCode.WORKSPACE_INACTIVE
