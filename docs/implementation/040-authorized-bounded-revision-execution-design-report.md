# Phase 2.20 Stage C1 — Durable Revision Runtime Lifecycle Foundation

Date: 2026-08-28

## Implemented source-only boundary

Stage A published runtime-validated immutable revision action, authorization-reference, command,
claim, evidence, lifecycle, outcome, reason, and artifact-submission contracts. A pure
Orchestration-owned claim service verifies the exact Phase 2.19 `REVISION_REQUIRED` decision and
current state, the already-reserved cycle, exact enabled Capability and Department Registry
definitions, current Capability quality policy, fresh Policy evidence, a fresh action digest, and
fresh human approval when Policy requires it. It prepares an idempotent claim and safe evidence in
memory only. It does not persist, launch, schedule, authorize a real runtime, or execute a revision.

`REVISION_REQUIRED` is governance evidence and reservation consumption, never execution authority.
Reviewer, Executive, AI Router, Planner, provider, user, and result prose cannot authorize work.
Every claim needs a fresh Policy evaluation and fresh revision authorization. Prior execution
authorization is explicitly bound and rejected as the new authorization identity. Approval may be
omitted only for a current `ALLOW`; `REQUIRE_APPROVAL` requires a current approved request and human
decision bound to the exact action digest; `DENY` always stops.

## Safe revision action and digest

The only Stage A action is closed `regenerate_artifact`. It may produce exactly the next version of
the same artifact identity for the same Workspace, gate decision, reserved cycle, plan/run/step,
Department, Capability, and quality policy. It may change artifact content only through the later
Capability boundary. The result must advance version by one and have a different SHA-256.

The canonical action snapshot contains schema/action type; Workspace; gate/decision/cycle;
planning request/plan/run/step/correlation/causation; exact Department and Capability identities and
versions; source artifact identity/version/SHA-256; next target identity/version; quality-policy
identity/version; and prior execution-authorization identity. Canonical JSON SHA-256 binds all of
it. No Reviewer reason/reference, prompt, provider/user prose, credential, payload, code, shell text,
or arbitrary instruction is accepted or projected.

## Claim and authority rules

- Cycle is structurally limited to `1` or `2`; it must equal the durable state count and the
  decision's `revision_count_after`, which must equal `revision_count_before + 1`.
- State must be the exact `REVISION_REQUIRED` next state and expected optimistic version.
- Exact command replay returns the existing claim and emits no new effects. Same command ID with
  different content conflicts. A different command for an already-claimed gate/decision/cycle
  conflicts. Database uniqueness and optimistic concurrency will select one concurrent winner.
- A second-cycle reservation may be claimed once. Cycle three is invalid by construction.
- Claims and every failure preserve the Phase 2.19 reservation; execution failure/cancellation never
  refunds it.
- Policy is evaluated after Registry re-resolution and immediately before the claim transaction.
  Registry disable/version/ownership change, quality-policy change, artifact/state change, expired
  authorization, or stale/revoked approval fails closed before launch.

The existing generic `AuthorizationEvidence` canonical snapshot/digest mechanism can safely carry
the safe revision snapshot. Existing plan-specific `ExecutionAuthorization` cannot be reused.
`RevisionExecutionAuthorizationReference` is the smallest extension: it binds the fresh evidence,
Policy evaluation, action digest, lifetime, and optional approval identities. Approval binds the
same digest, not a weaker parent digest.

## Lifecycle and claim/launch boundary

Closed lifecycle vocabulary is `CLAIMED`, `LAUNCH_PENDING`, `RUNNING`, `COMPLETED`, `FAILED`,
`RECONCILIATION_REQUIRED`, and `CANCELLED`.

The claim transaction durably creates `CLAIMED` plus execution request/run/step linkage,
safe evidence, Audit, and an Outbox launch intent. Commit occurs once before launch. The relay or
future application boundary may mark `LAUNCH_PENDING` before calling a workflow-engine boundary
with workflow ID `revision:{workspace_id}:{quality_gate_id}:{quality_decision_id}:{cycle}`. Temporal
input is the safe typed claim projection only. Temporal acceptance moves to `RUNNING`; an unknown
launch result moves to `RECONCILIATION_REQUIRED` and is reconciled by the deterministic workflow ID,
never blindly relaunched. Activity transport retries remain distinct from the two content-revision
reservations. Permanent failure/cancellation is terminal for that claim and does not refund it.

