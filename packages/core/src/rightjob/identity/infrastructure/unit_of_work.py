"""Identity/Tenancy SQLAlchemy transaction boundary."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from rightjob.identity.infrastructure.repositories import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)


class SqlAlchemyIdentityUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session = session_factory()
        self.workspaces = SqlAlchemyWorkspaceRepository(self._session)
        self.users = SqlAlchemyUserRepository(self._session)
        self.memberships = SqlAlchemyMembershipRepository(self._session)

    def __enter__(self) -> "SqlAlchemyIdentityUnitOfWork":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None or self._session.in_transaction():
            self.rollback()
        self.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def close(self) -> None:
        self._session.close()
