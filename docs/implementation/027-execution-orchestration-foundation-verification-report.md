# Phase 2.7 Execution & Orchestration Foundation Verification Report

**Date:** 2026-08-11
**Scope:** Source-only execution and orchestration foundation
**Status:** `PHASE 2.7 SOURCE-ONLY IMPLEMENTATION PASSED — MIGRATION AND RUNTIME GATED`

## Objective and boundaries

Phase 2.7 represents an already-validated synthetic execution plan, persists its proposed
canonical request/run/step records, compiles it deterministically, and launches it through the
provider-neutral `DurableWorkflowEngine`. PostgreSQL application state is authoritative; Temporal
state is infrastructure evidence only.

No Executive AI, Planner, LLM, Department, business Capability, Policy, approval, Memory, provider,
external effect, public API, frontend, workflow editor, dynamic workflow loading, Kafka, Redis, or
new dependency was added. No migration was created. PostgreSQL and Temporal were not started.

## Architecture decisions

- Orchestration owns execution semantics, definitions, compilation, run/step state, retry meaning,
  cancellation meaning, reconciliation, evidence, and event meaning.
- `workflow_definition_id` is the immutable internal identity. Selection remains exact
  `workflow_type + workflow_version`.
- The registry is immutable and code-owned. It contains only `synthetic.sequence@1.0.0` and
  `synthetic.signal@1.0.0`.
- `InitiatorType` contains only `USER` and `SYSTEM`. Persistence uses `varchar`, not a PostgreSQL
  enum or restrictive check, so future values do not require schema redesign.
- Ordered steps are sufficient for this phase; no general DAG engine was introduced.
- No `parent_run_id` exists. Parent/child execution remains a future orchestration capability.
- Canonical cancellation intent uses `cancellation_requested_at`; status remains canonical and is
  not changed to cancelled until engine cancellation is reconciled.
- Temporal identifiers are deterministically derived from Workspace, handler type, and canonical
  run ID. No Temporal identifier is canonical application data.

## Files changed

Core Orchestration:

- `packages/core/src/rightjob/orchestration/domain/models.py`
- `packages/core/src/rightjob/orchestration/domain/__init__.py`
- `packages/core/src/rightjob/orchestration/application/registry.py`
- `packages/core/src/rightjob/orchestration/application/compiler.py`
- `packages/core/src/rightjob/orchestration/application/repositories.py`
- `packages/core/src/rightjob/orchestration/application/service.py`
- `packages/core/src/rightjob/orchestration/application/__init__.py`
- `packages/core/src/rightjob/orchestration/infrastructure/models.py`
- `packages/core/src/rightjob/orchestration/infrastructure/repositories.py`
- `packages/core/src/rightjob/orchestration/infrastructure/unit_of_work.py`
- `packages/core/src/rightjob/orchestration/infrastructure/__init__.py`
- `packages/core/src/rightjob/orchestration/engine.py`

Worker infrastructure:

- `services/worker/src/rightjob_worker/execution_activities.py`
- `services/worker/src/rightjob_worker/execution_workflows.py`
- `services/worker/src/rightjob_worker/temporal_adapter.py`
- `services/worker/src/rightjob_worker/temporal_runtime.py`

Verification and documentation:

- `tests/unit/test_execution_orchestration.py`
- `tests/unit/test_workflow_engine.py`
- `docs/implementation/phase-status.md`
- this report

## State models

Run states are `queued`, `running`, `waiting`, `succeeded`, `failed`, `cancelled`, and
`reconciliation_required`.

Allowed run transitions:

```text
queued -> running | cancelled | reconciliation_required
running -> waiting | succeeded | failed | cancelled | reconciliation_required
waiting -> running | cancelled | reconciliation_required
reconciliation_required -> running | failed | cancelled
```

Step states use `pending` instead of `queued` and otherwise the same execution states.

```text
pending -> running | cancelled
running -> waiting | succeeded | failed | cancelled | reconciliation_required
waiting -> running | cancelled | reconciliation_required
reconciliation_required -> running | failed | cancelled
```

Terminal states have no outgoing transitions. Every undeclared transition raises
`InvalidExecutionTransition`. Optimistic version increments are part of every mutation.

Failure classifications are `validation`, `business`, `infrastructure_transient`,
`infrastructure_exhausted`, `cancelled`, `unknown_outcome`, and `internal_defect`. Unknown outcome
forces reconciliation; it is not treated as ordinary failure or blindly retried.

## Registry and compiler

Each definition has immutable ID, type, semantic version, expected input fields/types, exact ordered
step definitions, handler reference, and enabled/disabled state. Duplicate IDs or type/version pairs
are rejected. Disabled or absent versions fail closed.

