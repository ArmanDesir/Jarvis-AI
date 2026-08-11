# Phase 2.4 API Application Foundation Verification Report

**Date:** 2026-08-07  
**Scope:** Minimal Identity/Tenancy HTTP application boundary  
**Verdict:** `PHASE 2.4 API APPLICATION FOUNDATION PASSED`

## Summary

Phase 2.4 adds four typed, authenticated, active-Workspace API operations; a minimal
Identity/Tenancy application service; owner/admin Workspace-update authorization; explicit Unit of
Work mutation coordination; optimistic-concurrency translation; centralized sanitized errors;
correlation propagation; audit-ready in-memory mutation metadata; and deterministic internal
OpenAPI verification.

Arbitrary Workspace settings, slug mutation, permission management, audit persistence, business
domains, AI, workflows, Departments, Memory, providers, external effects, public API documentation,
and Phase 2.5 remain deferred. No migration, schema change, or dependency change was made.

## Files changed

Created:

- `packages/core/src/rightjob/identity/application/authorization.py`
- `packages/core/src/rightjob/identity/application/operations.py`
- `apps/api/src/rightjob_api/contracts.py`
- `apps/api/src/rightjob_api/errors.py`
- `apps/api/src/rightjob_api/routes.py`
- `tests/unit/test_identity_operations.py`
- `tests/integration/test_api_application.py`
- `tests/integration/test_api_application_database.py`
- `tests/integration/test_openapi_schema.py`
- `tests/phase24_runtime_app.py`
- `docs/implementation/024-api-application-foundation-verification-report.md`

Modified:

- `packages/core/src/rightjob/identity/application/__init__.py`
- `apps/api/src/rightjob_api/main.py`
- `apps/api/src/rightjob_api/identity_middleware.py`
- `scripts/check_phase1_scope.py`
- `tests/unit/test_authentication.py`
- `tests/unit/test_identity_service.py`

No migration, lockfile, package manifest, authentication adapter, repository implementation,
middleware authorization order, or Phase 2.2 `/identity/context` route behavior was removed.

## Route inventory

| Method | Path | Operation ID | Authorization | Request | Response |
|---|---|---|---|---|---|
| GET | `/health` | existing generated ID | public when anonymous | none | existing health contract |
| GET | `/ready` | existing generated ID | public when anonymous | none | existing readiness contract |
| GET | `/version` | existing generated ID | public when anonymous | none | existing version contract |
| GET | `/identity/context` | frozen Phase 2.2 ID | bearer + active Workspace | none | frozen Phase 2.2 verification body |
| GET | `/api/v1/me` | `getCurrentPrincipalContext` | bearer + active Membership | none | `CurrentPrincipalResponse` |
| GET | `/api/v1/workspace` | `getCurrentWorkspace` | bearer + active Membership | none | `WorkspaceResponse` |
| PATCH | `/api/v1/workspace` | `updateCurrentWorkspace` | bearer + owner/admin | `WorkspacePatchRequest` | `WorkspaceResponse` |
| GET | `/api/v1/membership` | `getCurrentMembership` | bearer + active Membership | none | `MembershipResponse` |

`WorkspacePatchRequest` requires `expected_version` and at least one of `name`, `timezone`, or
`locale`. Extra fields are forbidden. ID, slug, settings, ownership, membership roles, security
policy, and authentication data cannot be mutated.

## Application-service boundaries

Routes map Pydantic HTTP contracts and call `IdentityApplicationService`. The application service
coordinates current-context reads and Workspace update. `WorkspaceAuthorization` owns the narrow
active-membership and owner/admin decisions. Repositories own exact-ID persistence and versioned
save. `IdentityUnitOfWork` owns commit, rollback, and close. Routes and middleware do not import or
call SQLAlchemy models.

Workspace update loads the exact resolved Workspace, compares the persisted version, creates an
updated immutable aggregate, calls the repository, commits exactly once, and returns structured
mutation metadata containing correlation, actor, Workspace, Membership, operation, target,
expected/resulting versions, timestamp, and outcome. That metadata remains internal and is not
persisted or exposed in the Workspace response.

## Error model

Runtime errors use `ProblemDetail`: `type`, `title`, HTTP `status`, stable `code`, safe `detail`,
request `instance`, `correlation_id`, and safe structured validation `errors`.

