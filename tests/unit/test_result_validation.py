from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import CapabilityReference, ContractReference, SemanticVersion
from rightjob.contracts.review import (
    ArtifactReference,
    CapabilityResult,
    ResultContractError,
    ResultProvenance,
    ResultValidationContext,
    ResultValidationOutcome,
    ResultValidationReason,
    canonical_result_payload,
    result_digest,
)
from rightjob.registry import BUILT_IN_CAPABILITIES, BuiltInCapabilityRegistry
from rightjob.validation import CapabilityResultValidator

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
WORKSPACE_ID = UUID("21700000-0000-4000-8000-000000000001")
RUN_ID = UUID("21700000-0000-4000-8000-000000000002")
STEP_ID = UUID("21700000-0000-4000-8000-000000000003")
CORRELATION_ID = UUID("21700000-0000-4000-8000-000000000004")
CAUSATION_ID = UUID("21700000-0000-4000-8000-000000000005")
ARTIFACT_ID = UUID("21700000-0000-4000-8000-000000000006")


class Ids:
    def __init__(self) -> None:
        self.value = 100

    def __call__(self) -> UUID:
        self.value += 1
        return UUID(f"21700000-0000-4000-8000-{self.value:012d}")


def values(payload: object = None) -> tuple[CapabilityResult, ResultValidationContext]:
    capability = BUILT_IN_CAPABILITIES[0]
    payload_json = canonical_result_payload(
        {"outcome": "prepared"} if payload is None else payload  # type: ignore[arg-type]
    )
    artifact = ArtifactReference(ARTIFACT_ID, 1, result_digest(payload_json))
    provenance = ResultProvenance(
        WORKSPACE_ID,
        RUN_ID,
        STEP_ID,
        CORRELATION_ID,
        CAUSATION_ID,
        capability.reference,
        capability.output_contract,
        artifact,
        NOW,
    )
    return CapabilityResult(provenance, payload_json), ResultValidationContext(
        WORKSPACE_ID,
        RUN_ID,
        STEP_ID,
        CORRELATION_ID,
        CAUSATION_ID,
        capability.reference,
        capability.output_contract,
        artifact,
    )


def validate(result: CapabilityResult, context: ResultValidationContext, *, at: datetime = NOW):
    return CapabilityResultValidator(BuiltInCapabilityRegistry(), Ids(), lambda: at).validate(
        result, context
    )


def test_valid_result_is_immutable_bounded_and_has_exact_evidence() -> None:
    result, context = values()
    evidence = validate(result, context)

    assert evidence.outcome is ResultValidationOutcome.PASSED
    assert evidence.reasons == (ResultValidationReason.ACCEPTED,)
    assert tuple(item.evidence_key for item in evidence.evidence) == (
        "artifact.sha256",
        "capability.version",
        "output.contract",
    )
    assert evidence.provenance == result.provenance
    with pytest.raises(FrozenInstanceError):
        result.provenance.run_id = UUID(int=1)  # type: ignore[misc]


@pytest.mark.parametrize("field", ["workspace_id", "run_id", "step_id", "correlation_id"])
def test_trusted_provenance_mismatch_fails_closed(field: str) -> None:
    result, context = values()
    bad = replace(context, **{field: UUID("21700000-0000-4000-8000-000000009999")})
    evidence = validate(result, bad)
    assert evidence.outcome is ResultValidationOutcome.FAILED
    assert ResultValidationReason.PROVENANCE_MISMATCH in evidence.reasons


def test_causation_mismatch_fails_closed() -> None:
    result, context = values()
    evidence = validate(result, replace(context, causation_id=UUID(int=1)))
    assert ResultValidationReason.PROVENANCE_MISMATCH in evidence.reasons


