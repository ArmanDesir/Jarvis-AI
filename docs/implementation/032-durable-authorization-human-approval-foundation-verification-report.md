# Phase 2.12 Durable Authorization & Human Approval Foundation Verification Report

**Date:** 2026-08-13
**Scope:** Durable governance architecture and controlled verification checkpoints
**Status:** `PHASE 2.12 MIGRATION VERIFIED — BEHAVIORAL VERIFICATION PENDING`

## Architecture and ownership

Policy/Approval owns immutable Policy evidence, Approval lifecycle, exact-action binding, and
execution-authorization issuance. Identity remains canonical for Workspace, User, Membership,
status, role, and membership version. Planning remains proposal/validation authority only.
Orchestration verifies and consumes authorization but cannot issue it. Audit/Outbox accepts evidence
through published appenders in the aggregate-owning transaction. Temporal owns no authorization.

No module imports another module's infrastructure. All ORM mappings use the shared declarative Base
and are registered by `rightjob.database.register_sqlalchemy_mappings()`.

## Durable contracts and semantics

`AuthorizationEvidence` immutably binds the original five-minute `PolicyEvaluation` to the exact
Workspace, plan, step, Department, Capability, input, output contract, dependencies, effect, and
Policy set. `DENY` remains historical evidence only. It can create neither an ApprovalRequest nor an
ExecutionAuthorization.

`ApprovalRequest` supports `PENDING -> APPROVED|REJECTED|EXPIRED|CANCELLED|SUPERSEDED`, increments
its optimistic version once, and never outlives its Policy evidence. `ApprovalDecision` is append-only
and accepts only an active same-Workspace human USER with exact `owner` or `admin` membership.
`member`, inactive, missing, stale, or cross-Workspace facts fail closed. Identical duplicate decisions
are idempotent; conflicting duplicates fail.

`ALLOW` requires durable evidence without fabricated Approval. `REQUIRE_APPROVAL` requires an exact,
current APPROVED decision. Every plan step must be sufficient before one immutable, short-lived,
single-use `ExecutionAuthorization` is issued. Any DENY or unresolved approval blocks the entire plan.

## Action binding

Canonical JSON uses UTF-8, sorted keys, compact separators, finite JSON scalars, explicit schema
version, and normalized identifiers. SHA-256 produces a lowercase 64-character equality digest.
The digest supports deterministic mutation/replay detection only; it is not a signature, proof of
human identity, or protection from a trusted database owner.

## Orchestration enforcement

`ExecutionRequest` now requires an `ExecutionAuthorizationReference`. The plan compiler rejects
Workspace/plan mismatches. `create_execution()` invokes a published consumer inside the same Unit of
Work before request/run/step persistence. The consumer verifies the exact Workspace, plan digest,
workflow identity/version, ordered step IDs, and expiry. The proposed database uniqueness on
`execution_requests.execution_authorization_id` makes consumption single-use. No workflow was
launched during Phase 2.12 verification.

## Persistence and transaction boundaries

Five Policy/Approval-owned mappings represent the approved proposal:

- `authorization_evidence` — append-only;
- `approval_requests` — controlled mutable lifecycle with optimistic version;
- `approval_decisions` — append-only;
- `execution_authorizations` — append-only;
- `execution_authorization_steps` — append-only exact step bindings.

The proposed Orchestration alteration adds mandatory
`execution_requests.execution_authorization_id`. Repositories never commit. The Policy/Approval UoW
shares one SQLAlchemy Session with Audit and Outbox appenders. `GovernanceRecorder` commits aggregate
mutation, Audit evidence, and Outbox event together.

## Regenerated migration proposal and accepted migration

Proposed revision: `20260812_0004`; down revision: `20260811_0003`; owner: `policy`.
The proposal was later approved, created, and applied during separately authorized checkpoints.

### Read-only migration review refinement

The first read-only migration review correctly classified revision `20260812_0004` as not ready
for creation. The initial mappings permitted an ApprovalRequest to copy provenance not guaranteed
to belong to its referenced evidence, and permitted independently selected ApprovalRequest and
ApprovalDecision rows with an equal digest. They also contained one unused ApprovalRequest JSONB
column and one index duplicating a UNIQUE constraint.

The accepted source refinement corrected all eight findings without changing ownership or lifecycle
semantics:

1. AuthorizationEvidence now publishes the exact candidate key `(workspace_id, id,
   planning_request_id, plan_id, step_id, action_digest)` while retaining Workspace identity,
   Policy-evaluation idempotency, and the smaller step-binding candidate key required by the
   authorization-step FK.
