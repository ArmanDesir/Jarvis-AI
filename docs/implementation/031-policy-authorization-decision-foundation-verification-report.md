# Phase 2.11 Policy & Authorization Decision Foundation Verification Report

**Date:** 2026-08-13
**Scope:** Provider-neutral source-only deterministic Policy decisions
**Status:** `PHASE 2.11 POLICY & AUTHORIZATION DECISION FOUNDATION IMPLEMENTATION CANDIDATE PASSED`

## Ownership boundaries

Identity/Tenancy remains canonical for Workspace, User, Membership, authentication, roles,
permissions, and membership status. Policy consumes immutable resolved `MembershipFacts`; it does
not query Identity or import Identity application, domain, repository, ORM, or infrastructure code.

Policy owns deterministic authorization decisions and approval requirements. Planning continues to
own proposals and plan validation. Department and Capability Registries remain authoritative for
definitions and effect metadata. Orchestration remains the future enforcement and execution owner.
Future Approval owns exact durable human decisions. Audit/Observability retains audit acceptance and
append-only evidence storage. Temporal owns no authorization semantics.

## Published contracts

Phase 2.11 publishes immutable contracts for:

- `MembershipFacts` and `PolicySubject`;
- the single bounded `PolicyOperation.EXECUTE_CAPABILITY`;
- `PolicyAction` and deterministic-provenance-only `PolicyContext`;
- closed `PolicyDecision` outcomes `ALLOW`, `DENY`, and `REQUIRE_APPROVAL`;
- stable `PolicyReasonCode` values;
- exact `PolicySetReference` and `PolicyRuleReference` values;
- in-memory `PolicyEvaluation`;
- normalized `PolicyEvaluationError`;
- provider-neutral `PolicyEvaluator` protocol.

IDs are non-nil. Role and permission identifiers are unique, canonical, and bounded. Subject and
membership Workspaces must match. Policy evaluation timestamps are timezone-aware and use an
injected clock. `PolicyEvaluation` is time-bounded to five minutes in this synthetic proof.

`PolicyEvaluation is not durable authorization evidence and cannot authorize execution.`

## Policy set identity and deterministic rules

Exactly one code-owned policy set exists:

| Policy set | ID | Version |
|---|---|---|
| `synthetic.foundation.policy` | `03100000-0000-4000-8000-000000000001` | `1.0.0` |

Its exact ordered rule references are:

1. `synthetic.validate_action@1.0.0`;
2. `synthetic.authorize_subject@1.0.0`;
3. `synthetic.classify_effect@1.0.0`.

There is no latest-policy lookup, dynamic rule loading, database content, executable policy text,
or implicit fallback.

## Decision and reason semantics

The deterministic synthetic outcomes are:

| Trusted facts | Decision | Reason code |
|---|---|---|
| Active supported user membership and `READ_ONLY`/`REVERSIBLE` Capability | `ALLOW` | `SYNTHETIC_NONCONSEQUENTIAL_ALLOWED` |
| Active supported user membership and `CONSEQUENTIAL`/`EXTERNAL_EFFECT` Capability | `REQUIRE_APPROVAL` | `APPROVAL_REQUIRED_FOR_EFFECT` |
| Missing, inactive, mismatched-user, or unsupported subject facts | `DENY` | `SUBJECT_NOT_AUTHORIZED` |

`REQUIRE_APPROVAL` means only that sufficient future human approval is required. It does not mean
approval exists and contains no approver or approval state.

Malformed, unknown, disabled, stale, inconsistent, or cross-Workspace inputs raise
`PolicyEvaluationError`; they are never silently allowed or converted into a fabricated business
decision.

## Registry revalidation

`SyntheticPolicyEvaluator` receives only the published `CapabilityCatalog` and `DepartmentCatalog`
contracts. For every action it independently:

1. validates Workspace and plan provenance;
2. resolves the exact enabled Department;
3. resolves the exact enabled Capability;
4. verifies immutable definition identities;
5. verifies Capability ownership by Department;
6. verifies WorkCategory membership;
7. verifies exact canonical EffectClassification;
8. evaluates subject facts;
9. applies the synthetic effect rule.

Planner and PlanStep metadata is therefore proposed input, never policy authority. Capabilities and
handlers cannot authorize themselves.

## PlanStep and aggregate evaluation

`PlanPolicyEvaluator` validates PlanningRequest, ExecutionPlan, PolicySubject, and PolicyContext
provenance across Workspace, planning request, plan, correlation, and causation identifiers. Every
PlanStep becomes one bounded `PolicyAction` and receives an independent `PolicyEvaluation`.