The compiler validates definition identity, exact version, exact step sequence/types/retry limits,
and the expected input boundary. It emits an engine-neutral `CompiledExecution` and performs no
persistence, authorization, AI choice, Department/Capability selection, or Temporal operation.

Execution inputs are JSON-only, limited to 64 KiB, and reject nested secret-bearing keys. No
arbitrary executable code or large evidence payload is accepted.

## Transaction and Audit/Outbox boundaries

`ExecutionUnitOfWork` owns request, run, and step repositories and structurally receives Phase 2.6
Audit and Outbox appenders built over the same SQLAlchemy session. One application transition does:

```text
canonical aggregate mutation + AuditEvidence + IntegrationEvent = one commit
```

Implemented source event families include run creation/start/wait/success/failure/cancellation,
cancellation request, step transitions, and reconciliation required. Envelopes preserve Workspace,
actual actor, correlation, causation, safe state, resource identity, and producer. Raw request and
step output payloads are not copied into events.

The source launch sequence commits a queued canonical record before calling Temporal. An ambiguous
launch or cancellation outcome transitions the canonical run to `reconciliation_required` with
Audit/Outbox evidence. A deterministic engine ID makes later comparison safe, but Temporal never
chooses the final application state.

## Tenancy

Every proposed canonical table has non-null `workspace_id`, tenant-leading indexes, explicit
repository scope checks, and exact Workspace predicates. Cross-Workspace lookups return not found
without disclosure. Proposed composite foreign keys prevent a request, run, or step from crossing a
Workspace boundary. Missing Workspace context is expected to fail closed under forced RLS.

## Cancellation, retry, and reconciliation

- Cancellation intent is committed with Audit/Outbox evidence before the Temporal cancel call.
- A repeated request after intent/final cancellation is idempotent.
- Cross-Workspace cancellation fails before engine access.
- A queued, never-launched run cancels canonically without pretending Temporal received work.
- Temporal activity retries remain delivery mechanics. Canonical step attempt count and failure
  classification remain Rightjob values.
- Unknown engine outcomes require explicit reconciliation. `reconcile_run` operates only on a run
  already in `reconciliation_required` and uses the same state machine and transaction evidence.

## Proposed PostgreSQL schema

**No migration has been created.** Proposed revision is `20260811_0003`, owned by
`orchestration`, with `down_revision = 20260811_0002`.

### `execution_requests`

Columns: `id uuid`, `workspace_id uuid`, `correlation_id uuid`, `causation_id uuid?`,
`actor_type varchar(20)`, `actor_id varchar(255)`, `initiator_type varchar(20)`,
`workflow_definition_id uuid`, `workflow_type varchar(255)`, `workflow_version varchar(50)`,
`input_json jsonb`, `created_at timestamptz`; all non-null except causation.

Constraints:

- `pk_execution_requests`: primary key `(id)`.
- `uq_execution_requests_workspace_id`: unique `(workspace_id,id)` for tenant-aware references.
- `fk_execution_requests_workspace`: `workspace_id -> workspaces.id ON DELETE RESTRICT`.
- `ck_execution_requests_actor_type`: actor type is `user` or `system` only.
- `ck_execution_requests_actor_id_nonblank`.
- `ck_execution_requests_workflow_type_nonblank`.
- `ck_execution_requests_workflow_version_nonblank`.
- `ck_execution_requests_input_object`: `jsonb_typeof(input_json) = 'object'`.
- `ck_execution_requests_input_size`: UTF-8 JSON text is at most 65,536 bytes.

`initiator_type` remains application-validated and stored as extensible varchar. No PostgreSQL enum
or restrictive initiator check is introduced.

Indexes: `(workspace_id,created_at)` and `(workspace_id,correlation_id)`.

### `execution_runs`

Columns: `id uuid`, `workspace_id uuid`, `execution_request_id uuid`,
`workflow_definition_id uuid`, `workflow_type varchar(255)`, `workflow_version varchar(50)`,
`status varchar(40)`, `correlation_id uuid`, `causation_id uuid?`, `actor_type varchar(20)`,
`actor_id varchar(255)`, `initiator_type varchar(20)`, `created_at timestamptz`,
`started_at timestamptz?`, `completed_at timestamptz?`, `cancellation_requested_at timestamptz?`,
`cancelled_at timestamptz?`, `reconciliation_state varchar(40)`, `version integer`.

Constraints:

- `pk_execution_runs`: primary key `(id)`.
- `uq_execution_runs_workspace_id`: unique `(workspace_id,id)`.
- `uq_execution_runs_workspace_request`: unique `(workspace_id,execution_request_id)`, enforcing
  one canonical run per request.