2. ApprovalRequest binds all copied provenance and the digest to that exact evidence key.
3. AuthorizationStep binds ApprovalRequest by Workspace, request ID, evidence ID, and digest.
4. AuthorizationStep binds ApprovalDecision by Workspace, decision ID, request ID, and digest.
5. Every composite FK has an exact parent candidate key; no candidate key exists without an FK
   consumer.
6. The explicit authorization-step ordering index was removed because the sequence UNIQUE supplies
   the identical ordered index.
7. `approval_requests.reason_codes_json` and its fabricated repository value were removed; Policy
   reason codes remain solely on AuthorizationEvidence.
8. Mappings now include the accepted digest, algorithm/version, JSON type/size, nonblank identifier,
   actor, enum, snapshot-coherence, positive-version, timestamp, lifecycle, sequence, and paired
   approval-reference checks.

The final relational chain is:

```text
ExecutionAuthorizationStep
  -> exact AuthorizationEvidence(workspace, evidence, step, digest)
  -> exact ApprovalRequest(workspace, request, evidence, digest), when required
  -> exact ApprovalDecision(workspace, decision, request, digest), when required
```

Equal digests across distinct requests do not weaken identity because evidence, request, and decision
IDs participate in the applicable composite FKs.

All five new tables have UUID primary keys, non-null `workspace_id`, Workspace FK `ON DELETE
RESTRICT`, `UNIQUE(workspace_id,id)`, tenant-leading indexes, RLS, FORCE RLS, and a `FOR ALL`
Workspace policy using the established fail-closed setting expression.

Key constraints:

- evidence: unique Workspace/evaluation and composite exact evidence/step/digest binding; bounded
  object/array JSONB; SHA-256, enum, expiry, and schema-version checks;
- requests: unique Workspace/evidence and Workspace/idempotency key; composite evidence FK; bounded
  status; expiry, resolution, and positive-version checks;
- decisions: unique Workspace/request and Workspace/idempotency key; exact request/digest FK;
  USER-only approver, approved/rejected outcome, positive membership version;
- authorizations: unique Workspace/idempotency key; SHA-256/version and expiry checks;
- authorization steps: unique Workspace/authorization/step and sequence; exact evidence, request,
  and decision composite FKs; paired nullable approval references;
- execution requests: non-null authorization ID, exact composite FK, and unique Workspace/
  authorization ID.

Exact explicit indexes after refinement are:

- AuthorizationEvidence: Workspace/plan/step/evaluated time, Workspace/digest/expiry, and
  Workspace/correlation;
- ApprovalRequest: Workspace/status/expiry and Workspace/requester/requested time;
- ApprovalDecision: Workspace/approver membership/decision time;
- ExecutionAuthorization: Workspace/plan/expiry and Workspace/plan digest;
- ExecutionAuthorizationStep: none—the sequence UNIQUE supplies its required access path.

The migration must enable and force RLS on all five new tables and create one `FOR ALL` policy per
table using the established `NULLIF(current_setting('app.current_workspace_id', true), '')::uuid`
expression identically in `USING` and `WITH CHECK`. No existing RLS policy changes.

Upgrade order is evidence, requests, decisions, authorizations, authorization steps, then the
mandatory ExecutionRequest authorization column/FK/UNIQUE. Downgrade removes the ExecutionRequest
alteration first, then drops authorization steps, authorizations, decisions, requests, and evidence
in dependency-safe order.

All FKs use `ON DELETE RESTRICT`. Identity User/Membership IDs are intentionally snapshotted without
FKs so historical evidence survives later Identity lifecycle changes. Downgrade removes the
ExecutionRequest enforcement link first, then drops authorization steps, authorizations, decisions,
requests, and evidence.

## Files

Created:

- `packages/core/src/rightjob/contracts/authorization.py`
- `packages/core/src/rightjob/contracts/approval.py`
- `packages/core/src/rightjob/policy/authorization.py`
- `packages/core/src/rightjob/policy/application.py`
- `packages/core/src/rightjob/policy/repositories.py`
- `packages/core/src/rightjob/policy/infrastructure/models.py`
- `packages/core/src/rightjob/policy/infrastructure/repositories.py`
- `packages/core/src/rightjob/policy/infrastructure/unit_of_work.py`
- `tests/unit/test_durable_authorization.py`
- this report

Modified:

- published contract and Policy exports;
- `MembershipFacts` membership-version contract;
- database mapping composition root;
- Orchestration request, compiler, service, UoW, repository, and ORM mapping;
- existing Phase 2.7/2.10 source tests for mandatory authorization;
- phase-status documentation.

## Verification

