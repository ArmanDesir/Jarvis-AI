"""Synthetic Temporal workflows used only by the Phase 2.5 proof."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, TimeoutError


def _event(name: str, data: dict[str, Any], **extra: object) -> None:
    context = data["context"]
    workflow.logger.info(
        name,
        extra={
            "correlation_id": context["correlation_id"],
            "workspace_id": context["workspace_id"],
            "workflow_id": workflow.info().workflow_id,
            **extra,
        },
    )


def _result(data: dict[str, Any], **value: object) -> dict[str, Any]:
    context = data["context"]
    return {
        **value,
        "correlation_id": context["correlation_id"],
        "workspace_id": context["workspace_id"],
        "workflow_id": workflow.info().workflow_id,
    }


@workflow.defn(name="proof.durable-counter")
class DurableCounterWorkflow:
    def __init__(self) -> None:
        self._count = 0
        self._complete = False

    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        self._count += 1
        _event("workflow.waiting", data, count=self._count)
        await workflow.wait_condition(lambda: self._complete)
        return _result(data, state="completed", count=self._count)

    @workflow.signal(name="resume")
    async def resume(self, _payload: dict[str, Any]) -> None:
        self._count += 1
        self._complete = True

    @workflow.query(name="state")
    def state(self) -> dict[str, Any]:
        return {"count": self._count, "waiting": not self._complete}


@workflow.defn(name="proof.retry")
class RetryWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "proof.retry",
            {
                "fail_attempts": data["payload"]["fail_attempts"],
                "correlation_id": data["context"]["correlation_id"],
                "workspace_id": data["context"]["workspace_id"],
            },
            result_type=dict,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=100),
                backoff_coefficient=1,
                maximum_attempts=int(data["payload"]["maximum_attempts"]),
            ),
        )
        return _result(data, **dict(result))


@workflow.defn(name="proof.approval")
class ApprovalWorkflow:
    def __init__(self) -> None:
        self._approved = False
        self._signal_count = 0

    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        _event("workflow.approval-wait", data)
        await workflow.wait_condition(lambda: self._approved)
        _event("workflow.approval-resume", data)
        return _result(data, state="approved", accepted_signals=self._signal_count)

    @workflow.signal(name="approve")
    async def approve(self, _payload: dict[str, Any]) -> None:
        if not self._approved:
            self._approved = True
            self._signal_count += 1


@workflow.defn(name="proof.cancellation")
class CancellationWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        _event("workflow.cancellation-wait", data)
        await workflow.wait_condition(lambda: False)
        return {"state": "unreachable"}


@workflow.defn(name="proof.timeout")
class TimeoutWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            await workflow.execute_activity(
                "proof.timeout",
                {
                    "seconds": data["payload"]["sleep_seconds"],
                    "correlation_id": data["context"]["correlation_id"],
                    "workspace_id": data["context"]["workspace_id"],
                },
                start_to_close_timeout=timedelta(seconds=float(data["payload"]["timeout_seconds"])),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        except ActivityError as error:
            if isinstance(error.cause, TimeoutError):
                _event("workflow.activity-timeout", data)
                return _result(data, state="timed_out")
            raise
        return _result(data, state="unexpected_completion")


async def _effect(request: dict[str, Any]) -> dict[str, Any]:
    return dict(
        await workflow.execute_activity(
            "proof.external-effect",
            request,
            result_type=dict,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
    )


@workflow.defn(name="proof.idempotent-effect")
class IdempotentEffectWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        request = {
            "idempotency_key": data["payload"]["idempotency_key"],
            "correlation_id": data["context"]["correlation_id"],
            "workspace_id": data["context"]["workspace_id"],
        }
        first = await _effect(request)
        second = await _effect(request)
        return _result(data, first=first, second=second)


@workflow.defn(name="proof.unknown-outcome")
class UnknownOutcomeWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        result = await _effect(
            {
                "idempotency_key": data["payload"]["idempotency_key"],
                "simulate_unknown": True,
                "correlation_id": data["context"]["correlation_id"],
                "workspace_id": data["context"]["workspace_id"],
            }
        )
        if result["outcome"] == "unknown":
            _event("workflow.reconciliation-required", data)
            return _result(data, state="reconciliation_required", effect=result)
        return _result(data, state=result["outcome"], effect=result)


@workflow.defn(name="proof.versioned")
class VersionedWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        implementation = "v2" if workflow.patched("phase25-version-2") else "v1"
        return _result(
            data,
            implementation=implementation,
            input_version=data["context"]["workflow_version"],
        )


PROOF_WORKFLOWS = [
    DurableCounterWorkflow,
    RetryWorkflow,
    ApprovalWorkflow,
    CancellationWorkflow,
    TimeoutWorkflow,
    IdempotentEffectWorkflow,
    UnknownOutcomeWorkflow,
    VersionedWorkflow,
]
