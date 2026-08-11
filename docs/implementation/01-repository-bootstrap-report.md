# Phase 1 Repository Bootstrap Report

**Date:** 2026-07-29  
**Scope review:** Approved  
**Implementation verdict:** PHASE 1 PASSED WITH CONDITIONS

## Summary

### Implemented

- One modular repository with separate FastAPI API, idle worker, and Next.js
  frontend process roots.
- Vendor-free core module placeholders for every required architecture boundary.
- Trusted first-party Marketing, Website, and Operations placeholders with no
  Capability behavior.
- Environment loading/validation, JSON logging, request/correlation identifiers,
  structured errors, clock, pagination, Result convention, module metadata, and
  shutdown handling.
- API routes limited to `/health`, `/ready`, and `/version`.
- Idle worker lifecycle with process identity and signal-based shutdown.
- PostgreSQL/Alembic migration foundation with module ownership, direct-RLS, and
  `pgvector` gate checks.
- Optional local PostgreSQL Compose service.
- Unit, integration, architecture, API, worker, migration, and future tenant-RLS
  test scaffolding.
- Python import-boundary, Phase 1 scope, migration, and secret-hygiene checks.
- Formatting, lint, type, test, build, migration, clean, and CI commands.
- Validation-only GitHub Actions workflow; no deployment automation.
- Root and implementation documentation.

### Already existed

Only architecture and product documentation existed. There was no application
source, package manifest, lockfile, CI, environment file, Docker file, database
tooling, test framework, or duplicate bootstrap configuration.

### Changed

The stale documentation-only root README was replaced with the Phase 1 setup and
status entry point. No Constitution, ADR, ownership rule, approved architecture
document, schema, API specification, roadmap, or sprint plan was modified.

### Intentionally deferred

Business Capabilities, Department behavior, Executive/Planner/Memory behavior,
workflow compilation/execution, authentication, provider integrations, external
effects, production tables, production deployment, WebSockets, outbox behavior,
and all Phase 2+ work.

## Stack used

| Item | Exact selection | Authority or assumption |
|---|---|---|
| Python runtime | Python `>=3.11`; CI target uses UV-managed compatible Python | FastAPI/Python approved architecture; version is a bootstrap assumption |
| Python package manager/workspace | UV `0.12`, workspace mode | Smallest workspace tool compatible with approved modular repository; ADR-001 does not prescribe a manager |
| Node runtime | Node `>=20.20.2`, npm `>=10`; host validation used Node `20.20.2`/npm `10.8.2` | Next.js approved architecture; version is a bootstrap assumption |
| JavaScript workspace | Native npm workspaces | Avoids an additional monorepo tool |
| API | FastAPI `>=0.115,<1`, Uvicorn `>=0.34,<1` | Approved technical architecture |
| Worker | Separate Python process using `asyncio` lifecycle only | ADR-001 separate API/workers; no workflow engine adopted |
| Frontend | Next.js `15.5.4`, React `19.1.1`, TypeScript `5.9.2` | Approved architecture; exact versions are bootstrap assumptions pending lock resolution |
| Python tests | pytest `>=8.3,<9`, pytest-asyncio `>=0.25,<1` | Testing Constitution; exact tools are assumptions |
| Frontend tests | Node built-in test runner | Smallest deterministic foundation |
| Database | PostgreSQL 17 local image | PostgreSQL accepted by ADR-001/004; image major is a local bootstrap assumption |
| Migration/data tooling | Alembic `>=1.15,<2`, SQLAlchemy `>=2,<3`, psycopg `>=3.2,<4` | Approved database/ORM architecture |
| Python lint/format | Ruff `>=0.11,<1` | One tool for both responsibilities |
| Python type check | mypy `>=1.15,<2` | Type-safe requirement |
| Frontend lint/format | ESLint `9.35.0`, eslint-config-next `15.5.4`, Prettier `3.6.2` | Next.js-compatible bootstrap assumption |

`pyproject.toml` is the canonical Python dependency definition. No `uv.lock` was
fabricated.