- Focused Phase 2.11/2.12 and affected Orchestration/Planning tests: PASS — 50 passed.
- Full pytest: PASS — 149 passed, 31 runtime-gated skips.
- Ruff format/lint: PASS.
- strict mypy: PASS.
- architecture and phase-scope checks: PASS.
- migration safety: PASS; migration chain unchanged.
- secret hygiene and Python compilation: PASS;
- UV lock verification: PASS — 51 packages, lock unchanged (project-local UV cache used because
  the user cache is outside the workspace sandbox).

Post-review focused structural tests additionally prove the exact evidence/request/decision FK
chain, Workspace-leading references, candidate-key coverage, removal of the redundant index and
unused column, bounded checks, and ApprovalRequest's narrow mutable repository update.

PostgreSQL, Temporal, API, and worker remained stopped. No database mutation, provider call,
external effect, migration, or Temporal launch occurred.

## Risks and deferred work

- PostgreSQL constraints, RLS, atomicity, concurrency, and cleanup require separate migration and
  runtime approval.
- The five-minute synthetic approval window is deliberately unsuitable for general production use.
- Production approval roles, permissions, dual approval, thresholds, reusable grants, revocation,
  API/UI, real effects, and commit-time provider Policy remain deferred.
- ExecutionPlan persistence remains deferred; authorization stores the exact bounded action snapshot.
- PostgreSQL owner remains a trusted privileged boundary.

## PostgreSQL migration verification checkpoint — 2026-08-13

The retained isolated PostgreSQL 17 cluster was started on port `55416` using only the approved
project Unix socket. The read-only preflight confirmed revision `20260811_0003`; zero rows in
`workspaces`, `users`, `memberships`, `audit_entries`, `outbox_events`, `execution_requests`,
`execution_runs`, and `execution_steps`; no Phase 2.12 tables or ExecutionRequest authorization
column; no Phase 2.12 verifier role; only the accepted `plpgsql` extension; and the unchanged Phase
2.7 relations, constraints, indexes, forced RLS, and Workspace policies. In particular,
`execution_requests = 0`, satisfying the mandatory no-backfill precondition.

Alembic applied exactly `20260812_0004` over the approved Unix-socket connection. Post-migration
inventory confirmed revision `20260812_0004`, zero rows in all thirteen application tables, exactly
the five approved new tables, and `execution_requests.execution_authorization_id UUID NOT NULL`
without a default. The installed columns, primary keys, UNIQUE constraints, CHECK constraints,
composite foreign keys, `ON DELETE RESTRICT` actions, and explicit indexes match the accepted
SQLAlchemy metadata and migration proposal. The exact Evidence → ApprovalRequest →
ApprovalDecision and ExecutionAuthorizationStep bindings are installed and validated. Identical
digests cannot alias rows because the relevant evidence, request, and decision IDs remain in the
composite keys.

All five new tables have RLS enabled and forced, with exactly one `FOR ALL` Workspace-isolation
policy using the established fail-closed `app.current_workspace_id` expression identically in
`USING` and `WITH CHECK`. No redundant authorization-step or ExecutionRequest authorization index
exists. The migration introduced no role, grant, extension, default, backfill, trigger, provider or
Temporal persistence, and did not change Identity, Audit/Outbox, `execution_runs`, `execution_steps`,
or any earlier constraint, index, or policy. Static review confirms the downgrade removes the
ExecutionRequest authorization link first and then the five tables in dependency-safe reverse order.

No fixtures, verifier role, grants, behavioral tests, API, worker, or Temporal process were created
or started. PostgreSQL intentionally remains running at revision `20260812_0004` with all
application tables empty for the separately approved behavioral checkpoint.

Checkpoint verdict: `PHASE 2.12 MIGRATION VERIFIED`. This is not a claim that Phase 2.12 behavioral
verification has passed.

## PostgreSQL behavioral harness checkpoint — 2026-08-13

The owner approved the fixed Phase 2.12 PostgreSQL fixture inventory and creation of exactly
`tests/integration/test_authorization_approval_transactions.py`. The harness encodes only those
approved IDs, requires both `RIGHTJOB_DATABASE_URL` and `RIGHTJOB_PHASE212_RLS_DATABASE_URL`, and
has no database fallback. With both variables absent, collection/source execution passed with all
14 cases skipped as designed; the integration module was not executed.

