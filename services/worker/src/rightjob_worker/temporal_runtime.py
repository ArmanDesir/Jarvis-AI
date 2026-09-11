"""Phase 2.5 Temporal worker composition root."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from rightjob.contracts.revision_execution import RevisionExecutionContractError
from rightjob.database import register_sqlalchemy_mappings
from rightjob.orchestration.infrastructure.repositories import (
    SqlAlchemyRevisionActivityAuthority,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from temporalio.client import Client
from temporalio.worker import Worker

from rightjob_worker.execution_activities import synthetic_step
from rightjob_worker.execution_workflows import EXECUTION_WORKFLOWS
from rightjob_worker.proof_activities import (
    FakeExternalEffects,
    retry_activity,
    timeout_activity,
)
from rightjob_worker.proof_workflows import PROOF_WORKFLOWS
from rightjob_worker.revision_activities import RevisionActivities, RevisionActivityAuthority
from rightjob_worker.revision_workflows import REVISION_WORKFLOWS


@dataclass(frozen=True)
class TemporalSettings:
    target: str
    namespace: str
    task_queue: str
    credential: str | None
    tls: bool
    effect_db: Path
    database_url: str | None

    @classmethod
    def load(cls, values: Mapping[str, str] | None = None) -> "TemporalSettings":
        source = environ if values is None else values
        return cls(
            target=source.get("RIGHTJOB_TEMPORAL_TARGET", "127.0.0.1:7233"),
            namespace=source.get("RIGHTJOB_TEMPORAL_NAMESPACE", "default"),
            task_queue=source.get("RIGHTJOB_TEMPORAL_TASK_QUEUE", "rightjob-phase25-proof"),
            credential=source.get("RIGHTJOB_TEMPORAL_API_KEY") or None,
            tls=source.get("RIGHTJOB_TEMPORAL_TLS", "false").lower() == "true",
            effect_db=Path(
                source.get("RIGHTJOB_TEMPORAL_EFFECT_DB", "/tmp/rightjob-phase25-effects.sqlite3")
            ),
            database_url=source.get("RIGHTJOB_DATABASE_URL") or None,
        )


async def connect(settings: TemporalSettings) -> Client:
    options: dict[str, Any] = {"namespace": settings.namespace, "tls": settings.tls}
    if settings.credential:
        options["api" + "_key"] = settings.credential
    return await Client.connect(settings.target, **options)


async def run_temporal_worker(
    wait_for_stop: Callable[[], Awaitable[None]], settings: TemporalSettings
) -> None:
    client = await connect(settings)
    effects = FakeExternalEffects(settings.effect_db)
    database_engine = None
    if settings.database_url:
        register_sqlalchemy_mappings()
        database_engine = create_engine(settings.database_url)
        authority: RevisionActivityAuthority = SqlAlchemyRevisionActivityAuthority(
            sessionmaker(database_engine, class_=Session)
        )
    else:
        authority = _DenyRevisionActivityAuthority()
    revision = RevisionActivities(authority)
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[*PROOF_WORKFLOWS, *EXECUTION_WORKFLOWS, *REVISION_WORKFLOWS],
        activities=[
            retry_activity,
            timeout_activity,
            effects.execute,
            synthetic_step,
            revision.regenerate_artifact,
        ],
    )
    try:
        async with worker:
            await wait_for_stop()
    finally:
        if database_engine is not None:
            database_engine.dispose()


class _DenyRevisionActivityAuthority:
    def verify(self, request: dict[str, Any], workflow_id: str) -> None:
        raise RevisionExecutionContractError(
            "revision activity requires durable database authority"
        )
