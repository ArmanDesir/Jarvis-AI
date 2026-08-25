# Phase 2.14 Executive Application Composition Verification Report

**Date:** 2026-08-14
**Scope:** Source-only Executive composition over the published Planning boundary
**Status:** `PHASE 2.14 EXECUTIVE APPLICATION COMPOSITION & CONTROLLED AI PLANNING PATH IMPLEMENTATION CANDIDATE PASSED`

## Architecture and ownership

Executive remains a conversation and presentation owner. It constructs trusted bounded Planning
inputs, composes exact enabled Registry references into `PlanningContext`, calls a published
Planning application interface, verifies returned plan provenance, and converts the validated plan
to a presentation-safe result. It does not decompose work, construct prompts, resolve provider
responses, validate proposals, authorize, approve, persist, compile, or execute.

Planning owns the new `PlanningApplicationService`, which contains the existing
`Planner -> PlanValidator` handoff and normalizes Planning/provider failures before they cross the
published boundary. This small additional file is required to prevent Executive from importing
Planner implementations or `PlanValidator` directly.

The implemented path is:

```text
ExecutivePlanningRequest
  -> trusted PlanningRequest construction
  -> deterministic enabled-Registry PlanningContext
  -> published PlanningApplication
  -> injected Planner
  -> untrusted ProposedPlan
  -> existing PlanValidator
  -> validated in-memory ExecutionPlan
  -> provenance verification
  -> ExecutivePlanPresentation
  -> STOP
```

## Executive contracts

`rightjob.contracts.executive` publishes frozen, slotted contracts for:

- `ExecutivePlanningRequest`;
- `ExecutivePlanningOutcome` (`PLANNED`, `NOT_PLANNABLE`, `FAILED`);
- `ExecutivePlanningFailure`;
- `ExecutivePlanStep`;
- `ExecutivePlanPresentation`;
- `ExecutivePlanningResult`.

The request accepts only trusted Workspace, actor, correlation/causation, bounded synthetic goal,
Planning constraints, and immutable structured input. Nil IDs, unsupported actor types, and
oversized inputs fail before Planning.

The result contains no SDK response, prompt, credential, handler key, repository, ORM record,
Policy/Approval object, authorization, ExecutionRequest, Temporal handle, or executable content.
Effect classification remains descriptive presentation metadata and grants no authority.

## Planning application boundary

The published `PlanningApplication` protocol accepts exact `PlanningRequest` and `PlanningContext`
and returns only a deterministically validated in-memory `ExecutionPlan`.
`PlanningApplicationService` injects any `Planner` implementation and the existing `PlanValidator`.

Provider and validation failures become bounded `PlanningApplicationError` values with these
categories:

- proposal rejected;
- transient provider failure;
- provider configuration failure;
- provider-rejected output;
- invalid provider output.

Executive maps them to presentation-only outcomes without exposing raw provider payloads, SDK
exceptions, credentials, stack traces, or infrastructure details.

## Trusted request and context construction

`ExecutivePlanningService` uses injected ID and clock factories to create `planning_request_id` and
`created_at`. Workspace, actor, correlation, causation, goal, constraints, and input come only from
the validated Executive request. Provider/model output has no path to those fields.

The service depends only on published `CapabilityCatalog` and `DepartmentCatalog` protocols. It
calls `list_enabled()`, sorts exact definitions deterministically by key/version, and places only
their immutable references into `PlanningContext`. Executive imports no Registry implementation.

The service verifies that the returned validated plan preserves Workspace, planning-request ID,
correlation, and causation before presenting it. A mismatched plan fails closed as `NOT_PLANNABLE`.

## Planner injection proofs

The deterministic proof wires:

```text
ExecutivePlanningService
  -> PlanningApplicationService
  -> SyntheticPlanner
  -> PlanValidator
```

The AI-backed proof wires outside Executive:

```text
ExecutivePlanningService
  -> PlanningApplicationService
  -> ProviderBackedPlanner
  -> FakeAIProvider
  -> untrusted AIPlanProposal
  -> Registry enrichment
  -> PlanValidator
```

Both produce the same bounded three-step `prepare -> transform -> verify` presentation path.
Executive cannot observe or select the concrete Planner/provider implementation.

## Identity and provenance

Tests prove preservation of:

- trusted Workspace ID;
- trusted `USER` actor and actor ID;
- correlation ID;
- causation ID;
- generated PlanningRequest identity;
- trusted Planner-generated plan and step IDs.

The fake provider schema cannot carry Workspace, actor, correlation, causation, request, plan, or
step UUIDs. No membership, permission, role, approval, or authorization inference occurs.

With identical trusted request, Registry snapshot, injected ID sequences, injected clock, and fake
provider response, the validated presentation result is identical. No claim is made that a future
real model response is deterministic.

## Presentation and clarification behavior

`ExecutivePlanPresentation` exposes plan/request identity, trusted provenance, planner reference,
ordered objectives, exact Department and Capability references, dependencies, structured input,
and descriptive effects. It does not expose provider output or executable handlers.

No clarification engine was needed. Phase 2.14 accepts the existing closed
`SyntheticPlanningGoal`; malformed and unsupported inputs fail deterministically before planning.
There is no recursive provider call, retry, revision, reflection, or autonomous loop.

## Architecture enforcement

Executive source imports only its own module and published contracts. Architecture checks continue
to prohibit Executive imports of Planner internals, Registry implementation, provider adapters,
OpenAI, Policy, Orchestration, tools, repositories, SQLAlchemy, and Temporal. General module rules
prohibit Planning from importing Executive and provider adapters from importing Executive or
Planning internals. The Phase 2.13 SDK-isolation gate remains unchanged.

No circular dependency was introduced:

```text
Executive implementation -> published contracts <- Planning implementation
```

## Complete file inventory

Created:

- `packages/core/src/rightjob/contracts/executive.py`
- `packages/core/src/rightjob/executive/application.py`
- `packages/core/src/rightjob/planner/application.py`
- `tests/unit/test_executive_planning.py`
- `docs/implementation/034-executive-application-composition-verification-report.md`

Modified:

- `packages/core/src/rightjob/contracts/planning.py`
- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/executive/__init__.py`
- `packages/core/src/rightjob/planner/__init__.py`
- `scripts/check_architecture.py`
- `tests/architecture/test_boundaries.py`
- `docs/implementation/phase-status.md`

No provider adapter, Policy, Approval, authorization, Orchestration, database, migration, API,
worker, or Temporal production file changed in Phase 2.14.

## Verification

| Gate | Result |
|---|---|
| Ruff format | PASS — 250 files |
| Ruff lint | PASS |
| strict mypy | PASS — 115 source files |
| Focused Phase 2.10–2.14 tests | PASS — 75 passed |
| Executive composition tests | PASS — 9 passed |
| Full pytest with runtime integrations gated | PASS — 186 passed, 46 skipped |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages, unchanged |
| `git diff --check` | PASS |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Runtime and non-invocation confirmation

- PostgreSQL remained stopped; port `55416` and its Unix socket were absent.
- Temporal remained stopped; no listener on `7233` appeared.
- API and worker were not started; no listener on `8000` appeared.
- No database mutation or Alembic operation occurred.
- No migration was created or modified; head remains `20260812_0004`.
- No live OpenAI/provider call or real credential was used.
- No Policy evaluation, GovernanceRecorder, Approval request/decision, or durable authorization was
  invoked.
- No `ExecutionPlanCompiler`, `ExecutionRequest`, execution record, Orchestration service,
  Capability, tool, DurableWorkflowEngine, or Temporal workflow was invoked.

## Deferred work and risks

- Natural-language classification and clarification require a separate bounded design; Phase 2.14
  supports only the accepted synthetic goal enum.
- A future API route must resolve authenticated Workspace/actor context and call only this published
  Executive boundary; no route is added here.
- Live-provider smoke testing, durable provider observability, Memory/RAG, provider routing,
  fallback, retries, Policy/Approval continuation, execution submission, tools, and autonomous loops
  remain deferred.
- Executive catches unexpected boundary failures as a bounded internal presentation failure. Such a
  result grants no authority; operational logging remains a future composition concern and must not
  expose secrets.
- `ExecutionPlan` remains an in-memory validated plan, not authorization or permission to execute.

## Recommendation

`PHASE 2.14 EXECUTIVE APPLICATION COMPOSITION & CONTROLLED AI PLANNING PATH IMPLEMENTATION CANDIDATE PASSED`