The aggregate preserves all exact step decisions and derives one result using:

```text
DENY > REQUIRE_APPROVAL > ALLOW
```

Tests prove all-allow, approval-required, all-deny, and mixed
`ALLOW + REQUIRE_APPROVAL + DENY -> DENY` behavior. Aggregation cannot weaken any step decision.

## Approval and execution-enforcement boundaries

Phase 2.11 stops at an in-memory Policy evaluation:

```text
validated in-memory ExecutionPlan
  -> deterministic step Policy evaluations
  -> in-memory aggregate Policy result
```

Future lifecycle work is deliberately absent:

```text
durable Policy evidence
  -> durable human Approval when required
  -> Orchestration verifies exact evidence
  -> execution
```

The Phase 2.10 compiler, `OrchestrationApplicationService`, `ExecutionRequest`, and
`DurableWorkflowEngine` were not modified or called. No Policy result can reach compilation,
persistence, workflow launch, Capability execution, or an external effect.

## Tenancy, persistence, and Audit/Outbox

Workspace is the sole tenant boundary. Nil IDs, subject/membership mismatch, subject/context
mismatch, plan/context mismatch, and planning provenance mismatch fail closed. Department,
Capability, and Policy definitions remain global immutable reference data.

No Policy, authorization, or approval table, repository, Unit of Work, SQLAlchemy mapping, RLS
policy, or migration was introduced. Source-only evaluation is sufficient to prove decision
semantics because no decision is consumed operationally.

No Audit/Outbox mutation is required without a durable Policy transition. Future execution-enabling
Policy evidence must be persisted with truthful Audit evidence and an Outbox event in one
Policy-owned PostgreSQL transaction, subject to separate owner approval.

## Files created

- `packages/core/src/rightjob/contracts/policy.py`
- `packages/core/src/rightjob/policy/evaluator.py`
- `packages/core/src/rightjob/policy/plan_evaluation.py`
- `tests/unit/test_policy.py`
- `docs/implementation/031-policy-authorization-decision-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/policy/__init__.py`
- `docs/implementation/phase-status.md`

Architecture tests required no modification. Existing module-boundary enforcement plus focused
source-leakage tests cover the new dependency direction.

## Test coverage

Tests cover immutability, bounded identifiers, exact policy-set version and rule references,
deterministic IDs and clocks, allow/deny/approval-required decisions, stable reasons, active,
inactive, missing, unsupported, and mismatched subjects, Workspace and plan mismatches, unknown,
disabled, wrong-version, wrong-identity, and mismatched Registry references, category/effect drift,
step evaluation, aggregate decisions and precedence, correlation/causation propagation, and absence
of provider, Temporal, infrastructure, dynamic loading, executable policy, Planner, Executive,
Capability self-authorization, compilation, and execution authority.

## Quality gates

| Gate | Result |
|---|---|
| Ruff format | PASS — 226 files conformant |
| Ruff lint | PASS |
| strict mypy | PASS — 100 source files |
| Focused Phase 2.9–2.11 tests | PASS — 32 passed |
| Full pytest with services stopped | PASS — 138 passed, 31 gated skips |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock verification | PASS — 51 packages, lock unchanged |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Runtime and migration status

- PostgreSQL remained stopped; no listener, socket, runtime marker, or process was present.
- Temporal remained stopped; no listener or process was present.
- API and worker remained stopped.
- No runtime verification was performed.
- Migration head remains `20260811_0003`.
- Revision `20260812_0004` was not created or reserved.
- No `PolicyEvaluation` was persisted.
- No `ExecutionRequest` was submitted.

## Risks and deferred work

- In-memory Policy results must never be represented as durable authorization evidence.
- Operational enforcement requires durable Policy evidence and separately approved persistence.
- Human approval requests and decisions require a future Approval architecture.
- Policy must re-evaluate before execution and consequential commitment when operational wiring is
  introduced.
- Production roles, permissions, risk levels, budgets, quotas, restrictions, Workspace policy
  overrides, resource/effect snapshots, approval expiry, and reusable grants are deferred.
- Real AI, providers, Memory, external effects, API composition, worker composition, and Temporal
  enforcement are deferred.

## Verdict

`PHASE 2.11 POLICY & AUTHORIZATION DECISION FOUNDATION IMPLEMENTATION CANDIDATE PASSED`
