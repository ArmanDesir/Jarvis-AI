"""Test-only composition for the approved localhost Phase 2.4 runtime proof."""

from __future__ import annotations

import atexit
import os

from rightjob.identity.application.authentication import JwtAuthenticationProvider
from rightjob.identity.application.service import IdentityService
from rightjob.identity.infrastructure.jwt import PyJwtVerifier
from rightjob.identity.infrastructure.repositories import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from rightjob.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWork
from rightjob_api.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

database_url = os.environ["RIGHTJOB_RLS_TEST_DATABASE_URL"]
verification_key = os.environ["RIGHTJOB_PHASE24_TEST_JWT_KEY"]
engine = create_engine(database_url)
identity_session = Session(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False)

app.state.authentication_provider = JwtAuthenticationProvider(
    "test", PyJwtVerifier(verification_key, ("HS256",))
)
app.state.identity_service = IdentityService(
    SqlAlchemyUserRepository(identity_session),
    SqlAlchemyMembershipRepository(identity_session),
    SqlAlchemyWorkspaceRepository(identity_session),
)
app.state.identity_uow_factory = lambda: SqlAlchemyIdentityUnitOfWork(factory)


@atexit.register
def close_database() -> None:
    identity_session.close()
    engine.dispose()
