# Phase 2.10 Executive AI Planning Foundation Verification Report

**Date:** 2026-08-12
**Scope:** Provider-neutral source-only synthetic planning, deterministic validation, and compilation
**Status:** `PHASE 2.10 EXECUTIVE AI PLANNING FOUNDATION IMPLEMENTATION CANDIDATE PASSED`

## Ownership and architecture

The milestone name does not transfer Planning ownership to Executive. Executive remains unchanged
and owns conversation and presentation only. Planning owns decomposition and untrusted typed plan
proposals. Planning/application owns deterministic plan validation. Orchestration owns conversion
of a validated plan into an `ExecutionRequest`.

Department Registry remains authoritative for exact Department definitions. Capability Registry
remains authoritative for exact Capability definitions. Planner output is never authoritative and
cannot invoke Registry implementations, persistence, Orchestration services, workflow engines,
providers, Policy, approvals, Memory, or external effects.

## Planning contracts

Published immutable contracts include `PlanningRequest`, `PlanningContext`, `PlanningConstraints`,
`StructuredInput`, `SyntheticPlanningGoal`, `SyntheticStepObjective`, `PlannerIdentity`, `PlanStep`,
`ProposedPlan`, `ExecutionPlan`, and the provider-neutral `Planner` protocol.

`StructuredInput` stores a unique tuple of nonblank key/scalar pairs instead of a mutable nested
dictionary. It rejects secret-bearing keys and exposes deterministic encoded-size measurement.
Planning inputs are limited to 65,536 bytes and plans to at most 16 steps. All tenant, correlation,
request, plan, and step identities are non-nil; timestamps are timezone-aware. Planning actors are
limited to `USER` and `SYSTEM`, matching the Phase 2.7 execution boundary.

`ExecutionPlan` means only a deterministically validated in-memory plan. It does not mean durable,
authorized, approved, accepted for execution, or persisted.

## Deterministic planner

`SyntheticPlanner` implements the published Planner port with an injected ID factory and no random
default or hidden state. It supports exactly:

- `PREPARE` -> `foundation.operations@1.0.0` / `fake.prepare@1.0.0`;
- `TRANSFORM` -> `foundation.content@1.0.0` / `fake.transform@1.0.0`;
- `VERIFY` -> `foundation.operations@1.0.0` / `fake.verify@1.0.0`;
- `PREPARE_TRANSFORM_VERIFY` -> prepare, then transform, then verify.

The three-step proposal uses the exact dependency chain `prepare -> transform -> verify`. The fake
planner proposes exact references and metadata from bounded synthetic rules, but its output remains
untrusted and is independently re-resolved by the validator.

## Validation model

`PlanValidator` distinguishes the pipeline:

```text
Planner proposal
  -> deterministic validation
  -> validated in-memory ExecutionPlan
```

Validation fails closed unless all of the following hold:

- request, context, and proposal Workspace/correlation/causation provenance match;
- actor and constraints match between request and context;
- plan size and every structured step input are bounded;
- requested synthetic goal exactly matches the proposed objectives;
- step IDs are unique and sequences are contiguous;
- dependency IDs exist, do not reference self, are acyclic, and precede dependents;
- exact Department and Capability references were available in context;
- exact Department exists, is enabled, and its immutable ID matches;
- exact Capability exists, is enabled, and its immutable ID matches;
- Capability belongs to the selected Department;
- work category belongs to the selected Department;
- output contract equals canonical Capability metadata;
- effect classification equals canonical Capability metadata.

Unknown, disabled, mismatched, implicitly versioned, or cyclic proposals do not produce an
`ExecutionPlan`. Effect classification remains descriptive metadata only.

## Compiler boundary

The Orchestration-owned `ExecutionPlanCompiler` implements:

```text
validated in-memory ExecutionPlan
  -> exact compatible WorkflowDefinition validation
  -> ExecutionRequest
```

It verifies PlanningRequest provenance, exact enabled workflow shape, exact Department references,
exact Capability references, step types, step count, and workflow attempts. It propagates Workspace,
actor, correlation, causation, input, and deterministic plan step IDs into `ExecutionRequest`.

