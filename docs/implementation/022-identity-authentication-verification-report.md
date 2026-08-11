# Phase 2.2 Identity and Authentication Verification Report

**Date:** 2026-08-06  
**Scope:** External identity verification and Workspace Membership resolution only  
**Verdict:** `PHASE 2.2 IDENTITY FOUNDATION PASSED`

## Summary

Phase 2.2 adds a provider-neutral authentication boundary, strict JWT verification,
read-only identity resolution, canonical Principal and AuthorizationContext values,
FastAPI authentication and Workspace-context middleware, and request-scoped dependency
injection.

No login, OAuth flow, session, refresh token, password, invitation, email verification,
business permission, CRUD endpoint, AI, Memory, Department, workflow, billing, Tenant,
Organization, or Agency model was implemented. No database migration was required.

## Files changed

### Core Identity/Tenancy

- `packages/core/pyproject.toml` — provider-neutral PyJWT runtime dependency.
- `uv.lock` — real UV-generated lock now includes PyJWT 2.13.0.
- `packages/core/src/rightjob/identity/application/__init__.py`
- `packages/core/src/rightjob/identity/application/authentication.py`
- `packages/core/src/rightjob/identity/application/context.py`
- `packages/core/src/rightjob/identity/application/repositories.py`
- `packages/core/src/rightjob/identity/application/service.py`
- `packages/core/src/rightjob/identity/infrastructure/__init__.py`
- `packages/core/src/rightjob/identity/infrastructure/jwt.py`
- `packages/core/src/rightjob/identity/infrastructure/repositories.py`

### API composition

- `apps/api/src/rightjob_api/dependencies.py`
- `apps/api/src/rightjob_api/identity_middleware.py`
- `apps/api/src/rightjob_api/main.py`
- `scripts/check_phase1_scope.py` — permits only the new identity-context bootstrap
  route in addition to existing system routes.

### Tests

- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/unit/test_authentication.py`
- `tests/unit/test_identity_service.py`
- `tests/integration/test_identity_http.py`
- `tests/integration/test_identity_tenancy_rls.py` — adds read-only service resolution
  and temporary SELECT grants for platform roots during the isolated proof.
- `docs/implementation/022-identity-authentication-verification-report.md`

No Phase 2.1 migration, schema, ADR, Constitution ownership rule, API specification,
roadmap, or sprint plan was changed.

## Architecture compliance

- Workspace remains the canonical tenant and agency boundary.
- `workspace_id` remains the sole tenant key.
- Identity/Tenancy alone resolves User, Membership, and Workspace records.
- User is resolved by provider-neutral `(external_identity_provider, external_subject)`.
- Membership resolution sets transaction-local Workspace context and is explicitly
  filtered by `workspace_id` and `user_id`.
- Workspace is loaded by exact requested Workspace ID.
- Authentication output contains no business data.
- Permissions remain empty because business authorization is outside this phase.
- No provider SDK or Clerk-specific claim, column, DTO, or code exists.
- No Tenant, Organization, or Agency model exists.
- No database write occurs during identity resolution.
- Authenticated requests cannot bypass Workspace resolution, including requests to a
  normally public bootstrap path when credentials are presented.

## Provider abstraction

`AuthenticationProvider` is the application boundary. It returns only an
`ExternalIdentity(provider, subject)`. `JwtVerifier` separately owns token verification.
`JwtAuthenticationProvider` maps verified standard `sub` claims to the neutral identity.

`PyJwtVerifier` is an infrastructure adapter. It requires an explicit verification key,
an explicit algorithm allow-list, `exp`, and `sub`; it rejects `none`. It maps expired,
malformed, invalid-signature, and otherwise invalid tokens to typed authentication
errors. No verification key or credential is stored in source control.

Clerk and Auth.js remain proof-gated under ADR-001. No concrete production identity
provider was selected. The default API therefore fails closed with
`authentication_unavailable` on protected routes until an approved provider is wired.

## Principal and authorization context

The canonical Principal contains exactly:

- internal `user_id`;
- verified `external_subject`;
- `workspace_id`;
- `membership_id`;
- Membership-derived roles;
- permissions (empty in this phase);
- neutral authentication-provider name.

`AuthorizationContext` contains the Principal plus the resolved Workspace and
Membership. It owns no business record or permission logic.

## Middleware verification

Middleware order is correlation → authentication → Workspace context → route.

| Case | Result |
|---|---|
| Valid bearer token and authorized Workspace | 200; context injected. |
| Missing token | 401 `missing_token`. |
| Malformed token | 401 `malformed_token`. |
| Expired token | 401 `expired_token`. |
| Invalid signature | 401 `invalid_token`. |
| Valid token without Workspace header | 400 `workspace_required`. |
| Valid token for unauthorized Workspace | 403 `workspace_access_denied`. |
| Authenticated request to public health path with unauthorized Workspace | 403; no bypass. |
| Anonymous health request | remains public and returns 200. |
| No configured production provider | protected route fails closed with 503. |

Errors do not disclose whether another Workspace, User, or Membership exists.

## Dependency injection verification

FastAPI `Annotated` request dependencies provide:

- `CurrentAuthorizationContext`;
- `CurrentPrincipal`;
- `CurrentWorkspace`;
- `CurrentMembership`.

The `/identity/context` bootstrap endpoint exercised all four dependencies in one
request and proved that their IDs and Principal values refer to the same resolved
context. It performs no mutation and exposes no business endpoint.

## JWT verification evidence

PyJWT 2.13.0 was resolved by UV and installed into the project-local virtual
environment. Tests used non-production HMAC keys longer than the 32-byte SHA-256
minimum. Evidence:

| Token | Result |
|---|---|
| Correct signature, subject, and future expiry | PASS. |
| Wrong signature | PASS — `invalid_token`. |
| Past expiry | PASS — `expired_token`. |
| Non-JWT text | PASS — `malformed_token`. |
| Missing Authorization header | PASS — `missing_token`. |

These tests prove the neutral JWT adapter, not a Clerk/Auth.js proof or production key
configuration.

## Workspace and Membership resolution evidence

IdentityService executes the accepted order:

1. resolve the platform User by verified external identity;
2. resolve the User's Membership under exact Workspace/RLS context;
3. reject missing or suspended Membership;
4. resolve the exact Workspace;
5. reject inactive Workspace/User;
6. build Principal and AuthorizationContext.

Tests passed for an authorized Workspace, a non-member Workspace, two memberships with
selection of only the requested Workspace, and an inactive Membership.

The real PostgreSQL proof used two Workspaces, two Users, and two Memberships. Identity
resolution ran through SQLAlchemy repositories as temporary role
`rightjob_phase21_rls_verifier`, configured `NOSUPERUSER`, `NOINHERIT`, and
`NOBYPASSRLS`. The role received only temporary table SELECT plus the pre-existing RLS
test permissions. Counts were `(2,2,2)` before and after resolution, proving read-only
behavior. All test rows, grants, and the role were removed. Final database evidence was:

```text
revision: 20260806_0001
workspaces,users,memberships row counts: 0,0,0
temporary verifier role count: 0
```

## FastAPI startup and shutdown evidence

Production-like command:

```text
.venv/bin/uvicorn rightjob_api.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8012
```

The restricted sandbox first denied the localhost bind after successfully exercising
startup and shutdown hooks. The same command was then run with localhost-only execution
permission.

| Route | Status | Sanitized result |
|---|---:|---|
| `/health` | 200 | `{"status":"running"}` |
| `/ready` | 200 | required bootstrap dependencies ready; identity disabled by default |
| `/version` | 200 | `rightjob-api`, version `0.1.0`, build `dev` |
| `/identity/context` without configured provider | 503 | `authentication_unavailable` |

SIGTERM produced `Shutting down`, `api.stopped`, `Application shutdown complete`, and
`Finished server process`. TestClient lifespan tests also passed. The PTY command wrapper
reported exit 1 after the externally delivered SIGTERM despite Uvicorn's complete clean
shutdown log; no process remained.

## Quality gate results

| Gate | Result |
|---|---|
| Ruff format check | PASS — 148 files formatted. |
| Ruff lint | PASS. |
| mypy strict | PASS — 54 source files. |
| pytest final complete run | PASS — 41 tests. |
| Authentication/JWT tests | PASS. |
| Middleware/DI tests | PASS. |
| Real PostgreSQL read-only/RLS tests | PASS. |
| Architecture boundaries | PASS. |
| Phase scope | PASS. |
| Migration safety | PASS. |
| Secret hygiene | PASS. |
| Python compilation | PASS. |
| UV lock check | PASS — 47 packages. |
| PostgreSQL shutdown | PASS — project-local socket reported no response. |

The existing FastAPI/Starlette `httpx` deprecation warning remains unchanged and does
not affect this phase's behavior. No dependency-major upgrade or lint weakening was
introduced.

## Remaining risks

- Clerk versus Auth.js remains an accepted proof-gate decision. No production identity
  provider, JWKS fetching/caching, key rotation, issuer, audience, or geographic policy
  has been configured.
- Production database roles and grants are not created in this phase. They must enforce
  least privilege before real authenticated traffic is enabled.
- Role values are surfaced from Membership, but business permission mapping remains
  deliberately absent.
- Token revocation, sessions, refresh, login, invitations, and account lifecycle remain
  outside scope.
- The TestClient `httpx` deprecation must be handled in a separate compatible dependency
  review; it was not suppressed.

## Final verdict

`PHASE 2.2 IDENTITY FOUNDATION PASSED`

Phase 2.3 was not started.
