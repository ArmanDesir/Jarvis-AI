# Phase 2.8 Capability Registry Foundation Verification Report

**Date:** 2026-08-12
**Scope:** Global immutable code-owned synthetic Capability Registry
**Status:** `PHASE 2.8 CAPABILITY REGISTRY FOUNDATION PASSED`

## Architecture summary

Phase 2.8 establishes provider-neutral published capability contracts, an immutable built-in
catalog, explicit code-owned handler resolution, and exact capability-version validation during
Orchestration compilation. Registry owns definition identity, discovery, enablement metadata, and
handler keys. Orchestration continues owning workflow definitions, compilation, sequencing, and
canonical execution state.

No Executive AI, Department runtime, Policy, Workspace activation, provider integration, real
effect, API, repository, SQLAlchemy capability model, PostgreSQL table, migration, worker change,
or Temporal change was introduced.

## Capability model

`CapabilityDefinition` and `CapabilityReference` are frozen value contracts. A definition contains
an immutable UUID, canonical key, parsed semantic version, synthetic owner key, bounded descriptive
metadata, enabled state, exact input/output contract references, stable handler key, effect and
idempotency classifications, and bounded timeout/retry metadata.

`ContractReference` identifies an exact contract key/version and limits encoded payloads to at most
65,536 bytes. The three built-ins use a 4,096-byte bound. Definitions cannot contain credentials,
provider identifiers, Temporal identifiers, prompts, arbitrary code, or executable import paths.

Exactly three built-in capabilities exist:

| Capability | Definition ID | Version | Handler |
|---|---|---|---|
| `fake.prepare` | `02800000-0000-4000-8000-000000000001` | `1.0.0` | `fake.prepare.v1` |
| `fake.transform` | `02800000-0000-4000-8000-000000000002` | `1.0.0` | `fake.transform.v1` |
| `fake.verify` | `02800000-0000-4000-8000-000000000003` | `1.0.0` | `fake.verify.v1` |

`fake.wait_for_signal` remains an Orchestration control/wait step, not a Capability.

## Versioning and lookup

`SemanticVersion` validates semantic-version syntax, retains prerelease/build identifiers, and
provides deterministic precedence. The immutable Registry rejects duplicate definition IDs and
duplicate key/version pairs.

Discovery supports exact lookup, enabled exact lookup, explicitly requested latest-enabled lookup,
stable enabled listing, and stable owner filtering. Unknown versions and disabled definitions fail
closed. Persisted executions never use latest lookup.

## Handler resolution

`CapabilityHandlerResolver` copies an explicitly supplied mapping into a read-only mapping proxy.
It resolves only the definition's stable handler key and rejects missing handlers. There is no
`importlib`, `eval`, entry-point discovery, filesystem loading, database content, user-defined code,
or dynamic plugin installation.

## Effect, idempotency, retry, and timeout models

Effect metadata supports `read_only`, `reversible`, `consequential`, and `external_effect`; it is
descriptive only and grants no Policy authorization. Executable built-ins remain synthetic and
produce no external effects.

Idempotency metadata supports `naturally_idempotent`, `requires_idempotency_key`, and
`non_idempotent`. Retry metadata bounds attempts from 1 through 10 and declares normalized
retryable failure categories. Timeout metadata bounds application timeouts from 1 through 3,600
seconds. No Temporal retry or activity type leaks into these contracts.

## Orchestration integration

The published `CapabilityCatalog` protocol is the only Registry contract required by the compiler.
Immutable built-in workflow step definitions pin exact `CapabilityReference` values for
`fake.prepare`, `fake.transform`, and `fake.verify`. The compiler resolves each exact enabled
definition and rejects identity, key, version, enablement, or step-type drift.

ExecutionStep persistence remains unchanged. Canonical executions pin an immutable
`workflow_definition_id + workflow_version`; that immutable workflow definition transitively pins
exact capability definition IDs and versions. The DurableWorkflowEngine boundary and worker runtime
are unchanged.

## SQLAlchemy architecture-boundary correction