| Condition | HTTP | Code |
|---|---:|---|
| Missing/malformed/expired/invalid token | 401 | existing neutral authentication code |
| Inactive or unauthorized Workspace context | 403 | `workspace_access_denied` or `FORBIDDEN` |
| Authorized-scope resource absent | 404 | `NOT_FOUND` |
| Invalid body | 422 | `VALIDATION_ERROR` |
| Stale version | 409 | `VERSION_CONFLICT` |
| Database/internal failure | 500 | `INTERNAL` |

Database exceptions, exception messages, SQL, JWT contents, URLs, credentials, and stack traces are
not returned or logged by the central translators.

## Authorization and transaction source evidence

- Owner update: success, version increments once, commit exactly once.
- Admin update: success and commit exactly once.
- Member update: 403, zero commits, rollback and close.
- Stale version: 409, zero commits, rollback and close.
- Invalid/extra fields: 422, zero commits, close.
- Internal/database failure: sanitized 500, zero commits, rollback and close.
- Inactive User, Membership, and Workspace: fail closed in Identity resolution tests.
- Multiple Memberships and missing requested Membership: exact Workspace resolution remains proven.
- Read-only Workspace/Membership requests use one UoW and close without commit.

## OpenAPI evidence

Public `/openapi.json`, Swagger, and ReDoc remain disabled. Internal `app.openapi()` is OpenAPI 3.1
and deterministic across fresh generation. Tests prove the exact seven public path keys (with GET
and PATCH sharing the Workspace path), explicit operation IDs, typed request/response schemas,
provider-neutral `BearerAuth`, and documented 401/403/404/409/422/500 responses where applicable.
The exact route-scope script independently rejects additions or removals.

## Source-only quality gates

| Gate | Result |
|---|---|
| Source-only pytest | PASS — 60 passed, 13 PostgreSQL tests skipped |
| Ruff format | PASS — 163 files |
| Ruff lint | PASS |
| mypy strict | PASS — 60 source files |
| Architecture boundaries | PASS |
| Exact phase route scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 47 packages |
| Internal OpenAPI determinism/scope | PASS — 2 tests |

The existing Starlette TestClient/httpx deprecation warning remains unchanged and unsuppressed.
One initial unit-test collection run exposed a test-only missing postponed-annotation import and
was corrected. One integration run proved router-level 404 uses Starlette's base HTTP exception;
central registration was corrected and the full source-only suite passed.

## Database evidence

Only the retained PostgreSQL 17.7 cluster, `rightjob_phase16`, localhost port `55416`, and the
project-local socket were used. Startup completed and `pg_isready` reported accepting connections.
Preflight proved revision `20260806_0001`, application row counts `0,0,0`, no verification role,
14 expected public relations, 18 constraints, 10 indexes, forced Membership RLS, and the single
`memberships_workspace_isolation:ALL` policy.

Use the same six fixed fixture IDs:

```text
workspaces:  0198ff00-0000-7000-8000-000000000001
             0198ff00-0000-7000-8000-000000000002
users:       0198ff00-0000-7000-8000-000000000011
             0198ff00-0000-7000-8000-000000000012
memberships: 0198ff00-0000-7000-8000-000000000021
             0198ff00-0000-7000-8000-000000000022
```

The proof created only temporary role `rightjob_phase21_rls_verifier` with `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOINHERIT`, and `NOBYPASSRLS`. Grant database connect, public-schema usage,
Membership SELECT, Workspace SELECT/UPDATE, and User SELECT. Membership INSERT/UPDATE/DELETE may
remain only if the existing Phase 2.1–2.3 RLS suite runs in the same approved lifecycle.

Test mutations performed:

- insert the exact two Workspaces, two Users, and two Memberships;
- update only Workspace A `name`, `timezone`, `locale`, `updated_at`, and `version`;
- executed stale/forbidden/invalid/failure requests that rolled back or made no write;
- set transaction-local Workspace context;
- delete only the six exact fixture IDs during cleanup;
- revoke exact grants and drop only the temporary role.