- `fk_execution_runs_workspace`: `workspace_id -> workspaces.id ON DELETE RESTRICT`.
- `fk_execution_runs_workspace_request`: tenant-aware request FK `ON DELETE RESTRICT`.
- `ck_execution_runs_actor_type`: actor type is `user` or `system` only.
- nonblank actor ID, workflow type, and workflow version checks.
- canonical status check.
- reconciliation state check limited to `not_required`, `required`, and `resolved`.
- `ck_execution_runs_version`: `version > 0`.

Indexes: `(workspace_id,status,created_at)` and `(workspace_id,correlation_id)`.

### `execution_steps`

Columns: `id uuid`, `run_id uuid`, `workspace_id uuid`, `step_type varchar(255)`, `sequence integer`,
`status varchar(40)`, `attempt_count integer`, `max_attempts integer`, `input_ref varchar(500)`,
`output_evidence_ref varchar(500)?`, `started_at timestamptz?`, `completed_at timestamptz?`,
`failure_classification varchar(40)?`, `version integer`.

Constraints:

- `pk_execution_steps`: primary key `(id)`.
- `uq_execution_steps_workspace_id`: unique `(workspace_id,id)`.
- `uq_execution_steps_workspace_run_sequence`: unique `(workspace_id,run_id,sequence)`.
- `fk_execution_steps_workspace`: `workspace_id -> workspaces.id ON DELETE RESTRICT`.
- `fk_execution_steps_workspace_run`: tenant-aware run FK `ON DELETE RESTRICT`.
- canonical status and failure-classification vocabulary checks.
- `ck_execution_steps_sequence`: `sequence >= 0`.
- bounded attempt check: `0 <= attempt_count <= max_attempts` and `max_attempts > 0`.
- `ck_execution_steps_status_failure`: failed steps require a failure classification,
  reconciliation-required steps require `unknown_outcome`, and other states prohibit a failure
  classification.
- nonblank step type and input reference checks; nullable output evidence must be nonblank when
  present.
- `ck_execution_steps_version`: `version > 0`.

Index: `(workspace_id,status)`. No separate `(workspace_id,run_id,sequence)` index is created
because its UNIQUE constraint already supplies that tenant-leading B-tree index.

All three tables require enabled and forced RLS with one table-specific `ALL` policy using
transaction-local `app.current_workspace_id`. The migration must also add the declared Workspace
foreign keys and must not alter Identity or Audit/Outbox objects.

Exact RLS policies:

```text
execution_requests_workspace_isolation
execution_runs_workspace_isolation
execution_steps_workspace_isolation
```

Each policy is `FOR ALL`, uses and checks
`workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid`, and requires
both enabled and forced RLS.

All columns have no server default. Application code explicitly supplies IDs, canonical statuses,
timestamps, counters, reconciliation state, and optimistic version.

Downgrade drops each Phase 2.7 RLS policy and then drops tables in child-first order:
`execution_steps`, `execution_runs`, `execution_requests`. It does not alter Identity or
Audit/Outbox objects. Migration creation and validation require a separate owner decision.

## Source-only tests and gates

Final source-only results:

| Gate | Result |
|---|---|
| Focused Phase 2.7 and engine tests | PASS — 19 passed |
| Full pytest with PostgreSQL and Temporal stopped | PASS — 97 passed, 24 gated skips |
| Ruff format | PASS |
| Ruff lint | PASS |
| strict mypy | PASS — 85 source files |
| Architecture checks | PASS |
| Phase scope | PASS |
| Migration safety | PASS — no new revision |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV locked resolution | PASS — lock unchanged |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Proposed PostgreSQL verification

After separate migration approval: prove exact preflight revision/inventory, apply only
`20260811_0003`, test canonical request/run/step persistence, one-commit aggregate + audit + outbox,
rollback, idempotency, optimistic concurrency, forced RLS, missing/cross-Workspace denial, exact
fixture cleanup, unchanged earlier schema, and clean shutdown.

## Proposed Temporal verification

After separate runtime approval: prove create-before-launch durability, synthetic step delivery,
canonical step transitions, worker restart/resume, signal wait, bounded retry, cancellation and
duplicate cancellation, ambiguous outcome reconciliation, correlation/causation, Workspace denial
before Temporal access, PostgreSQL authority during disagreement, exact cleanup, and clean shutdown.

## Risks and remaining blockers

- Migration `20260811_0003` is not authorized or created; database behavior is unproven.
- Temporal runtime verification is not authorized; source registration is not runtime evidence.
- PostgreSQL/Temporal cannot share one transaction. Queued-run reconciliation closes the launch
  gap, but crash-window behavior remains to be proven.
- The outbox relay remains deferred; Phase 2.7 records durable events but does not claim delivery.
- Parent/child execution, dynamic definitions, real Capabilities, Policy/approval, compensation,
  scheduling, and external effects remain future work.