Completion accepts only a `RevisionArtifactSubmission` plus `PASSED` `ResultValidationEvidence`
whose Workspace/run/step/Capability/artifact provenance exactly matches the claim, advances the same
artifact by one version, and changes SHA-256. One atomic completion transaction records result and
validation evidence, marks the claim complete, and returns the quality gate to `AWAITING_REVIEW`.
Invalid/missing validation does not advance the gate. It does not automatically run another quality
decision.

## Implemented migration `20260827_0006_revision_execution`

Stage B creates `revision=20260827_0006`, `down_revision=20260827_0005`.

One Orchestration-owned `revision_execution_claims` table is sufficient because existing durable
Policy evidence and Approval rows remain the authority records, while this row is the unique
consumption/lifecycle record.

| Column | SQL type / rule | Purpose |
|---|---|---|
| workspace_id, claim_id | UUID, `id` PK plus tenant-leading unique pair | claim identity |
| command_id | UUID NOT NULL | restart-safe idempotency identity |
| quality_gate_id, quality_decision_id | UUID NOT NULL | exact governance source |
| reserved_cycle | SMALLINT CHECK IN (1,2) | bounded consumed reservation |
| planning_request_id, plan_id, source_run_id, source_step_id | UUID NOT NULL | execution provenance |
| correlation_id, causation_id | UUID, causation nullable | trace provenance |
| department_definition_id/key/version | UUID/VARCHAR | exact Registry Department |
| capability_definition_id/key/version | UUID/VARCHAR | exact Registry Capability |
| quality_policy_key/version | VARCHAR | exact trusted policy |
| action_type, action_digest | VARCHAR / CHAR(64) | closed action and SHA-256 binding |
| prior_execution_authorization_id | UUID NOT NULL | proves prior authority is not reused |
| authorization_evidence_id | UUID NOT NULL | fresh authority linkage through Policy evidence |
| approval_request_id, approval_decision_id | UUID nullable pair | required-approval linkage |
| source_artifact_id/version/sha256 | UUID/INTEGER/CHAR(64) | immutable source binding |
| target_artifact_id/version | UUID/INTEGER | bounded next artifact target |
| execution_request_id, execution_run_id, execution_step_id | UUID NOT NULL | runtime ownership linkage created atomically with claim |
| status, lifecycle_reason | closed VARCHAR CHECKs | lifecycle state and safe exception reason |
| workflow_id | VARCHAR(255), nullable only while CLAIMED, tenant-unique | deterministic workflow ownership |
| launch_pending_at, running_at, reconciliation_required_at | TIMESTAMPTZ nullable | trusted launch lifecycle evidence |
| completed_at, failed_at, cancelled_at | TIMESTAMPTZ nullable | trusted terminal evidence |
| result_artifact_id/version/sha256 | UUID/INTEGER/CHAR(64), nullable set | validated result linkage required for COMPLETED |
| result_validation_evidence_id | UUID nullable | PASSED validation identity only |
| last_lifecycle_command_id/digest | UUID/CHAR(64) nullable pair | deterministic transition idempotency |
| version | INTEGER CHECK >=1 | optimistic concurrency |
| claimed_at, created_at, updated_at | TIMESTAMPTZ | trusted row timestamps |

Required constraints: tenant/execution composite foreign keys with `ON DELETE RESTRICT`; composite
FK to the exact quality-gate decision and state ownership; exact source/target artifact identity;
target version = source version + 1; approval columns all-null or all-non-null; result/validation
columns complete as a set; lowercase 64-character hex hashes; lifecycle/timestamp consistency;
unique `(workspace_id, command_id)` and `(workspace_id, quality_gate_id, quality_decision_id,
reserved_cycle)`; unique non-null execution IDs. State updates use `WHERE workspace_id=? AND
claim_id=? AND version=?`, exactly one row required. Indexes lead with Workspace for gate/decision,
status/updated time, execution linkage, and authorization linkage.

Enable and force RLS. `USING` and `WITH CHECK` use the established
`workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid` expression. Application-role
cross-Workspace read/write tests are required. Downgrade drops only this table, its policies,
indexes, and Phase 2.20 constraints; it restores head `20260827_0005` and never rewrites Phase 2.19
data.