## Repository structure

```text
.
├── apps/
│   ├── api/                 FastAPI composition root
│   └── web/                 Next.js status shell
├── services/
│   └── worker/              Separate idle worker
├── packages/
│   ├── core/                Modules and shared foundations
│   ├── contracts/           Versioned-contract registration point
│   ├── plugin_sdk/          First-party plugin SDK registration point
│   ├── provider_ports/      Vendor-neutral port registration point
│   └── provider_adapters/   Vendor-adapter registration point
├── departments/
│   ├── marketing/
│   ├── website/
│   └── operations/
├── db/
│   └── migrations/          Module-owned Alembic stream
├── tests/
│   ├── unit/
│   ├── integration/
│   └── architecture/
├── scripts/                 Dependency, migration, scope, secret, clean checks
├── docs/implementation/     Phase setup, rules, status, and this report
├── .github/workflows/ci.yml Validation only
├── compose.yaml             Optional local PostgreSQL
├── pyproject.toml           Python workspace and canonical dependencies
├── package.json             npm workspace
└── Makefile                 Command interface
```

## Commands

| Purpose | Command |
|---|---|
| Install | `make install` |
| Development API | `make dev-api` |
| Worker | `make dev-worker` |
| Frontend | `make dev-web` |
| Lint | `make lint` |
| Format | `make format` |
| Formatting check | `make format-check` |
| Type check | `make typecheck` |
| Unit tests | `make test-unit` |
| Integration tests | `make test-integration` |
| All tests | `make test` |
| Architecture tests | `make test-architecture` |
| Build | `make build` |
| Apply migrations | `make migrate` |
| Migration validation | `make migration-check` |
| Secret check | `make secret-check` |
| Full CI | `make ci` |
| Clean generated output | `make clean` |

## Boundary enforcement

`scripts/check_architecture.py` parses Python imports using the standard library.
It prevents module-internal imports, cross-Department imports, Department access
to concrete providers/Repository shortcuts, Tool-to-Adapter inversion, and
forbidden Executive, Planner, Reviewer, and Memory edges.

`scripts/check_phase1_scope.py` permits exactly three API routes and rejects
Temporal, Clerk, `pgvector`, Redis, or AI-provider dependencies. Migration checks
enforce declared ownership and require `workspace_id`, enabled/forced RLS, and
proof-gate compliance when future tables appear.

## Security foundation

- `.env` and generated environment variants are ignored; `.env.example` contains
  no secrets.
- Startup validation rejects malformed values and enabled dependencies without
  required configuration.
- JSON logging drops fields named password, secret, token, authorization, or
  credential.
- API requests receive request and correlation IDs.
- Database migrations require one owner. Tenant table rules are statically
  prepared; real RLS denial tests remain skipped until the first tenant table.
- PostgreSQL is optional locally and no production table exists.
- API scope checks prevent business endpoints and proof-gate SDKs.
- No Tool implementation, Provider Adapter, credential, outbound network call,
  external effect, arbitrary code execution, or business write exists.

## Proof-gate technologies

| Technology | Status | Evidence |
|---|---|---|
| Temporal | Not started | No dependency, adapter, engine, or workflow behavior |
| Clerk | Not started | No dependency or authentication flow |
| `pgvector` | Not started | Migration check rejects production vector use |

Redis is deferred and absent.

## Tests executed

