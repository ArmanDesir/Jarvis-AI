# Phase 2.6 Audit Evidence & Transactional Outbox Foundation Verification Report

**Date:** 2026-08-11  
**Scope:** Source implementation, approved migration, and PostgreSQL runtime proof  
**Status:** `PHASE 2.6 AUDIT EVIDENCE AND TRANSACTIONAL OUTBOX FOUNDATION PASSED`

## Summary

Phase 2.6 establishes typed, provider-neutral audit evidence and versioned integration-event
contracts, append-only audit repository semantics, a transactional outbox repository, explicit
Audit/Outbox Unit of Work lifecycle, Workspace-scoped SQLAlchemy behavior, correlation and
causation propagation, and a consumer-owned idempotency boundary.

One approved migration was created and applied at revision `20260811_0002`. Its schema, RLS, and
corrected PostgreSQL behavior suite passed. The first behavior attempt stopped during fixture setup
because an untyped raw SQL statement could not adapt Python dictionaries to JSONB. That setup
transaction rolled back in full. Owner review classified it as a verification-harness defect, and
the approved correction reused the existing typed SQLAlchemy mappings without changing production
behavior. No dependency, API, Identity, repository-owner, Temporal, business-domain, frontend,
provider, broker, or workflow behavior changed. Phase 2.7 has not begun.

## Architecture and ownership

- Producers own truthful event names, versions, payload meaning, compatibility, and evidence for
  their operations.
- Published contracts own the cross-module envelope, actor classification, sensitivity, IDs,
  correlation, causation, versions, and safe JSON boundary.
- Audit/Observability owns audit acceptance and append-only persistence plus the outbox persistence
  implementation.
- Aggregate-owning Units of Work retain authority over aggregate transactions. They can construct
  `SqlAlchemyOutboxRepository` with their existing SQLAlchemy session so the aggregate change and
  event commit once in the same PostgreSQL transaction.
- Consumers own their durable receipt storage and satisfy `EventDeduplicator`, which atomically
  claims `(workspace_id, consumer, event_id)`. No speculative global inbox table was introduced.
- Audit records remain evidence and cannot substitute for canonical aggregates.
- PostgreSQL remains the initial outbox. No Kafka, Redis, external broker, or production Temporal
  workflow was introduced.

## Contracts

`AuditEvidence` records a stable ID, Workspace, actual actor, action, resource, outcome,
correlation/causation, timestamp, sensitivity, optional policy/approval/evidence references, and
safe before/after summaries. It is a frozen typed input. Secret-bearing JSON keys are rejected.

`IntegrationEvent` is a frozen, versioned envelope containing event ID/type/version, schema
version, timestamp, Workspace, actual actor, correlation/causation, producer, sensitivity, typed
JSON payload, and idempotency key. Producers supply semantics; the Audit module only validates and
persists the envelope.

`AuditEvidenceRepository` exposes only `append`; it has no update or delete contract.
`OutboxRepository` exposes add, bounded pending retrieval, and Workspace-scoped publication
marking. `AuditUnitOfWork` retains explicit commit, rollback, and close operations.

## Persistence design and migration

The SQLAlchemy mappings describe two tenant tables:

1. `audit_entries` — append-only audit evidence, indexed by Workspace/time and correlation.
2. `outbox_events` — versioned event envelope, unique Workspace/idempotency key, pending-event and
   correlation indexes, publication timestamp, and bounded delivery-attempt metadata.

Both mappings require `workspace_id`. Every repository operation checks explicit scope before
database use and establishes transaction-local `app.current_workspace_id`. Migration
`20260811_0002` adds physical Workspace foreign keys, enables and forces RLS, and defines
fail-closed Workspace policies. Catalog inspection verified those database objects.

Append-only enforcement in this foundation consists of an append-only repository interface and no
application-role UPDATE/DELETE grants. The database owner remains capable of exact fixture cleanup
and governed maintenance. Retention/partitioning remains volume- and policy-driven.

## Transaction and idempotency evidence

Source tests prove:

- explicit commit occurs exactly once and closes the session;
- omitted commit and exceptions roll back and close;
- aggregate work and an outbox record can share one SQLAlchemy session and one commit;
- Workspace mismatch fails before session use;
- pending reads require a positive bound;
- naive publication timestamps fail before database use;
- consumer claims deduplicate by Workspace, consumer, and immutable event ID;
- separate consumers may independently claim the same event.

Real atomicity, rollback, append-only privilege, duplicate-key, RLS, and persistence behavior were
proven by the corrected PostgreSQL suite.

## Files created

- `packages/core/src/rightjob/contracts/events.py`
- `packages/core/src/rightjob/audit/application/__init__.py`
- `packages/core/src/rightjob/audit/application/repositories.py`
- `packages/core/src/rightjob/audit/infrastructure/__init__.py`
- `packages/core/src/rightjob/audit/infrastructure/models.py`
- `packages/core/src/rightjob/audit/infrastructure/repositories.py`
- `packages/core/src/rightjob/audit/infrastructure/unit_of_work.py`
- `tests/unit/test_audit_event_contracts.py`
- `tests/unit/test_audit_repositories.py`
- `tests/unit/test_audit_unit_of_work.py`
- `tests/unit/test_outbox_atomicity_and_idempotency.py`
- `docs/implementation/026-audit-outbox-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `docs/implementation/phase-status.md`

No pre-Phase-2.6 implementation was modified.

## Source-only verification

| Gate | Result |
|---|---|
| Focused Phase 2.6 unit suite | PASS — 17 passed |
| Full pytest with services stopped | PASS — 84 passed, 24 correctly service-gated skips |
| Phase 2.6 PostgreSQL suite | PASS — 6 passed |
| Ruff format check | PASS — 187 files already formatted |
| Ruff lint | PASS |
| strict mypy | PASS — 72 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock verification | PASS — 51 packages resolved, lock unchanged |
| Frontend lint/format/type/test | NOT RERUN — no Node/npm executable is retained on this host; frontend unchanged |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed. No gate was
weakened. The attempted frontend command stopped at `npm: command not found`; installing runtime
tooling was outside the approved no-dependency-change source scope.

## Exact migration

One Audit-owned Alembic revision was created after `20260806_0001`: `20260811_0002`.

It only:

- creates `audit_entries` and `outbox_events` matching the source mappings;
- adds each table's `workspace_id` foreign key to `workspaces.id`;
- creates the declared checks, uniqueness constraint, and indexes;
- enables and forces RLS on both tables;
- creates one Workspace-isolation policy per table using transaction-local
  `app.current_workspace_id`;
- provides a downgrade that drops only these two Phase 2.6 tables and their owned objects.

It would not alter Identity columns, existing policies, dependencies, extensions, Temporal state,
or any business-domain schema.

## Exact proposed PostgreSQL fixture and mutation plan

Use only the retained PostgreSQL 17.7 cluster on `127.0.0.1:55416` and its project-local socket.
Preflight must prove PostgreSQL starts cleanly, current revision is `20260806_0001`, the three
Identity tables are empty, both new table names are absent before migration, the temporary role is
absent, and the full schema/index/constraint/RLS/policy inventory is captured.

After an approved migration to `20260811_0002`, insert exactly the existing six fixed Identity
fixtures:

```text
workspaces:  0198ff00-0000-7000-8000-000000000001
             0198ff00-0000-7000-8000-000000000002
users:       0198ff00-0000-7000-8000-000000000011
             0198ff00-0000-7000-8000-000000000012
memberships: 0198ff00-0000-7000-8000-000000000021
             0198ff00-0000-7000-8000-000000000022
