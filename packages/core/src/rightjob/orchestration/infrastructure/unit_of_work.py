"""Orchestration transaction boundary sharing Audit/Outbox persistence."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from rightjob.contracts.authorization import ExecutionAuthorizationConsumer
from rightjob.orchestration.application.repositories import AuditEvidenceAppender, OutboxAppender
from rightjob.orchestration.infrastructure.repositories import (
    SqlAlchemyExecutionRequestRepository,
    SqlAlchemyExecutionRunRepository,
    SqlAlchemyExecutionStepRepository,
)

AuditFactory = Callable[[Session], AuditEvidenceAppender]
OutboxFactory = Callable[[Session], OutboxAppender]
AuthorizationFactory = Callable[[Session], ExecutionAuthorizationConsumer]


class SqlAlchemyExecutionUnitOfWork:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        audit_factory: AuditFactory,
        outbox_factory: OutboxFactory,
        authorization_factory: AuthorizationFactory,
    ) -> None:
        self._session = session_factory()
        self.requests = SqlAlchemyExecutionRequestRepository(self._session)
        self.runs = SqlAlchemyExecutionRunRepository(self._session)
        self.steps = SqlAlchemyExecutionStepRepository(self._session)
        self.audit_evidence = audit_factory(self._session)
        self.outbox = outbox_factory(self._session)
        self.authorizations = authorization_factory(self._session)

    def __enter__(self) -> SqlAlchemyExecutionUnitOfWork:
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
