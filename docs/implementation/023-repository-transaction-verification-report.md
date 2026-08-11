# Phase 2.3 Repository and Transaction Verification Report

**Date:** 2026-08-07  
**Scope:** Identity/Tenancy repository and transaction foundation only  
**Verdict:** `PHASE 2.3 REPOSITORY AND TRANSACTION FOUNDATION PASSED`

## Architecture review

```text
Status: approved
Ownership: Identity/Tenancy owns its Repository and Unit of Work contracts and implementations.
Affected modules: Identity/Tenancy and the FastAPI composition root only.
Duplication findings: Existing repositories were extended; no generic cross-module repository was added.
Security findings: Explicit commit, rollback, close, version checks, and fail-closed DI are retained.
Tenancy findings: Membership operations retain explicit workspace filters and transaction-local RLS context.
Scale findings: One request-scoped session/UoW; no capacity claim.
Required contracts: Owner-scoped repositories, optimistic concurrency error, Identity Unit of Work.
Required tests: Unit lifecycle/concurrency tests, non-database DI test, real PostgreSQL/RLS transaction tests.
Required observability: No new runtime business boundary or external effect in this phase.
Unresolved decisions: None. PostgreSQL execution requires separate approval.
Recommended architecture: Extend the existing Identity repositories and use SQLAlchemy's installed session support.
```

No migration, dependency, schema field, ownership transfer, CRUD endpoint, business workflow,
provider, AI, Department, command, event, worker, or Phase 2.4 behavior was introduced.

## Source implementation

- Repository interfaces now expose owner-scoped `save` operations.
- Updates match aggregate ID and expected version, increment version exactly once, and raise
  `ConcurrentUpdateError` when no row matches.
- Membership saves require the supplied Workspace scope to match the aggregate and retain the
  transaction-local `app.current_workspace_id` RLS context.
- `IdentityUnitOfWork` exposes Identity-owned repositories plus explicit `commit`, `rollback`, and
  `close` boundaries.
- `SqlAlchemyIdentityUnitOfWork` rolls back exceptions and uncommitted work and always closes its
  session.
- FastAPI dependencies create one Unit of Work per request and derive all three repositories from
  that same boundary. Missing configuration fails with HTTP 503.

## Suspected Phase 2.2 defect review

A focused regression test was added before any implementation correction. It asserts that
`SqlAlchemyWorkspaceRepository.add()` maps `Workspace.status` to the storage value `"active"`.
The test passed unchanged because `RecordStatus` is a string-backed enum. The suspected defect was
not proven, and no Phase 2.2 implementation was changed for it.

Evidence:

```text
tests/unit/test_identity_mappings.py::test_workspace_repository_maps_status_to_storage_value
1 passed
```

## Source-only evidence

| Gate | Result |
|---|---|
| Focused suspected-defect regression | PASS — 1 passed |
| Non-integration tests | PASS — 31 passed, 17 deselected |
| Non-database integration selection | PASS — 10 passed |
| Full suite with PostgreSQL stopped | PASS — 42 passed, 10 PostgreSQL tests skipped |
| Phase 2.3 PostgreSQL scaffold | Correctly skipped — 4 tests require isolated URLs |
| Ruff format | PASS — 154 files formatted |
| Ruff lint | PASS |
| mypy strict | PASS — 55 source files |
| Architecture boundaries | PASS |

The existing Starlette TestClient/httpx deprecation warning remains unchanged and unsuppressed.

## PostgreSQL verification

Only the retained project-local PostgreSQL 17.7 cluster, database `rightjob_phase16`,
project-local socket, address `127.0.0.1`, and port `55416` were used. No migration ran.

Startup completed with `server started`; `pg_isready` reported `accepting connections`.
The first read-only inventory used a relative socket argument that `psql` treated as a hostname;
no SQL executed. The corrected absolute socket connected. A later read-only relation expression
required an explicit `relkind::text` cast. Neither read-only correction mutated the database.

Pre-mutation evidence:

```text
revision=20260806_0001
counts=0,0,0
role_count=0
relations=14 expected public tables/indexes
extensions=plpgsql
rls=true,true
policy=memberships_workspace_isolation:ALL
constraints=18
indexes=10
```

The existing isolated RLS fixture:

1. create temporary role `rightjob_phase21_rls_verifier` with `NOSUPERUSER`, `NOINHERIT`, and
   `NOBYPASSRLS`;