- Read-only preflight found retained Phase 2.3/2.4/2.6 temporary reports/pycache and two old
  Phase 2.5 `effects.sqlite3` ledgers. They were not deleted because cleanup was not authorized.

## Stop point

Source-only implementation and gates are complete. Work stops before migration creation,
PostgreSQL verification, or Temporal runtime verification, as required.

## PostgreSQL migration and behavioral verification update — 2026-08-12

Migration revision `20260811_0003` was separately approved, applied over the approved Unix-domain
socket, and accepted after complete post-migration inventory. PostgreSQL remained canonical; the
migration introduced only `execution_requests`, `execution_runs`, and `execution_steps`, with the
approved constraints, indexes, composite foreign keys, forced RLS, and Workspace policies. No
Temporal persistence or Audit/Outbox ownership change was introduced.

The approved test-only harness was added at
`tests/integration/test_execution_orchestration_transactions.py`. Ruff and pytest collection passed:
seven tests were collected, covering the approved atomicity, rollback, uniqueness, optimistic
concurrency, cancellation/reconciliation, RLS, append-only Audit, Outbox, and idempotency proofs.

The PostgreSQL behavioral run stopped during module fixture setup, before the first behavioral test.
The exact failing operation was the first ORM `Session.flush()` of an `ExecutionRequestRecord`.
SQLAlchemy raised `NoReferencedTableError`: the orchestration mapping declares
`ForeignKey("workspaces.id")`, but the orchestration `Base.metadata` does not contain the Identity
module's `workspaces` table. Consequently SQLAlchemy cannot sort the mapped tables for persistence.
The database foreign key itself is present and correct; this is a production ORM metadata/composition
defect, not a migration defect.

No production source or migration was changed. The setup transaction rolled back atomically,
including temporary role creation, grants, Identity fixtures, and attempted Phase 2.7 fixtures.
Read-only recovery evidence confirmed:

- revision remained `20260811_0003`;
- all eight application tables contained zero rows;
- all approved fixture IDs were absent;
- `rightjob_phase27_rls_verifier` was absent.

The isolated PostgreSQL cluster was then shut down cleanly. Port `55416` had no listener, its Unix
socket was absent, and no `postgres`, `pytest`, `psql`, or `pg_ctl` process remained.

Behavioral verification is therefore **BLOCKED / NOT PASSED**. The smallest required production
correction is to make the Identity `workspaces` table resolvable from the orchestration mappings
without changing database schema or module ownership. That correction requires a separate owner
decision before production source may be modified or the behavioral module may be rerun. Phase 2.8
has not begun, and Temporal was not started.

## ORM metadata correction and completed behavioral verification — 2026-08-12

Owner approval authorized the minimal production correction. Identity, Audit, and Orchestration had
each declared an independent `DeclarativeBase` and `MetaData`; consequently Orchestration's string
foreign key could not resolve the Identity-owned `workspaces` table during ORM flush.

The correction adds one shared SQLAlchemy `Base` and naming convention in
`rightjob.shared.sqlalchemy`. Each bounded module continues to own its records and repositories while
registering mappings on the shared metadata. Orchestration references the actual Identity-owned
`WorkspaceRecord.id`, making the dependency explicit and acyclic. Repository behavior, Unit of Work
boundaries, database schema, migration `20260811_0003`, Temporal, and Audit/Outbox ownership were not
changed.

Verification results:

- Ruff format/lint: PASS.
- strict mypy: PASS — 66 core source files.
- focused Phase 2.7 source/mapping tests: PASS — 22 passed.
- approved PostgreSQL behavioral module: PASS — 7 passed.
- atomic request/run/steps/Audit/Outbox creation and rollback: PASS.
- one-request/one-run and step-sequence uniqueness: PASS.
- run and step optimistic concurrency: PASS.
- canonical idempotent cancellation and reconciliation-required behavior: PASS.
- forced Workspace RLS, missing context, and cross-Workspace denial: PASS.
- append-only Audit and durable/idempotent Outbox behavior: PASS.

Final cleanup inventory passed: revision `20260811_0003`; all eight application tables zero rows;
all approved fixture IDs absent; verifier role and grants absent; 63 constraints and 30 indexes
unchanged; all six policies present; all tenant tables retained enabled and forced RLS. The three
Phase 2.7 policies remained exactly
`execution_requests_workspace_isolation`, `execution_runs_workspace_isolation`, and
`execution_steps_workspace_isolation`.

Phase 2.7 PostgreSQL behavioral verification is **PASSED**. Temporal runtime verification remains a
separately authorized activity. Phase 2.8 has not begun.
