"""Synthetic local Activities; no real external effects."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError


@activity.defn(name="proof.retry")
async def retry_activity(request: dict[str, Any]) -> dict[str, int]:
    attempt = activity.info().attempt
    activity.logger.info(
        "activity.retry",
        extra={
            "attempt": attempt,
            "correlation_id": request["correlation_id"],
            "workspace_id": request["workspace_id"],
            "workflow_id": activity.info().workflow_id,
        },
    )
    if attempt <= int(request["fail_attempts"]):
        raise ApplicationError("synthetic retry failure")
    return {"attempt": attempt}


@activity.defn(name="proof.timeout")
async def timeout_activity(request: dict[str, Any]) -> None:
    activity.logger.info(
        "activity.timeout-start",
        extra={
            "attempt": activity.info().attempt,
            "correlation_id": request["correlation_id"],
            "workspace_id": request["workspace_id"],
            "workflow_id": activity.info().workflow_id,
        },
    )
    await asyncio.sleep(float(request["seconds"]))


class FakeExternalEffects:
    """SQLite-backed proof adapter so idempotency survives worker restart."""

    def __init__(self, path: Path) -> None:
        self._path = path
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS effects "
                "(idempotency_key TEXT PRIMARY KEY, outcome TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    @activity.defn(name="proof.external-effect")
    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.apply(request)
        activity.logger.info(
            "activity.external-effect",
            extra={
                "attempt": activity.info().attempt,
                "correlation_id": request["correlation_id"],
                "workspace_id": request["workspace_id"],
                "workflow_id": activity.info().workflow_id,
                "outcome": result["outcome"],
            },
        )
        return result

    def apply(self, request: dict[str, Any]) -> dict[str, Any]:
        key = str(request["idempotency_key"])
        unknown = bool(request.get("simulate_unknown", False))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT outcome FROM effects WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if row is None:
                outcome = "unknown" if unknown else "succeeded"
                connection.execute("INSERT INTO effects VALUES (?, ?)", (key, outcome))
            else:
                outcome = str(row[0])
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effects WHERE idempotency_key = ?", (key,)
                ).fetchone()[0]
            )
        return {"outcome": outcome, "effect_count": count}

    def count(self, key: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM effects WHERE idempotency_key = ?", (key,)
                ).fetchone()[0]
            )