2. grant only database connect, schema usage, Membership CRUD, and Workspace/User SELECT;
3. insert two fixed Workspaces, two fixed Users, and two fixed Memberships;
4. run the existing six Phase 2.2 RLS/read-only tests;
5. ran seven Phase 2.3 tests for role/grant restrictions, committed versioned update, explicit
   rollback, implicit rollback, exception rollback/session release, stale-version rejection, and
   Workspace-scope mismatch rejection;
6. rerun all source and quality gates;
7. removed the exact fixture rows, revoked exact grants, dropped the temporary role, verified zero
   rows and no verifier role, then stopped PostgreSQL and proved no process/socket/listener remained.

The first combined database run passed all six existing RLS tests, then stopped at the first
Phase 2.3 setup error because the reused fixture had not registered in the new test module. The
Phase 2.2 fixture cleaned successfully: revision remained exact, row counts and fixed-ID counts
were zero, and the role was absent. No repository assertion failed. The test module was corrected
to register the existing fixture as a pytest plugin; `pytest --fixtures` proved discovery without
executing a mutation. The corrected approved run passed.

## Database behavior evidence

| Proof | Result |
|---|---|
| Existing non-bypass RLS suite | PASS — 6 tests |
| Phase 2.3 database suite | PASS — 7 tests |
| Temporary role attributes | PASS — superuser, create-db, create-role, inherit, and bypass-RLS all false |
| Temporary table grants | PASS — Membership CRUD; User/Workspace SELECT only |
| Commit | PASS — role persisted and version increment matched returned aggregate |
| Explicit rollback | PASS — stored role remained `owner` |
| Implicit rollback | PASS — omitted commit left stored role `owner` |
| Exception rollback | PASS — raised exception left stored role `owner` |
| Optimistic concurrency | PASS — stale writer raised `ConcurrentUpdateError` |
| Workspace scope | PASS — Workspace A returned only Workspace A; mismatch raised `ValueError` |
| RLS reads/writes | PASS — cross-Workspace and missing-context access denied |
| Session cleanup | PASS — pool checked-out count returned to zero after success and failure |
| Request-scoped DI | PASS — one UoW shared by all three repository dependencies and closed afterward |

Exact fixture IDs:

```text
workspaces:  0198ff00-0000-7000-8000-000000000001
             0198ff00-0000-7000-8000-000000000002
users:       0198ff00-0000-7000-8000-000000000011
             0198ff00-0000-7000-8000-000000000012
memberships: 0198ff00-0000-7000-8000-000000000021
             0198ff00-0000-7000-8000-000000000022
```

## Exact test mutations performed

No schema or migration mutation occurred. Test-only mutations were:

- create and later drop one temporary non-bypass role;
- grant and later revoke its narrowly listed privileges;
- insert and later delete exactly six fixed fixture rows;
- update only fixture Membership A's `role`, `updated_at`, and `version` during commit/concurrency
  tests;
- perform rollback-only Membership updates that must leave no durable change;
- set transaction-local `app.current_workspace_id` values through `set_config(..., true)`.

## Cleanup and schema-drift evidence

The fixture deleted only its fixed UUIDs before and after execution. Cleanup revoked each grant
before dropping the role. Every uncommitted Unit of Work rolled back and closed. No truncation,
broad deletion, database recreation, RLS disablement, migration, stamp, or schema edit occurred.

Final database evidence after the complete suite:

```text
revision=20260806_0001
counts=0,0,0
role_count=0
fixture_ids=0
public_relations=14
constraints=18
indexes=10
extensions=plpgsql
rls=true,true
policy=memberships_workspace_isolation:ALL
```

The full preflight and post-test relation, constraint, index, extension, RLS, and policy listings
matched. Temporary grants disappeared with the removed role.

## Final quality gates

| Gate | Result |
|---|---|
| Full database-enabled pytest | PASS — 55 tests |
| Ruff format | PASS — 155 files |
| Ruff lint | PASS |
| mypy strict | PASS — 55 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 47 packages |

The existing Starlette TestClient/httpx deprecation warning remains unchanged and unsuppressed.

## Shutdown evidence

`pg_ctl -m fast -w stop` returned `server stopped`. After shutdown:

```text
pg_isready: exit 2, no response
pg_ctl status: exit 3, no server running
PostgreSQL/Postgres process count: 0
```

## Files changed during database verification

- `tests/integration/test_identity_repository_transactions.py` — corrected fixture registration
  and added direct role/grant, explicit rollback, exception rollback, and session-release proofs.
- `docs/implementation/023-repository-transaction-verification-report.md` — final evidence and
  verdict.

## Final verdict

`PHASE 2.3 REPOSITORY AND TRANSACTION FOUNDATION PASSED`

Phase 2.4 has not begun.
