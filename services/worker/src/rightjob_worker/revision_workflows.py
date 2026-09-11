"""Deterministic bounded revision workflow."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="rightjob.revision.regenerate_artifact")
class RevisionArtifactWorkflow:
    @workflow.run
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await workflow.execute_activity(
                "rightjob.revision.regenerate_artifact",
                request,
                result_type=dict,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            ),
        )


REVISION_WORKFLOWS = [RevisionArtifactWorkflow]