## Implemented durable claim and lifecycle transactions

The claim transaction loads exact state and decision; locks/compares expected state version; re-resolves
Registries; verify current Policy/evidence/Approval; insert one claim and execution request/run/step
linkage; append safe claim evidence, Audit, and Outbox launch intent; commit once. Any failure rolls
back all. The created run remains `QUEUED` and step `PENDING`; no launch follows commit. No Outbox
relay is implemented in Stage B; runtime
authorization must choose the repository's existing delivery boundary or stop for owner review.

Stage C1 adds legal, optimistic lifecycle persistence for `CLAIMED → LAUNCH_PENDING`,
`LAUNCH_PENDING → RUNNING`, `LAUNCH_PENDING → RECONCILIATION_REQUIRED`,
`RECONCILIATION_REQUIRED → RUNNING`, and `RUNNING → FAILED|CANCELLED|COMPLETED`. Exact command replay
returns the current row without duplicate Audit or Outbox; conflicting replay and stale versions
fail closed. Closed failure/reconciliation reasons replace arbitrary diagnostics.

Completion compares the exact claim, workflow, execution linkage, artifact submission, and PASSED
validation provenance; updates claim/result, run, step, and quality gate; appends safe Audit and
Outbox; and commits once. The gate moves to `AWAITING_REVIEW`, the reservation count is unchanged,
and no Reviewer or next quality decision is invoked. No raw artifact, validation diagnostic,
Reviewer/provider/user prose, exception text, or credential is persisted.

Stage C1.1 distinguishes a definite pre-launch rejection from an ambiguous launch outcome without
fabricating runtime evidence. Only `LAUNCH_PENDING → FAILED` with closed reason `LAUNCH_REJECTED`
may omit `running_at`; it still requires `launch_pending_at` and `failed_at`. Other failures remain
RUNNING-origin failures and require `running_at`. Ambiguity remains `RECONCILIATION_REQUIRED`.
Neither path refunds a reservation, retries launch, invokes Reviewer, or runs another decision.

Stage C1.2 makes that definite-rejection transition transactionally terminal across its exact
revision execution linkage. The revision lifecycle service alone changes the claim to
`FAILED(LAUNCH_REJECTED)`, its linked run from `QUEUED` to `FAILED`, and its linked revision step
from `PENDING` to `FAILED` in one Unit-of-Work commit. The run and step retain null `started_at`
values because no workflow or activity began. The step uses the existing closed
`INFRASTRUCTURE_EXHAUSTED` failure classification; no provider/Temporal exception text is stored.
This narrow operation does not add `QUEUED → FAILED` or `PENDING → FAILED` to the ordinary
execution transition tables. Any run, step, Audit, or Outbox failure rolls the transaction back,
and exact replay produces no duplicate evidence.

## Crash and unknown-outcome matrix

| Failure point | Durable state | Safe action | Authority / reservation |
|---|---|---|---|
| before claim commit | no claim | retry full fresh checks | authorization rechecked; reservation remains consumed |
| after commit, before launch | CLAIMED | idempotently deliver launch intent | bound authority; reservation consumed |
| launch definitely rejected | FAILED | no relaunch without new governed command | not reusable; consumed |
| launch definitely accepted | RUNNING | observe deterministic workflow ID | consumed authorization; consumed reservation |
| launch result unknown | RECONCILIATION_REQUIRED | query/reconcile workflow ID; no blind retry | not reusable; consumed |
| crash after Temporal accepts, before acknowledgement | RECONCILIATION_REQUIRED | reconcile to existing workflow | not reusable; consumed |
| worker crash | RUNNING | Temporal resumes deterministic workflow | same execution only; consumed |
| activity retry | RUNNING | only declared transport/activity retry | no new content cycle; consumed |
| permanent activity failure | FAILED | terminal/manual review | no refund |
| cancellation | CANCELLED | terminal/manual review | no refund |
| crash after artifact creation, before completion | RUNNING or reconciliation | idempotently recover artifact identity then validate | no new launch; consumed |
| validation failure | FAILED | no gate advancement | no refund |
| completion transaction failure | RUNNING | retry exact completion transaction | no duplicate evidence; consumed |