```

Use only these Phase 2.6 evidence IDs:

```text
audit:  02600000-0000-4000-8000-000000000001 through ...0004
outbox: 02600000-0000-4000-8000-000000000011 through ...0014
```

Approved runtime mutations would need to cover:

- one synthetic Workspace A aggregate update plus its outbox event in one transaction;
- one Workspace A audit append in that same consequential transaction;
- rollback-only aggregate/audit/outbox writes that persist nothing;
- one duplicate outbox idempotency-key insert that fails and rolls back;
- publication metadata update only for the exact committed Workspace A outbox fixture;
- cross-Workspace and missing-context read/write attempts that persist nothing;
- an append-only privilege proof showing the verifier cannot update/delete audit rows.

No external publish or effect is required.

## Proposed temporary role and grants

Create exactly one temporary `rightjob_phase26_rls_verifier` role with `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOINHERIT`, and `NOBYPASSRLS`. Minimum grants:

- database CONNECT and public schema USAGE;
- Identity Workspace/User SELECT and Workspace UPDATE only for the atomicity fixture;
- `audit_entries`: SELECT and INSERT only;
- `outbox_events`: SELECT, INSERT, and UPDATE only.

No DELETE, TRUNCATE, schema creation, role creation, RLS bypass, or ownership grant is proposed.

## Cleanup, rollback, and shutdown plan

Stop at the first failed preflight or assertion. On test success or setup failure, remove only
exact Phase 2.6 IDs under their expected Workspace scopes, then remove the exact six Identity
fixtures in foreign-key order. Cleanup uses the database owner solely for exact-ID fixture cleanup,
not for RLS assertions. Revoke every temporary grant and drop only the temporary verifier role.

Then verify all five application tables contain zero rows, none of the fixed IDs remain, revision
is `20260811_0002`, schema matches the post-migration inventory, and no role/grant remains. If
cleanup fails, leave PostgreSQL running and report exact residue. Otherwise stop PostgreSQL cleanly
and prove no listener, socket, or PostgreSQL process remains.

Rollback testing of the migration itself would occur only if separately authorized; the normal
verification cleanup does not downgrade or alter the approved schema.

## PostgreSQL execution evidence

The first sandboxed startup attempt failed before PostgreSQL became available because the sandbox
denied `shmget`. No database action occurred. The already-approved isolated startup was repeated
outside the sandbox and succeeded:

```text
server started
127.0.0.1:55416 - accepting connections
listener: 127.0.0.1:55416 only
```

The first catalog export contained an invalid positional `ORDER BY` for a one-column projection.
The principal preflight values had already passed and no mutation occurred. Corrected read-only
catalog exports completed before migration.

Pre-migration evidence:

```text
revision=20260806_0001
counts=0,0,0
new_tables=0
temp_role=0
verification_roles=0
extensions=plpgsql
relations=14
constraints=18
indexes=10
tables_with_rls_inventory=4
policies=1
```

Alembic applied exactly one transactional migration:

```text
Running upgrade 20260806_0001 -> 20260811_0002
```

Immediate post-migration evidence:

```text
revision=20260811_0002
counts=0,0,0,0,0
new_relations=9
new_constraints=10
forced_rls=audit_entries:true:true,outbox_events:true:true
policies=audit_entries:audit_entries_workspace_isolation:ALL,
         outbox_events:outbox_events_workspace_isolation:ALL
```

### Initial verification-harness failure

The approved integration module stopped during fixture setup. Psycopg rejected Python `dict`
parameters passed through an untyped raw `text()` statement for JSONB columns:

```text
psycopg.ProgrammingError:
cannot adapt type 'dict' using placeholder '%s' (format: AUTO)
6 errors during shared fixture setup
```

This was a verification-harness setup defect, not evidence that the migration, SQLAlchemy mapped
repositories, PostgreSQL RLS, atomic transaction behavior, or idempotency constraint failed. None
of the six behavioral tests reached its assertions in that attempt. Fail-closed rules prohibited
correcting and rerunning the failed proof without a new owner approval.

The failing setup used one owner transaction. PostgreSQL rolled back the role, grants, six Identity
inserts, and attempted Phase 2.6 inserts together. No fixture finalizer was needed to remove durable
state because setup never committed.

Post-failure residue and integrity proof:

```text
revision=20260811_0002
counts=0,0,0,0,0
fixture_ids=0
role=0
grants=0
forced_rls=audit_entries:true:true,outbox_events:true:true
policies=2
preexisting_schema_match=true
```

All pre-existing Phase 2.1–2.5 relations, constraints, and indexes matched the preflight inventory.
The approved Phase 2.6 migration remains applied and empty.

Shutdown evidence:

```text
server stopped
pg_ctl: no server running
127.0.0.1:55416 - no response
socket entries: none
listener: none
```

### Approved harness correction and corrected proof

Owner review accepted the classification:

```text
PHASE 2.6 VERIFICATION-HARNESS DEFECT — AUDIT/OUTBOX FOUNDATION NOT YET FAILED
```

Only the two Phase 2.6 JSONB fixture inserts changed. Untyped raw `text()` statements were replaced
with SQLAlchemy Core `insert(AuditEntryRecord)` and `insert(OutboxEventRecord)` statements. The
existing mapped `JSONB` columns supplied dictionary adaptation. No manual JSON serialization,
production change, migration change, dependency, or RLS change was made.

Corrected-run preflight:

```text
revision=20260811_0002
counts=0,0,0,0,0
fixture_ids=0
role=0
relations=23
constraints=28
indexes=17
fks=fk_audit_entries_workspace:ON DELETE RESTRICT,
    fk_outbox_events_workspace:ON DELETE RESTRICT