Source verification detected that the accepted Phase 2.7 shared-metadata fix had introduced an
invalid Orchestration-infrastructure import of Identity's `WorkspaceRecord`. Owner approval
classified this as `PRODUCTION ARCHITECTURE BOUNDARY DEFECT — PHASE 2.8 NOT YET FAILED`.

The correction adds `rightjob.database` as the database composition root. It registers the
Identity-, Audit-, and Orchestration-owned mappings on the existing shared Base. Orchestration again
uses string Workspace foreign-key references and imports no Identity infrastructure. Alembic obtains
the same shared metadata through this composition root. No schema or migration changed.

The approved Phase 2.7 PostgreSQL regression passed all seven tests, including the real first
`Session.flush()`, atomic canonical/Audit/Outbox persistence, rollback, uniqueness, concurrency,
cancellation, reconciliation, RLS, Workspace isolation, append-only Audit privileges, and Outbox
idempotency.

## Tenancy decision

Definitions are global immutable platform reference data. No Workspace capability table,
activation record, override, join, RLS policy, or tenant-specific definition exists. Workspace-level
activation remains deferred pending its own Registry, tenancy, and Policy review.

## Files created

- `packages/core/src/rightjob/contracts/capabilities.py`
- `packages/core/src/rightjob/registry/catalog.py`
- `packages/core/src/rightjob/registry/handlers.py`
- `packages/core/src/rightjob/database.py`
- `tests/unit/test_capability_registry.py`
- `docs/implementation/028-capability-registry-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/registry/__init__.py`
- `packages/core/src/rightjob/orchestration/application/registry.py`
- `packages/core/src/rightjob/orchestration/application/compiler.py`
- `packages/core/src/rightjob/orchestration/infrastructure/models.py`
- `db/migrations/env.py`
- `tests/unit/test_execution_orchestration.py`
- `tests/integration/test_execution_orchestration_transactions.py`
- `docs/implementation/phase-status.md`

The integration harness change registers mappings through the approved composition root and applies
Ruff-only formatting; its behavioral assertions and fixtures are unchanged.

## Verification

| Gate | Result |
|---|---|
| Ruff format | PASS — 210 files conformant |
| Ruff lint | PASS |
| strict mypy | PASS — 90 source files |
| Focused Phase 2.7/2.8 source tests | PASS — 31 passed |
| Full pytest with services stopped | PASS — 106 passed, 31 gated skips |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock verification | PASS — 51 packages, lock unchanged |
| Phase 2.7 PostgreSQL behavioral regression | PASS — 7 passed |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

Post-regression cleanup confirmed revision `20260811_0003`, all eight application tables empty,
all approved fixture IDs absent, verifier role/grants absent, 63 constraints, 30 indexes, six
policies, all expected restrictive foreign keys, and forced RLS on all three execution tables.
PostgreSQL then stopped cleanly; port `55416`, the Unix socket, and PostgreSQL/pytest/psql/pg_ctl
processes were absent. Temporal remained stopped throughout.

## Risks and deferred work

- Historical built-in workflow and capability definitions must remain available while referenced.
- Direct independently queryable per-step capability persistence would require a future reviewed
  schema change; Phase 2.8 needs none because pinning is transitive through immutable workflow
  definitions.
- Workspace activation, real Department ownership, Capability invocation/result envelopes, Policy,
  approval, credentials, providers, external effects, and runtime handler composition are deferred.
- Effect classification is metadata and must never be treated as authorization.

## Explicit runtime and migration determination

- PostgreSQL remained stopped during Phase 2.8 source implementation and gates. It was started only
  for the separately approved Phase 2.7 metadata-composition regression, then cleaned and stopped.
- Temporal remained stopped and no Temporal runtime verification was required.
- No migration was created or modified.
- No Phase 2.8 PostgreSQL persistence or runtime verification is required.
- Phase 2.9 has not begun.

## Final verdict

`PHASE 2.8 CAPABILITY REGISTRY FOUNDATION PASSED`
