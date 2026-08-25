# Phase 2.9 Department Runtime Foundation Verification Report

**Date:** 2026-08-12
**Scope:** Global immutable code-owned synthetic Department metadata and routing
**Status:** `PHASE 2.9 DEPARTMENT RUNTIME FOUNDATION IMPLEMENTATION CANDIDATE PASSED`

## Architecture summary

Phase 2.9 establishes published provider-neutral Department contracts, an immutable built-in
Department Registry, deterministic routing from structured metadata, and exact Department-version
validation during Orchestration compilation. Departments group approved exact Capability
references under explicit ownership metadata; they do not execute work or behave as agents.

Capability Registry remains authoritative for Capability definitions and handlers. Orchestration
remains authoritative for workflow definitions, compilation, sequencing, and canonical execution
state. Department Registry owns only Department identity, discovery, grouping, work-category
metadata, and enabled state.

No Executive AI, Policy, prompt, provider, external effect, API route, repository, SQLAlchemy model,
PostgreSQL table, migration, worker change, or Temporal change was introduced.

## Department definition model

`DepartmentDefinition` and `DepartmentReference` are frozen, slotted value contracts. An immutable
definition contains:

- non-nil `department_definition_id`;
- canonical `department_key`;
- exact `SemanticVersion`;
- bounded nonblank display name and description;
- enabled metadata;
- bounded `DepartmentRole` classification;
- unique exact `CapabilityReference` values;
- unique bounded `WorkCategory` values.

`DepartmentRole` currently contains only `FOUNDATION`. It is classification metadata only and is
not consulted by routing, authorization, compilation decisions, or execution.

Exactly two built-in synthetic Departments exist:

| Department | Definition ID | Version | Role | Capabilities | Work categories |
|---|---|---|---|---|---|
| `foundation.operations` | `02900000-0000-4000-8000-000000000001` | `1.0.0` | `foundation` | `fake.prepare@1.0.0`, `fake.verify@1.0.0` | `prepare`, `verify` |
| `foundation.content` | `02900000-0000-4000-8000-000000000002` | `1.0.0` | `foundation` | `fake.transform@1.0.0` | `transform` |

No production Department or business Capability was added.

## Registry and versioning model

The immutable Registry validates all definitions at construction and rejects duplicate definition
IDs, duplicate key/version pairs, unresolved Capability identities, and duplicate active Department
ownership of one exact Capability reference.

Discovery supports exact lookup, enabled exact lookup, explicitly requested latest-enabled lookup,
stable enabled listing, exact Capability filtering, and bounded work-category filtering. Unknown or
disabled exact definitions fail closed. Latest-enabled lookup is discovery-only; workflow
definitions always pin exact Department versions.

Disabled historical definitions may remain discoverable by exact identity so immutable historical
references can continue to be interpreted. Disabled definitions are excluded from new routing and
enabled discovery.

## Capability relationship

The relationship is:

```text
DepartmentDefinition
  -> exact CapabilityReference
  -> published CapabilityCatalog
  -> immutable CapabilityDefinition
```

Registry construction resolves each assigned exact Capability through the published
`CapabilityCatalog`. Departments do not redefine Capability contracts, resolve handlers, execute
Capabilities, or reinterpret effect/idempotency/retry metadata.

The existing synthetic Capability `owner_key` remains `synthetic.foundation`; accepted Phase 2.8
definitions were not mutated. Department membership is the Phase 2.9 grouping boundary. A future
production ownership taxonomy must be approved before real Departments and Capabilities are added.

## Routing and work categories

`WorkCategory` is a bounded enum containing `PREPARE`, `TRANSFORM`, and `VERIFY`.
`DepartmentRouteRequest` accepts only structured criteria:

- optional exact work category;
- zero or more unique exact Capability references;
- optional exact Department reference.

The router intersects these criteria over enabled definitions. It returns exactly one pinned
`DepartmentReference`, otherwise it raises explicit not-found or ambiguity errors. An exact
Department must match immutable identity and all supplied criteria.

Department role is deliberately absent from routing logic. The router performs no natural-language
classification, AI inference, Policy decision, provider selection, execution, or mutation.

## Orchestration integration

Immutable `WorkflowStepDefinition` now pairs each synthetic Capability step with one exact
`DepartmentReference`. The compiler resolves the exact enabled Department, verifies immutable
Department identity, and confirms that the exact Capability belongs to that Department.

The relationship is transitively pinned:

```text
WorkflowDefinition
  -> WorkflowStepDefinition
  -> exact DepartmentReference
  -> exact CapabilityReference
```

`fake.wait_for_signal` remains an Orchestration control step with neither a Department nor a
Capability. Execution request/run/step persistence and the DurableWorkflowEngine representation
remain unchanged. No Temporal type entered published, application, or domain contracts.

## Tenancy decision

Department definitions are global immutable platform reference data. Phase 2.9 introduces no
Workspace activation, tenant override, join table, registration record, or RLS policy. Future
Workspace activation requires a separate ownership, tenancy, Policy, and persistence review.

## Files created

- `packages/core/src/rightjob/contracts/departments.py`
- `packages/core/src/rightjob/registry/departments.py`
- `packages/core/src/rightjob/registry/routing.py`
- `tests/unit/test_department_registry.py`
- `docs/implementation/029-department-runtime-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/registry/__init__.py`
- `packages/core/src/rightjob/orchestration/application/registry.py`
- `packages/core/src/rightjob/orchestration/application/compiler.py`
- `tests/unit/test_capability_registry.py`
- `tests/unit/test_execution_orchestration.py`
- `docs/implementation/phase-status.md`

## Test coverage

Source tests cover immutable identity, bounded validation, role/category metadata, duplicate
definition rejection, exact and enabled lookups, explicit latest lookup, stable listing, exact
Capability discovery, work-category filtering, unresolved and duplicate Capability ownership,
disabled definitions, structured routing, ambiguity, not-found behavior, exact Department pinning,
workflow integration, compiler membership validation, and absence of dynamic/AI/provider/Temporal
behavior.

## Quality gates

| Gate | Result |
|---|---|
| Ruff format | PASS — 215 files conformant |
| Ruff lint | PASS |
| strict mypy | PASS — 93 source files |
| Focused Phase 2.7–2.9 source tests | PASS — 29 passed |
| Full pytest with services stopped | PASS — 113 passed, 31 gated skips |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock verification | PASS — 51 packages, lock unchanged |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Migration and runtime determination

- No migration was created or modified for Phase 2.9.
- No Department persistence is required.
- PostgreSQL remained stopped and no PostgreSQL verification is required.
- Temporal remained stopped and no Temporal verification is required.
- No API or worker runtime verification is required.

Future independently queryable Department persistence, Workspace activation, or canonical
execution-level Department columns may require a separately reviewed migration. None is required by
the accepted transitive immutable-definition model.

## Risks and deferred work

- Historical Department, Capability, and Workflow definitions must remain available while
  referenced.
- Latest-enabled discovery must never replace exact version pinning in persisted workflows.
- Category-only routing may become ambiguous as definitions expand; ambiguity must continue to fail
  closed.
- Department role and membership are metadata, not authorization.
- Production owner-key taxonomy, real Departments, Workspace activation, Policy, approvals,
  Executive AI, capability invocation, provider credentials, external effects, and Department
  persistence are deferred.

## Verdict

`PHASE 2.9 DEPARTMENT RUNTIME FOUNDATION IMPLEMENTATION CANDIDATE PASSED`
