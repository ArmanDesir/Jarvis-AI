"""Temporal mechanics for approved synthetic compiled executions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from rightjob_worker.execution_activities import synthetic_step


@workflow.defn(name="rightjob.synthetic.sequence")
class SyntheticSequenceWorkflow:
    @workflow.run
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for step in request["payload"]["steps"]:
            result = await workflow.execute_activity(
                synthetic_step,
                step,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=step["max_attempts"]),
            )
            results.append(result)
        return {
            "state": "succeeded",
            "workspace_id": request["context"]["workspace_id"],
            "correlation_id": request["context"]["correlation_id"],
            "results": results,
        }


@workflow.defn(name="rightjob.synthetic.signal")
class SyntheticSignalWorkflow:
    def __init__(self) -> None:
        self._released = False

    @workflow.signal(name="resume")
    def resume(self, _: dict[str, Any]) -> None:
        self._released = True

    @workflow.run
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        await workflow.wait_condition(lambda: self._released)
        step = request["payload"]["steps"][0]
        result = await workflow.execute_activity(
            synthetic_step,
            step,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=step["max_attempts"]),
        )
        return {
            "state": "succeeded",
            "workspace_id": request["context"]["workspace_id"],
            "correlation_id": request["context"]["correlation_id"],
            "results": [result],
        }


EXECUTION_WORKFLOWS = [SyntheticSequenceWorkflow, SyntheticSignalWorkflow]