| Command | Result | Failure/corrective action |
|---|---|---|
| Repository/document `find`, `rg`, tool/version inspection | PASS | Confirmed documentation-only starting state and no `AGENTS.md` |
| Official UV installer download to `/private/tmp` | Downloaded installer only | Installer payload download failed DNS; user directed no retry |
| UV installer in sandbox | FAIL | DNS unavailable for `releases.astral.sh`/GitHub |
| Escalated UV installer | ABORTED by user | Not retried; no repository artifact or lock fabricated |
| `python3 -m venv .venv` | PASS | Host isolated environment created with Python 3.8.2 |
| Initial `compileall` | FAIL due macOS sandbox bytecode cache location | Re-run with `PYTHONPYCACHEPREFIX=/private/tmp/rightjob-pycache` |
| `compileall` with temporary cache prefix | PASS | All Python source and tests parse |
| Shared utility assertion script | PASS | Configuration, bounds, Result, and log redaction validated |
| `python -m rightjob_worker.main --once` | PASS | Worker started, logged identity, and stopped safely |
| `scripts/check_architecture.py` | PASS | No prohibited dependency edge |
| `scripts/check_phase1_scope.py` | PASS | Only system routes; no proof-gate dependency |
| `scripts/check_migrations.py` | PASS | Migration foundation meets static rules |
| `scripts/check_secrets.py` | PASS | No committed environment file or obvious credential |
| Node built-in frontend shell test | PASS, 1 test | No dependency required |
| Final consolidated host validation | PASS | Python compile, architecture, scope, migration, secret, utilities, worker, Node test, and JSON manifests all returned zero |
| Online `npm install --package-lock-only --ignore-scripts` | ABORTED after DNS wait | No lockfile created |
| Offline npm lock attempt | FAIL `ENOTCACHED` | Required packages are not cached; no lock fabricated |
| API health pytest | NOT RUN | FastAPI/httpx/pytest unavailable on host |
| Full pytest suite | NOT RUN | Python dependency installation unavailable |
| Ruff, mypy, Alembic runtime | NOT RUN | Tools unavailable without dependency resolution |
| Next lint/type/build/start | NOT RUN | npm packages and lockfile unavailable |
| Docker PostgreSQL integration | NOT RUN | Docker unavailable on host |

## Deviations and conflicts

No architectural deviations were introduced.

Execution-environment conditions:

1. The host exposes Python 3.8.2 only; the project target is Python 3.11+.
2. UV is unavailable and cannot be downloaded because DNS/network access to its
   release hosts is unavailable.
3. npm dependencies are not cached and registry access is unavailable.
4. Docker is unavailable.
5. Consequently `uv.lock` and `package-lock.json` could not be generated or
   validated. Neither was fabricated.

These conditions do not change the approved stack. They must be closed in a
networked Python 3.11+ environment before this Phase is unconditionally passed.

## Phase-gate checklist

| Gate | Status | Evidence/condition |
|---|---|---|
| Repository installs from a clean checkout | FAIL | UV/npm lock generation blocked by environment |
| API starts | FAIL | FastAPI dependency unavailable; source compiles |
| Worker starts | PASS | Host lifecycle run completed |
| Frontend starts | FAIL | npm dependencies unavailable |
| Health endpoint responds | FAIL | Dependency-backed API test not runnable |
| Lint passes | FAIL | Ruff/ESLint unavailable |
| Type check passes | FAIL | mypy/TypeScript unavailable |
| Tests pass | FAIL | Host-runnable checks pass; full pytest/Next suite unavailable |
| Build passes | FAIL | UV/npm dependencies unavailable |
| Migration validation passes | PASS | Static migration check passed |
| Dependency-boundary checks pass | PASS | Architecture and Phase 1 scope passed |
| No required paid service is needed | PASS | Defaults disable all optional integrations |
| No business Capability was implemented | PASS | Placeholders and scope check only |
| No external effect was enabled | PASS | No Tool/Adapter implementation |
| No Constitution or ADR was modified | PASS | Architecture authority remains unchanged |

## Conditions to close

On a host with Python 3.11+, UV 0.12, Node 20.20.2+, npm registry access, and
optional Docker:

1. resolve dependencies and commit genuine `uv.lock` and `package-lock.json`;
2. run `make install`;
3. run `make ci`;
4. start API and verify `/health`, `/ready`, and `/version`;
5. start the frontend and idle worker;
6. record any corrective actions in this report.

No Phase 2 work is required to close these conditions.

## Final verdict

`PHASE 1 PASSED WITH CONDITIONS`

The repository foundation and host-runnable safety checks are complete. Clean
dependency installation and dependency-backed runtime/build validation remain
blocked by the execution environment, not by an architecture conflict.