The module encodes the temporary `rightjob_phase212_rls_verifier` contract with LOGIN,
NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT, and NOBYPASSRLS. Its grants are limited to
database CONNECT, schema USAGE, SELECT/INSERT on the approved governance, execution, Audit, and
Outbox tables, plus column-level UPDATE of only `approval_requests.status`, `resolved_at`, and
`version`. Identity fixtures remain owner-controlled. No DELETE, TRUNCATE, CREATE, ownership,
BYPASSRLS, or broad UPDATE privilege is granted.

The harness covers pristine revision/schema checks, exact owner-controlled setup and child-first
cleanup, atomic governance/Audit/Outbox commit and rollback, forced-RLS isolation and missing-context
denial, append-only privilege denial, narrow ApprovalRequest mutation, exact equal-digest composite
binding, optimistic terminal-transition races, synthetic OWNER/ADMIN/MEMBER authority, complete
multi-step authorization, DENY dominance, authorization single use, and the one-request/one-run
regression. Finalization deletes only approved IDs, revokes only exact grants, drops only the verifier
role, and re-verifies the pristine revision and schema counts.

Static gates passed: Ruff format/lint, strict mypy over 108 source files, Python compilation,
architecture boundaries, phase scope, migration safety, secret hygiene, and safe skipped pytest
collection. PostgreSQL received no mutation during this checkpoint and remains running at
`20260812_0004`; Temporal, API, and worker remain stopped.

Coverage reconciliation exposed one production behavior gap before runtime execution: repository
and `GovernanceRecorder` ports only provide `add()` operations for AuthorizationEvidence,
ApprovalRequest, ApprovalDecision, and ExecutionAuthorization. Although PostgreSQL uniqueness safely
rejects duplicate identities/keys, there is no lookup-and-compare operation that can return the
existing result for the approved “same idempotency key + same semantic content” behavior. Therefore
the harness cannot honestly prove deterministic reuse for those four aggregates without a separately
approved production correction. Conflicting duplicates remain fail-closed through uniqueness. No
production source was changed under this harness-only authorization.

Status remains `PHASE 2.12 MIGRATION VERIFIED — BEHAVIORAL VERIFICATION PENDING`.

## Idempotency correction checkpoint — 2026-08-13

The behavioral-harness review finding was accepted as a production application/repository
idempotency gap, not a database defect. The installed UNIQUE constraints were retained unchanged.
The root cause was that the four governance repositories exposed write-only `add()` operations and
`GovernanceRecorder` always emitted Audit/Outbox records before commit. Consequently, an identical
retry reached PostgreSQL as a second insert instead of resolving to the already accepted canonical
aggregate.

The repository ports and SQLAlchemy implementations now provide only the bounded Workspace-scoped
lookups required by the accepted natural identities:

- AuthorizationEvidence by `(workspace_id, policy_evaluation_id)`;
- ApprovalRequest by evidence and by `(workspace_id, idempotency_key)`;
- ApprovalDecision by request and by `(workspace_id, idempotency_key)`;
- ExecutionAuthorization by `(workspace_id, idempotency_key)`, including its ordered step bindings.

`GovernanceRecorder` now performs lookup, explicit immutable semantic comparison, canonical reuse,
or normalized `IdempotencyConflictError` before mutation. Aggregate record IDs and authorization-step
record IDs are incidental for identical retries; all authorization-bearing provenance, exact Policy
facts, subject and membership snapshot, action snapshot/digest, expiry, correlation/causation,
request semantics, decision outcome and authority facts, workflow binding, and ordered authorization
step manifest remain comparison-significant. ApprovalRequest comparison deliberately ignores only
the mutable lifecycle fields on the existing record, so replay after approval/rejection returns the
current canonical state without resetting status or version.

First creation still writes the governance aggregate, Audit evidence, and Outbox event in one Unit
of Work commit. Canonical replay returns before any new Audit/Outbox append; conflict returns before
success evidence. For a concurrent insert race, only the exact accepted UNIQUE constraint names are
recoverable: the failed Unit of Work rolls back, a fresh Unit of Work re-reads the winner, and the
same semantic comparison determines reuse or conflict. An unrelated `IntegrityError` propagates
unchanged.

Unit coverage proves reuse and conflict for all four aggregates, ApprovalRequest lifecycle replay,
APPROVED/REJECTED conflict, exact ordered authorization-step comparison, no duplicate Audit/Outbox
writes, exact race recovery, and rejection of unrelated integrity failures. The gated PostgreSQL
harness now represents the same four-aggregate application paths using the approved fixed IDs; it
was collected but not executed.

Correction checkpoint gates passed: focused Phase 2.11/2.12 tests `29 passed`; PostgreSQL harness
collection `15 skipped` without its required URLs; full pytest `153 passed, 46 skipped`; Ruff format
and lint; strict mypy over 108 source files; architecture boundaries; phase scope; migration safety;
secret hygiene; Python compilation; UV lock consistency; and `git diff --check`.

