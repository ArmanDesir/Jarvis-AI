"""Synthetic Phase 2.7 activities with no external effects."""

from __future__ import annotations

from typing import Any

from temporalio import activity

ALLOWED_SYNTHETIC_STEPS = frozenset(
    {"fake.prepare", "fake.transform", "fake.verify", "fake.wait_for_signal"}
)


@activity.defn(name="rightjob.synthetic_step")
async def synthetic_step(payload: dict[str, Any]) -> dict[str, Any]:
    step_type = payload.get("type")
    if step_type not in ALLOWED_SYNTHETIC_STEPS:
        raise ValueError("unapproved synthetic step type")
    return {
        "step_id": payload["id"],
        "type": step_type,
        "outcome": "succeeded",
        "evidence_ref": f"synthetic:{payload['id']}",
    }