The source-only proof compiles the three-step plan against exact
`synthetic.sequence@1.0.0`. Individual one-step plans validate correctly but fail closed if compiled
against an incompatible workflow. No new workflow definition was invented.

The compiler never imports or invokes `OrchestrationApplicationService` or
`DurableWorkflowEngine`. No resulting `ExecutionRequest` was submitted, persisted, or launched.

## Future lifecycle boundary

Phase 2.10 stops here:

```text
proposal -> validation -> in-memory plan -> compilation -> ExecutionRequest
```

The following remains future work:

```text
persistence -> Policy -> approval when required -> execution
```

No `requires_policy_review` or equivalent field exists. Plan acceptance never implies authorization,
and future Policy must evaluate execution independently.

## Tenancy and persistence decision

Every planning object carries exact Workspace identity, and mismatches fail closed. Department and
Capability definitions remain global immutable reference data; Workspace activation is absent.

Source-only objects are sufficient because Phase 2.10 performs no durable acknowledgement,
approval, resume, recovery, or execution. Operationally accepted plans will require canonical
Orchestration-owned PostgreSQL persistence and a separately approved Workspace-scoped migration.
No planning table, repository, SQLAlchemy model, or migration was added.

With no persistent mutation, Phase 2.6 Audit/Outbox writes are not required. Future plan persistence
must atomically commit canonical state, Audit evidence, and an Outbox event without changing Phase
2.6 ownership.

## Provider, Policy, and runtime boundaries

No Executive behavior, prompt, AI SDK, provider selection, provider adapter, dynamic import,
executable content, Memory, Policy engine, approval engine, autonomous loop, worker change, API
route, Temporal type, external effect, or production Department/Capability was introduced.

## Files created

- `packages/core/src/rightjob/contracts/planning.py`
- `packages/core/src/rightjob/planner/synthetic.py`
- `packages/core/src/rightjob/planner/validation.py`
- `packages/core/src/rightjob/orchestration/application/plan_compiler.py`
- `tests/unit/test_planning.py`
- `docs/implementation/030-executive-ai-planning-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/planner/__init__.py`
- `packages/core/src/rightjob/orchestration/application/__init__.py`
- `docs/implementation/phase-status.md`

No architecture test modification was necessary because existing module-boundary enforcement and
the focused no-leakage source test cover the new dependency directions.

## Tests and quality gates

Tests cover all four goals, deterministic injected IDs, immutable and bounded contracts, secret-key
rejection, goal/proposal compatibility, unique IDs, missing dependencies, cycles, sequence rules,
unknown and disabled definitions, Department/Capability mismatch, category/output/effect drift,
context/provenance mismatch, exact workflow compilation, propagation, incompatible workflows, and
absence of provider/Temporal/Policy/dynamic execution.

| Gate | Result |
|---|---|
| Ruff format | PASS — 221 files conformant |
| Ruff lint | PASS |
| strict mypy | PASS — 97 source files |
| Focused Phase 2.8–2.10 tests | PASS — 41 passed |
| Full pytest with services stopped | PASS — 125 passed, 31 gated skips |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock verification | PASS — 51 packages, lock unchanged |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## PostgreSQL, Temporal, and migration status

- PostgreSQL remained stopped; no listener, socket, runtime marker, or process was present.
- Temporal remained stopped; no listener or process was present.
- API and worker remained stopped.
- No runtime verification was performed.
- Revision chain remains `20260806_0001 -> 20260811_0002 -> 20260811_0003`.
- Migration `20260812_0004` was not created.

## Risks and deferred work

- Source-only plans must never be represented as durable or accepted for execution.
- Historical planner, plan, Workflow, Department, and Capability versions must remain interpretable.
- Individual synthetic goals need separately reviewed compatible workflows before compilation.
- Operational plan persistence requires a separately approved Orchestration schema and
  Audit/Outbox transaction boundary.
- Policy, approvals, real providers, natural-language goals, Memory, planning revision loops,
  Workspace activation, production definitions, API composition, and execution are deferred.

## Verdict

`PHASE 2.10 EXECUTIVE AI PLANNING FOUNDATION IMPLEMENTATION CANDIDATE PASSED`
