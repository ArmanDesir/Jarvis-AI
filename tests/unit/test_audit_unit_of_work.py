from unittest.mock import MagicMock

import pytest
from rightjob.audit.infrastructure.unit_of_work import SqlAlchemyAuditUnitOfWork
from sqlalchemy.orm import Session


def _unit_of_work() -> tuple[SqlAlchemyAuditUnitOfWork, MagicMock]:
    session = MagicMock(spec=Session)
    session.in_transaction.return_value = True
    factory = MagicMock(return_value=session)
    return SqlAlchemyAuditUnitOfWork(factory), session  # type: ignore[arg-type]


def test_commit_is_explicit_and_session_closes() -> None:
    unit_of_work, session = _unit_of_work()
    session.in_transaction.return_value = False

    with unit_of_work:
        unit_of_work.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_uncommitted_transaction_rolls_back_and_closes() -> None:
    unit_of_work, session = _unit_of_work()

    with unit_of_work:
        pass

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_exception_rolls_back_and_closes() -> None:
    unit_of_work, session = _unit_of_work()

    with pytest.raises(RuntimeError, match="stop"), unit_of_work:
        raise RuntimeError("stop")

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