## Deferred runtime work and stop conditions

Temporal workflow/activity, worker wiring, Outbox delivery, runtime launch reconciliation, and
artifact regeneration require separate owner approval. Stop if Policy cannot
evaluate the exact current step action, if existing Outbox delivery ownership remains ambiguous, or
if the synthetic Capability cannot regenerate an artifact without unsafe prose.

Stage C1 verifies the expanded, still-uncommitted `0006` from `0005`, downgrade, and re-upgrade;
forced Workspace RLS; lifecycle constraints; durable idempotency; completion atomicity; reservation
preservation; and safe evidence against isolated PostgreSQL. It starts no Temporal/API/worker,
launches no workflow, regenerates no artifact through runtime, and invokes no provider or
Capability.

## Stage C2 — bounded Temporal revision runtime

Stage C2 keeps migration `20260827_0006` frozen and adds no migration. The existing durable claim
remains the only launch authority. A revision-only worker coordinator revalidates the exact current
claim, Workspace, gate, decision, reserved cycle, execution request/run/step linkage, Registry
definitions, source artifact, target version, optimistic version, and persisted canonical workflow
ID in the atomic `CLAIMED → LAUNCH_PENDING` transaction before any Temporal contact.

The Temporal adapter starts only `rightjob.revision.regenerate_artifact` with the persisted ID
`revision:{workspace_id}:{quality_gate_id}:{quality_decision_id}:{cycle}` and a closed immutable
identifier projection. Exact claim identity is recorded in Temporal memo for describe-based
reconciliation. A matching existing workflow is adopted, definite absence permits one controlled
same-ID start, unknown existence remains reconciliation-required, and mismatch fails closed.
Definite initial rejection uses the C1.2 atomic claim/run/step terminalization; ambiguous launch
never fabricates `RUNNING`.

The deterministic workflow invokes one bounded synthetic activity with maximum two Temporal
attempts. The activity accepts only `REGENERATE_ARTIFACT`, preserves artifact identity, advances
exactly one version, and deterministically produces a changed SHA-256 with exact Workspace,
run/step, Capability/version, claim, and cycle provenance. It performs no provider, production
tool, filesystem, subprocess, or network work. The existing deterministic Validator is unchanged.
Only PASSED evidence reaches the existing C1 completion transaction, which completes the linked
run/step and returns the gate to `AWAITING_REVIEW` without changing the consumed reservation.
Validation failure remains failed and does not advance the gate. Cancellation request acknowledgement
is not terminal evidence: only an exact follow-up Temporal `CANCELED` status permits the persisted
workflow ID's `RUNNING → CANCELLED` boundary; ambiguous cancellation remains `RUNNING`.

Stage C2.1 corrects the still-uncommitted migration's reconciliation crash-window constraints. A
terminal claim may omit `running_at` only when `reconciliation_required_at` proves the lost-
acknowledgement recovery path and the closed reason is `workflow_failed`, `workflow_cancelled`,
`workflow_terminated`, or `workflow_timed_out`; validated recovered completion uses the same marker
without a failure reason. Runtime launch, inspect, result, and cancellation calls first reload the
exact durable claim and linkage. Temporal memo binds the complete safe action projection. The
activity independently verifies that projection, workflow ID, current durable lifecycle, execution
linkage, and gate through the Orchestration repository boundary before generating its bounded
synthetic JSON result. That generated JSON is present in Temporal result history; it contains only
closed synthetic identifiers, versions, and hashes, never external/user/provider prose or secrets.

An isolated real proof passed from durable claim through Temporal Server 1.25.0, delayed startup of
the actual RightJob worker composition, synthetic activity, Validator PASS, C1 completion, and
`AWAITING_REVIEW`. Concurrent callers produced one logical workflow. The existing real Temporal
restart/replay, bounded/exhausted retry, cancellation, idempotency, and multiprocess-turnover suite
also passed. No Reviewer or quality decision ran after completion, and no API, UI, provider,
production Capability, or Outbox relay was started.

**PHASE 2.20 STAGE C2 TEMPORAL REVISION RUNTIME IMPLEMENTED — ADVERSARIAL CHECKPOINT REVIEW REQUIRED**