def test_exact_capability_identity_and_version_are_re_resolved() -> None:
    result, context = values()
    wrong_identity = replace(
        context.capability,
        capability_definition_id=UUID("21700000-0000-4000-8000-000000009999"),
    )
    mismatch = validate(result, replace(context, capability=wrong_identity))
    assert ResultValidationReason.CAPABILITY_MISMATCH in mismatch.reasons

    unknown = CapabilityReference(
        UUID("21700000-0000-4000-8000-000000009998"),
        "fake.missing",
        SemanticVersion.parse("1.0.0"),
    )
    unavailable = validate(result, replace(context, capability=unknown))
    assert ResultValidationReason.CAPABILITY_UNAVAILABLE in unavailable.reasons


def test_result_supplied_capability_and_output_metadata_are_untrusted() -> None:
    result, context = values()
    wrong_capability = replace(
        result.provenance.capability,
        capability_definition_id=UUID("21700000-0000-4000-8000-000000009997"),
    )
    capability_result = replace(
        result, provenance=replace(result.provenance, capability=wrong_capability)
    )
    assert (
        ResultValidationReason.CAPABILITY_MISMATCH in validate(capability_result, context).reasons
    )

    wrong_output = ContractReference("fake.untrusted.output", SemanticVersion.parse("1.0.0"), 4_096)
    output_result = replace(
        result, provenance=replace(result.provenance, output_contract=wrong_output)
    )
    assert (
        ResultValidationReason.OUTPUT_CONTRACT_MISMATCH in validate(output_result, context).reasons
    )


def test_disabled_capability_is_stale_and_fails_closed() -> None:
    result, context = values()
    disabled = replace(BUILT_IN_CAPABILITIES[0], enabled=False)
    catalog = BuiltInCapabilityRegistry((disabled, *BUILT_IN_CAPABILITIES[1:]))
    evidence = CapabilityResultValidator(catalog, Ids(), lambda: NOW).validate(result, context)
    assert ResultValidationReason.CAPABILITY_UNAVAILABLE in evidence.reasons


def test_output_contract_artifact_and_timestamp_must_match() -> None:
    result, context = values()
    wrong_contract = ContractReference("fake.wrong.output", SemanticVersion.parse("1.0.0"), 4_096)
    output = validate(result, replace(context, output_contract=wrong_contract))
    assert ResultValidationReason.OUTPUT_CONTRACT_MISMATCH in output.reasons

    artifact = replace(context.artifact, version=2)
    artifact_result = validate(result, replace(context, artifact=artifact))
    assert ResultValidationReason.ARTIFACT_MISMATCH in artifact_result.reasons

    future = replace(result, provenance=replace(result.provenance, produced_at=NOW + timedelta(1)))
    timestamp = validate(future, context)
    assert ResultValidationReason.INVALID_TIMESTAMP in timestamp.reasons


def test_canonical_sha_payload_and_capability_bound_are_enforced() -> None:
    result, context = values({"value": "x" * 4_100})
    evidence = validate(result, context)
    assert ResultValidationReason.PAYLOAD_TOO_LARGE in evidence.reasons

    with pytest.raises(ResultContractError, match="canonical"):
        CapabilityResult(result.provenance, b'{"z": 1}')
    with pytest.raises(ResultContractError, match="secret-bearing"):
        canonical_result_payload({"token": "must-not-enter-results"})


def test_nil_ids_naive_timestamps_and_invalid_hashes_are_rejected() -> None:
    result, _ = values()
    with pytest.raises(ResultContractError, match="nil"):
        replace(result.provenance, run_id=UUID(int=0))
    with pytest.raises(ResultContractError, match="timezone-aware"):
        replace(result.provenance, produced_at=NOW.replace(tzinfo=None))
    with pytest.raises(ResultContractError, match="SHA-256"):
        replace(result.provenance.artifact, sha256="not-a-digest")


def test_malformed_json_and_payload_artifact_sha_mismatch_are_rejected() -> None:
    result, _ = values()
    with pytest.raises(ResultContractError, match="UTF-8 JSON"):
        CapabilityResult(result.provenance, b"{")

    wrong_artifact = replace(result.provenance.artifact, sha256="0" * 64)
    wrong_provenance = replace(result.provenance, artifact=wrong_artifact)
    with pytest.raises(ResultContractError, match="does not match"):
        CapabilityResult(wrong_provenance, result.payload_json)