The Phase 2.4 database API module passed three tests. It proved authenticated current-context reads,
exact Workspace update, version `1 → 2`, unchanged Workspace B, stale `409`, cross-Workspace `403`,
invalid-body `422`, forced application failure rollback, and preservation of the committed
Workspace A values after every failed request. Earlier non-bypass RLS and transaction suites also
passed in the final database-enabled run.

Cleanup deleted Membership IDs first by exact ID and Workspace ownership, then exact User and
Workspace IDs. It revoked every grant before dropping the role. Cleanup output was exactly
`DELETE 2`, `DELETE 2`, `DELETE 2`, five revocations, and one role removal. Final database evidence
after runtime and again after the full suite was:

```text
revision=20260806_0001
counts=0,0,0
role=0
fixtures=0
relations=14
constraints=18
indexes=10
rls=true,true
policy=memberships_workspace_isolation:ALL
```

The complete preflight and post-runtime relation, constraint, index, RLS, and policy listings
matched exactly. No migration, stamp, schema change, truncation, broad deletion, RLS disablement,
or additional role occurred.

## Runtime evidence

A test-only composition used the neutral JWT adapter and temporary application role, then launched
Uvicorn on `127.0.0.1:8024`. Startup logged `api.started` and `Application startup complete`.

| Request | Result | Sanitized evidence |
|---|---:|---|
| `GET /health` | 200 | running |
| `GET /ready` | 200 | required dependencies ready; existing semantics preserved |
| `GET /version` | 200 | `rightjob-api`, `0.1.0`, `dev` |
| `GET /api/v1/me` | 200 | exact User/Workspace/Membership, owner, neutral provider |
| `GET /api/v1/workspace` | 200 | Workspace A, version 1, no settings |
| `GET /api/v1/membership` | 200 | caller Membership only |
| `PATCH /api/v1/workspace` | 200 | approved fields, resulting version 2 |
| stale PATCH | 409 | `VERSION_CONFLICT` |
| cross-Workspace PATCH | 403 | nondisclosing `workspace_access_denied` |
| invalid PATCH | 422 | safe field detail; slug rejected |
| missing token | 401 | `missing_token` |
| unknown route | 404 | `NOT_FOUND` |

Every application/error response carried the supplied correlation ID; anonymous system responses
carried generated correlation IDs. Captured runtime logs contained only startup/shutdown facts and
HTTP method/path/status lines. They contained no JWT, database URL, SQL, credential, request body,
or response payload.

The first sandboxed SIGTERM command was denied before signal delivery. The required escalated
SIGTERM succeeded. Uvicorn logged `Shutting down`, `api.stopped`, `Application shutdown complete`,
and `Finished server process`; the wrapper reported signal exit 143 with no orphan process.

## Final quality gates

| Gate | Result |
|---|---|
| Full database-enabled pytest | PASS — 76 tests |
| Phase 2.4 real database API | PASS — 3 tests |
| Ruff format | PASS — 166 files |
| Ruff lint | PASS |
| mypy strict | PASS — 60 source files |
| Architecture boundaries | PASS |
| Exact phase route scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 47 packages |
| Internal OpenAPI determinism/scope | PASS |

The unchanged Starlette TestClient/httpx deprecation warning remains visible and unsuppressed.

## Final shutdown

PostgreSQL stopped through `pg_ctl -m fast -w stop` with `server stopped`. Final checks:

```text
pg_isready: exit 2, no response
pg_ctl status: exit 3, no server running
port 55416 listener: none
port 8024 listener: none
project-local PostgreSQL socket: none
PostgreSQL/Uvicorn/runtime process: none
```

## Architecture compliance

- Migration/schema change: none.
- Dependency/lock change: none.
- Business domain: none.
- AI/Memory/Department/workflow/provider coupling: none.
- Authentication remains provider-neutral.
- RLS/repository/UoW boundaries remain intact.
- Public API documentation remains disabled.
- Phase 2.5 has not begun.

## Remaining risks

- Full permission management is deferred.
- Audit persistence is deferred.
- External identity provider selection remains proof-gated.
- Mutation concurrency beyond the tested Workspace operation is unproven.
- Rate limiting is deferred.
- Production security and load testing are deferred.
- Production database-role provisioning remains deferred.

## Final verdict

`PHASE 2.4 API APPLICATION FOUNDATION PASSED`

Phase 2.5 has not begun.
