"""One-session Policy/Approval transaction boundary."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from rightjob.policy.infrastructure.repositories import (
    SqlAlchemyApprovalDecisionRepository,
    SqlAlchemyApprovalRequestRepository,
    SqlAlchemyAuthorizationEvidenceRepository,
    SqlAlchemyExecutionAuthorizationRepository,
)
from rightjob.policy.repositories import AuditEvidenceAppender, OutboxAppender
from sqlalchemy.orm import Session, sessionmaker

AppenderFactory = Callable[[Session], AuditEvidenceAppender]
OutboxFactory = Callable[[Session], OutboxAppender]


class SqlAlchemyPolicyApprovalUnitOfWork:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        audit_factory: AppenderFactory,
        outbox_factory: OutboxFactory,
    ) -> None:
        self._session = session_factory()
        self.authorization_evidence = SqlAlchemyAuthorizationEvidenceRepository(self._session)
        self.approval_requests = SqlAlchemyApprovalRequestRepository(self._session)
        self.approval_decisions = SqlAlchemyApprovalDecisionRepository(self._session)
        self.execution_authorizations = SqlAlchemyExecutionAuthorizationRepository(self._session)
        self.audit_evidence = audit_factory(self._session)
        self.outbox = outbox_factory(self._session)

    def __enter__(self) -> SqlAlchemyPolicyApprovalUnitOfWork:
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
