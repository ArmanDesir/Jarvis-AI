# Phase 2.15 Natural-Language Intent & Clarification Verification Report

**Date:** 2026-08-14
**Scope:** Source-only bounded Executive natural-language intake
**Status:** `PHASE 2.15 NATURAL-LANGUAGE INTENT, CLARIFICATION & PLANNING INTAKE FOUNDATION PASSED`

## Implemented path and ownership

Executive now owns one bounded intent-classification interaction and its presentation outcomes.
It reuses the Phase 2.13 `AIProvider` contract and delegates planning-ready results to the existing
Phase 2.14 `ExecutivePlanningFacade`. Planning still owns decomposition, Registry composition and
validation; no planning logic moved into Executive.

```text
trusted context + untrusted natural-language message
  -> ExecutiveIntakeService
  -> one provider-neutral structured intent request
  -> untrusted ExecutiveIntent
  -> PLANNING_READY: existing ExecutivePlanningService -> validated plan presentation -> STOP
  -> CLARIFICATION_REQUIRED: bounded clarification -> STOP
  -> UNSUPPORTED: bounded reason -> STOP
  -> FAILED: normalized failure -> STOP
```

The path cannot invoke Policy, Approval, durable authorization, Orchestration, Capability handlers,
Temporal, tools, repositories, or persistence.

## Contracts and bounds

`rightjob.contracts.executive_intake` publishes frozen, slotted contracts for the intake request,
closed intent, clarification, result, outcomes, reasons, failures, and the narrow Phase 2.14 facade
protocol. Trusted context is structurally separate from the user message.

- The message is whitespace-normalized, nonempty, and limited to **16,384 UTF-8 bytes** before any
  provider call. This reserves most of the Phase 2.13 65,536-byte request envelope for trusted
  prompt/schema material.
- Clarification text is limited to 500 characters.
- Clarification contains one to eight unique canonical missing-field identifiers, each at most 64
  characters.
- Intent schema version is exactly `1`.
- Planning goals remain the existing four-value `SyntheticPlanningGoal`; Planning contracts were
  not broadened.
- Planning input remains immutable `StructuredInput`, including its secret-key rejection.
- Intent output has no Workspace, actor, membership, role, authorization, approval, workflow,
  execution, handler, tool, credential, or canonical-ID field.

Exactly one result payload is permitted: plan, clarification, unsupported reason, or normalized
failure. Clarification and unsupported branches make no Planning call. Failed provider/schema
branches also make no Planning call.

## Prompt, schema, and provider boundary

Executive owns a separate code-controlled intent prompt:

- prompt: `executive.intent-classification@1.0.0`;
- schema: `executive.intent-result@1.0.0`.

The prompt and JSON schema are immutable, source-controlled, deterministic, and distinct from the
Planning decomposition prompt. User text is JSON-encoded as untrusted data. The intent request uses
the existing `EXECUTIVE_PLANNING` logical model because Phase 2.15 requires no model routing or
different provider configuration. It uses one invocation, a 30-second timeout, 512 maximum output
tokens, no retries in this service, and the existing Phase 2.13 request/response limits.

No Registry snapshot is sent for intent classification: the closed planning-goal enum is sufficient
for this phase, and Registry truth remains resolved only by the controlled Planning continuation.
All tests use `FakeAIProvider`; no OpenAI adapter or SDK is imported by Executive and no network
request is possible in the tests.

Malformed JSON, unknown/additional fields, invalid branch shapes, refusal, truncation, mismatched
provider provenance, transient failures, and configuration failures map to bounded failures. No raw
provider response, exception object, stack trace, SDK type, or secret enters the published result.

## Trusted identity and continuation

The application injects a trusted intake request ID and aware timestamp. Workspace, actor,
correlation, and causation come only from validated application input and are copied unchanged into
the result and Phase 2.14 request. The structured model schema cannot express replacements.

For `PLANNING_READY`, the service constructs an `ExecutivePlanningRequest` from the trusted context
plus the closed goal and bounded structured input, then calls the existing façade exactly once.
That façade continues through trusted Registry context construction, Planning, the injected Planner,
and `PlanValidator`, producing only a validated in-memory presentation. Planning rejection becomes
unsupported; normalized Planning infrastructure failures remain bounded failures.

Tests pass adversarial text asking the model to change Workspace, become administrator, approve,
bypass Policy, invoke a Capability, create an ExecutionRequest, launch Temporal, reveal secrets,
use tools, and change provider configuration. It remains ordinary message data; trusted provenance
is unchanged and no authority-bearing field exists.

## Clarification and stop behavior

Clarification is one finite presentation result with a bounded question, canonical missing fields,
and reason code. There is no second provider call, recursive conversation, persistence, Memory,
reflection, retry loop, or autonomous follow-up. A caller may submit a future independent request.

Unsupported and failed outcomes likewise stop immediately. Natural language never becomes
authorization or execution authority.

## File inventory

Created:

- `packages/core/src/rightjob/contracts/executive_intake.py`
- `packages/core/src/rightjob/executive/intake.py`
- `tests/unit/test_executive_intake.py`
- `docs/implementation/035-natural-language-intent-clarification-foundation-verification-report.md`

Modified:

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/executive/__init__.py`
- `scripts/check_architecture.py`
- `docs/implementation/phase-status.md`

No Planning, provider-adapter, Policy, Approval, Orchestration, database, migration, Temporal, API,
worker, dependency, configuration, or lock file changed for Phase 2.15.

## Architecture enforcement

Executive remains limited to its own package and published contracts. The architecture checker now
also rejects `importlib` and `subprocess` imports in Executive and applies its dynamic
`eval`/`exec`/`compile`/`__import__` prohibition to Executive AI paths. Existing bans on OpenAI,
provider adapters, Planner/Registry internals, Policy, Orchestration, repositories, SQLAlchemy,
Temporal, and tools remain active. Planning and provider adapters cannot import Executive internals.

## Verification evidence

| Gate | Result |
|---|---|
| Ruff format | PASS |
| Ruff lint | PASS |
| strict mypy | PASS — 98 source files |
| Focused Phase 2.13–2.15 and architecture tests | PASS — 46 passed |
| Executive intake tests | PASS — 12 passed |
| Full pytest with runtime integrations gated | PASS — 198 passed, 46 skipped |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — unchanged |
| `git diff --check` | PASS |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Runtime and authority confirmation

- PostgreSQL remained stopped; no database mutation or Alembic command occurred.
- Migration head remains `20260812_0004`; no migration was created or changed.
- Temporal, API, and worker remained stopped.
- No live provider call or API key was used.
- No Policy evaluation, Approval action, authorization issuance, Audit/Outbox mutation, or
  persistence occurred.
- No compiler, Orchestration service, ExecutionRequest, Capability handler, tool, execution record,
  or Temporal workflow was invoked.

## Deferred work and risks

- Caller-managed follow-up after clarification, conversation persistence, Memory/RAG, model routing,
  fallback, retries, and live-provider smoke testing remain deferred.
- The closed synthetic goal vocabulary intentionally limits natural-language planning coverage. A
  future expansion needs an explicitly approved bounded Planning contract; arbitrary free-form
  model-controlled goals remain prohibited.
- A future API must supply authenticated Workspace/actor context and must not derive it from message
  text.
- AI classification remains nondeterministic. Deterministic schema validation, trusted-context
  injection, the Phase 2.14 boundary, Registry resolution, and `PlanValidator` own acceptance.

## Recommendation

`PHASE 2.15 NATURAL-LANGUAGE INTENT, CLARIFICATION & PLANNING INTAKE FOUNDATION PASSED`