No migration or schema object changed. PostgreSQL received no mutation during this checkpoint and
remains running at the previously verified revision `20260812_0004`. Temporal, API, and worker
remain stopped. The status remains `PHASE 2.12 MIGRATION VERIFIED — BEHAVIORAL VERIFICATION
PENDING` until the separately approved PostgreSQL behavioral run completes.

## PostgreSQL behavioral execution — fail-fast checkpoint — 2026-08-13

The final read-only preflight passed at revision `20260812_0004`: all thirteen application tables
were empty; the approved fixture IDs and temporary verifier role were absent; and the installed
inventory remained 14 relations, 129 constraints, 62 indexes, 11 forced-RLS tables, and 11 `FOR
ALL` Workspace policies.

The approved module ran with `-x -vv`. Thirteen tests passed, covering atomic governance/Audit/
Outbox commit and rollback, Workspace RLS and missing-context denial, append-only and narrow-update
privileges, equal-digest relational constraints, optimistic terminal races, all six synthetic
approver-authority cases, four-aggregate application idempotency, and multi-step authorization with
DENY dominance.

The run then stopped at
`test_execution_authorization_single_use_and_one_request_one_run`. Its raw textual SQL INSERT passed
the Python value `{}` directly as `execution_requests.input_json`; psycopg raised
`ProgrammingError: cannot adapt type 'dict'` before inserting the ExecutionRequest. This is
classified as a behavioral-harness JSONB parameter adaptation defect, not a production-source or
migration defect. Per fail-closed instructions, the test was not changed or retried, and the
remaining single-use, one-request/one-run, and final schema/grant test did not complete.

The module finalizer completed exact cleanup. A separate read-only residue check confirmed all
thirteen application tables returned to zero rows, the verifier role and grants are absent,
revision remains `20260812_0004`, and the inventory remains 14 relations, 129 constraints, 62
indexes, 11 forced-RLS tables, and 11 policies. PostgreSQL remains running for diagnosis. No source
quality regression or shutdown was performed after the failed runtime checkpoint.

Status remains `PHASE 2.12 MIGRATION VERIFIED — BEHAVIORAL VERIFICATION PENDING`.

### Behavioral harness JSONB correction — 2026-08-14

The owner accepted the failure as a test-harness defect. Inspection confirmed the production
`ExecutionRequestRecord.input_json` mapping already uses PostgreSQL `JSONB`, while the failing raw
`text()` statement discarded that bind type and passed `{}` directly to psycopg. The two equivalent
ExecutionRequest inserts in the one affected test now use `insert(ExecutionRequestRecord)`, reusing
the production mapping's JSONB type. No production source, mapping, migration, schema, constraint,
RLS policy, or privilege changed.

### Successful PostgreSQL behavioral verification — 2026-08-14

The repeated pristine preflight confirmed revision `20260812_0004`, zero rows across all thirteen
application tables, no approved fixture residue, no verifier role or grants, and the unchanged
inventory of 14 relations, 129 constraints, 62 indexes, 11 forced-RLS tables, and 11 Workspace
policies.

The complete approved module then passed: `15 passed`. It proved atomic governance/Audit/Outbox
commit and rollback, Workspace isolation and missing-context denial, append-only privileges and
narrow ApprovalRequest updates, exact equal-digest relational binding, optimistic lifecycle races,
synthetic OWNER/ADMIN authority and MEMBER/inactive/cross-Workspace denial, four-aggregate
idempotent canonical reuse and conflicting-replay rejection, complete multi-step authorization and
DENY dominance, ExecutionAuthorization single use, and the one-request/one-run invariant. Identical
governance retries produced no duplicate Audit/Outbox success records.

The module finalizer removed only approved fixtures, revoked only approved grants, and dropped only
`rightjob_phase212_rls_verifier`. Post-run verification again found zero rows in all thirteen tables,
no role or grant residue, revision `20260812_0004`, and the unchanged schema inventory above.
PostgreSQL then shut down cleanly; port `55416`, its Unix socket, the cluster process, and test/tool
processes were absent. Temporal, API, and worker remained stopped.

Final source regression passed: full pytest `153 passed, 46 skipped`; Ruff format/lint; strict mypy
over 108 source files; architecture boundaries; phase scope; migration safety; secret hygiene;
Python compilation; UV lock consistency; and `git diff --check`.

## Verdict

`PHASE 2.12 DURABLE AUTHORIZATION & HUMAN APPROVAL FOUNDATION PASSED`
