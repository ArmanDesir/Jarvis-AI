"""Bounded synthetic artifact regeneration with no external effects."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from temporalio import activity


class RevisionActivityAuthority(Protocol):
    def verify(self, request: dict[str, Any], workflow_id: str) -> None: ...


class RevisionActivities:
    def __init__(self, authority: RevisionActivityAuthority) -> None:
        self._authority = authority

    @activity.defn(name="rightjob.revision.regenerate_artifact")
    async def regenerate_artifact(self, request: dict[str, Any]) -> dict[str, Any]:
        workflow_id = activity.info().workflow_id
        if workflow_id is None:
            raise ValueError("revision activity requires workflow identity")
        self._authority.verify(request, workflow_id)
        return regenerate_artifact_result(request)


def regenerate_artifact_result(request: dict[str, Any]) -> dict[str, Any]:
    required = {
        "action_type",
        "claim_id",
        "workspace_id",
        "quality_gate_id",
        "quality_decision_id",
        "cycle",
        "run_id",
        "step_id",
        "correlation_id",
        "causation_id",
        "capability_id",
        "capability_key",
        "capability_version",
        "artifact_id",
        "source_version",
        "source_sha256",
        "target_version",
        "workflow_id",
        "request_id",
        "department_id",
        "department_key",
        "department_version",
        "quality_policy_key",
        "quality_policy_version",
        "action_digest",
        "authorization_id",
        "approval_request_id",
        "approval_decision_id",
        "expected_gate_version",
    }
    if set(request) != required or request["action_type"] != "regenerate_artifact":
        raise ValueError("only the closed REGENERATE_ARTIFACT projection is permitted")
    if request["target_version"] != request["source_version"] + 1:
        raise ValueError("revision target must advance exactly one version")
    payload = {
        "artifact_id": request["artifact_id"],
        "capability": {
            "key": request["capability_key"],
            "version": request["capability_version"],
        },
        "claim_id": request["claim_id"],
        "revision_cycle": request["cycle"],
        "source_sha256": request["source_sha256"],
        "version": request["target_version"],
        "workspace_id": request["workspace_id"],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if digest == request["source_sha256"]:
        raise ValueError("synthetic revision did not change artifact content")
    return {"payload_json": encoded.decode("utf-8"), "sha256": digest, **request}