forced_rls=audit_entries:true:true,outbox_events:true:true
policies=audit_entries:audit_entries_workspace_isolation:ALL,
         outbox_events:outbox_events_workspace_isolation:ALL
```

Corrected Phase 2.6 PostgreSQL suite:

```text
tests/integration/test_audit_outbox_transactions.py
6 passed in 0.80s
```

Behavior evidence:

| Proof | Result |
|---|---|
| Temporary role | PASS — non-superuser, no create-db, no create-role, no inherit, no RLS bypass |
| Minimum grants | PASS — Audit SELECT/INSERT; Outbox SELECT/INSERT/UPDATE; required Identity access only |
| Atomicity | PASS — Workspace update, Audit evidence, and Outbox event persisted together |
| Commit count | PASS — SQLAlchemy `after_commit` observed exactly one commit |
| Aggregate version | PASS — version incremented exactly once from 1 to 2 |
| Correlation/causation | PASS — exact IDs matched across Audit and Outbox |
| Rollback | PASS — aggregate retained committed state; rollback Audit/Outbox IDs absent |
| Session cleanup | PASS — connection pool returned to zero checked-out sessions |
| Append-only repository | PASS — repository exposes append and no update/delete operation |
| Append-only role | PASS — direct verifier UPDATE and DELETE failed with permission denied |
| Idempotency key | PASS — duplicate `(workspace_id, idempotency_key)` rejected |
| Duplicate event ID | PASS — duplicate primary key rejected |
| Failed duplicates | PASS — original Outbox event remained exactly once and unchanged |
| Workspace RLS | PASS — Workspace A saw only A; Workspace B records remained invisible |
| Cross-Workspace write | PASS — cross-Workspace insert denied and update affected zero rows |
| Missing context | PASS — reads returned zero rows and insert was denied |
| Publication update | PASS — exact Workspace A Outbox row received the approved timestamp |

Corrected-run final cleanup and schema comparison:

```text
revision=20260811_0002
counts=0,0,0,0,0
fixture_ids=0
role=0
grants=0
schema_constraints_indexes_fks_rls_policies_match=true
```

Final corrected-run shutdown:

```text
server stopped
pg_ctl: no server running
127.0.0.1:55416 - no response
socket entries: none
listener: none
PostgreSQL data-directory process: none
```

## Files changed during PostgreSQL verification

- `db/migrations/versions/audit_20260811_0002_audit_entries_outbox_events.py`
- `tests/integration/test_audit_outbox_transactions.py`
- `docs/implementation/026-audit-outbox-foundation-verification-report.md`

No other source, migration, API, Identity, Temporal, provider, business-domain, or frontend file
changed during this step.

## Deferred work and risks

- Durable consumer receipt persistence is consumer-owned and deferred until a real consumer exists.
- Outbox relay scheduling, backoff, leasing, dead-letter/reconciliation, metrics, and retention are
  deferred; no broker is justified yet.
- Audit acceptance policy, retention/partitioning, controlled evidence artifacts, and audit-query
  APIs are deferred.
- No claim is made that producer modules emit production events yet.
- The nested event payload is validated on construction but is not deeply immutable; producers
  must not mutate it after construction. A future schema/code-generation decision may harden this
  without changing envelope ownership.

## Final verdict

`PHASE 2.6 AUDIT EVIDENCE AND TRANSACTIONAL OUTBOX FOUNDATION PASSED`
