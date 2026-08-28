# Implementation phase status

## Phase 1 — Repository Bootstrap

Implemented with environment conditions. See
`01-repository-bootstrap-report.md`.

## Explicitly unavailable

- Business Capabilities and business persistence
- Executive AI, prompts, model calls, and AI routing behavior
- Workflow compilation/execution
- Authentication flows
- Memory retrieval
- Provider Adapters and external effects
- Third-party plugins
- Production deployment automation

## Proof gates

| Technology | Status |
|---|---|
| Temporal | Phase 2.5 passed; Managed Temporal adopted by owner on 2026-08-11 |
| Clerk/Auth.js comparison | Not started |
| `pgvector` | Not started |
| Redis | Deferred |

Phases 2.1 through 2.7 are accepted. Managed Temporal is the approved Durable
Workflow Engine; production implementation remains behind the provider-neutral
orchestration contract.

## Phase 2.6 — Audit Evidence & Transactional Outbox Foundation

Accepted complete on 2026-08-11. See
`026-audit-outbox-foundation-verification-report.md`.

## Phase 2.7 — Execution & Orchestration Foundation

Accepted complete on 2026-08-12. See
`027-execution-orchestration-foundation-verification-report.md`.

## Phase 2.8 — Capability Registry Foundation

Accepted complete on 2026-08-12. Source gates and the approved Phase 2.7
SQLAlchemy metadata-composition PostgreSQL regression pass. No Capability persistence, migration,
Temporal runtime, Department, Policy, Executive AI, provider, or external effect was introduced.
See `028-capability-registry-foundation-verification-report.md`.

## Phase 2.9 — Department Runtime Foundation

Accepted complete on 2026-08-12. Source gates pass for global immutable synthetic
Department definitions, exact Capability membership, deterministic structured routing, and exact
Department-version validation during Orchestration compilation. No persistence, migration,
PostgreSQL runtime, Temporal runtime, Executive AI, Policy, provider, or external effect was
introduced. See `029-department-runtime-foundation-verification-report.md`.

## Phase 2.10 — Executive AI Planning Foundation

Accepted complete on 2026-08-12. Source gates pass for bounded structured planning
requests, deterministic synthetic proposals, exact Department/Capability validation, dependency and
cycle validation, validated in-memory plans, and Orchestration-owned compilation to—but not
submission of—`ExecutionRequest`. No persistence, migration, PostgreSQL runtime, Temporal runtime,
Executive behavior, real AI provider, Policy, approval, Memory, provider integration, or external
effect was introduced. See
`030-executive-ai-planning-foundation-verification-report.md`.

## Phase 2.11 — Policy & Authorization Decision Foundation

Implementation candidate completed on 2026-08-13. Source gates pass for immutable Policy contracts,
exact versioned synthetic rules, independent Registry revalidation, deterministic allow/deny/future
approval-required decisions, and step/aggregate plan evaluation. `PolicyEvaluation` remains
in-memory and cannot authorize compilation, persistence, workflow launch, Capability execution, or
external effects. No persistence, migration, PostgreSQL runtime, Temporal runtime, human Approval,
provider, Memory, API, worker, or execution wiring was introduced. See
`031-policy-authorization-decision-foundation-verification-report.md`.

## Phase 2.12 — Durable Authorization & Human Approval Foundation

Accepted complete on 2026-08-14. Immutable per-step Policy evidence, exact OWNER/ADMIN synthetic
approval, exact-action SHA-256 binding, aggregate plan authorization, mandatory Orchestration
verification, Policy/Approval persistence, migration `20260812_0004`, forced Workspace RLS, and
atomic Audit/Outbox application boundaries passed source and isolated PostgreSQL verification. The
behavioral proof completed with all fixtures and verifier privileges removed and PostgreSQL shut
down. See `032-durable-authorization-human-approval-foundation-verification-report.md`.

## Phase 2.13 — Executive AI Provider & Structured Reasoning Foundation

Accepted complete on 2026-08-14. Provider-neutral immutable AI contracts, a
Planning-owned provider-backed Planner, deterministic prompt/schema and Registry snapshots,
trusted identity injection, a deterministic fake provider, and one OpenAI Responses API adapter
establish the first real provider boundary. OpenAI tests use injected fake SDK behavior only. Model
output remains untrusted and becomes a validated in-memory `ExecutionPlan` only through the
existing deterministic `PlanValidator`; no Policy, approval, persistence, execution compilation,
ExecutionRequest, Temporal workflow, tool call, or live provider call occurs. See
`033-executive-ai-provider-structured-reasoning-foundation-verification-report.md`.

## Phase 2.14 — Executive Application Composition & Controlled AI Planning Path

Accepted complete on 2026-08-14. A presentation-only Executive façade constructs
trusted bounded Planning requests and deterministic enabled-Registry contexts, then calls a
published Planning application boundary. The same path works with `SyntheticPlanner` and with
`ProviderBackedPlanner` plus `FakeAIProvider`, producing only a validated in-memory `ExecutionPlan`
and a safe Executive presentation. No Policy, Approval, authorization, persistence, compiler,
ExecutionRequest, Capability, tool, provider network call, Temporal workflow, API route, or runtime
service was invoked. See `034-executive-application-composition-verification-report.md`.

## Phase 2.15 — Natural-Language Intent, Clarification & Planning Intake Foundation

Accepted complete on 2026-08-14. A bounded Executive-owned intake service
uses the published provider-neutral AI boundary to classify untrusted natural language into one
closed structured outcome: planning-ready, clarification-required, unsupported, or failed.
Planning-ready intent delegates to the existing Phase 2.14 façade; every other outcome stops before
Planning. Trusted Workspace, actor, correlation, causation, request identity, and timestamp remain
application-owned. No Policy, Approval, authorization, persistence, execution, Capability, tool,
provider network call, Temporal workflow, API route, or runtime service was invoked. See
`035-natural-language-intent-clarification-foundation-verification-report.md`.

## Phase 2.16 — Controlled Live AI Runtime Composition & Provider Smoke Foundation

Groq authentication, the exact `openai/gpt-oss-20b` model, chat connectivity, strict Structured
Outputs, the non-overlapping primitive `anyOf` normalization, and the Groq system-message
compatibility path were live verified. Removing the provider-local root-description mutation
restored HTTP acceptance. The final bounded smoke reached canonical INTENT decoding, which
correctly failed closed with `invalid_clarification`; Planning was not reached and no retry occurred.
Groq's documented strict-schema subset cannot encode every canonical RightJob INTENT invariant
without narrowing the canonical accepted value set. No retries, repair, coercion, canned values,
decoder weakening, or semantic relaxation are authorized. OpenAI remains unchanged and full Groq
runtime verification is not claimed. Status:
`PHASE 2.16 GROQ TRANSPORT/STRUCTURED OUTPUT VERIFIED — CANONICAL INTENT GUARANTEE BLOCKED BY PROVIDER SCHEMA EXPRESSIVENESS`.
See `036-controlled-live-ai-runtime-verification-report.md`.

## Phase 2.17 — Result Validation, Review & Executive Synthesis Foundation

Implemented on 2026-08-25 as a source-only, in-memory path from immutable Capability result through
trusted-context deterministic validation, exact Capability Registry re-resolution, optional
provider-neutral non-authoritative review, and presentation-safe Executive synthesis. Validation
evidence preserves Workspace/run/step/correlation/causation, exact Capability/output-contract and
artifact version/SHA-256 identity, timestamp validity, and payload bounds. Review may only score,
explain, cite evidence, and recommend `ACCEPT`, `REVISE`, or `NEEDS_HUMAN_REVIEW`; it cannot approve,
authorize, persist, mutate workflow state, invoke Policy/Approval, execute a Capability, or call a
provider. Executive deterministically projects only review criteria identity/version, bounded
numeric scores, and the closed recommendation into a presentation-safe summary. Free-form Reviewer
reasons and evidence references remain outside Executive presentation, which also excludes result
payloads, executable content, credentials, raw provider data, repositories, and workflow authority.
No migration, provider request, service, persistence, retry, repair, revision loop, API/UI,
worker/Temporal, Memory, tool, or production Capability change was introduced. Status:
`PHASE 2.17 RESULT VALIDATION / REVIEW / SYNTHESIS IMPLEMENTED — CHECKPOINT REVIEW READY`. See
`037-result-validation-review-synthesis-verification-report.md`.

## Phase 2.18 — AI Capability Routing & Safety Evaluation Foundation

Implemented on 2026-08-27 as a source-only, in-memory path from typed route requirements and
resolved policy/workspace constraints plus trusted immutable, versioned, expiring candidate
snapshots through independent deterministic eligibility filtering and stable ranking to either a
selected model reference or typed unavailable decision. Every mandatory structured-output, tool,
context, modality, privacy, retention, region, cost, latency, quality, availability, qualification,
and fallback constraint fails closed without relaxation; all applicable closed rejection reasons
are retained. Ranking is independent of input order and uses explicit provider/model tie-breaks.
Fallback is eligibility-only and cannot execute, retry, or weaken requirements. Route decisions are
non-authoritative and contain no credentials, prompts, provider payloads, runtime objects, Policy,
Approval, Authorization, workflow transition, or executable content. The Phase 2.16 Groq
limitation is represented only by injected test evidence; no production provider profile or runtime
behavior changed. No persistence, migration, provider request, service, runtime adapter selection,
health polling, Temporal/worker/API, Memory, tool, or production Capability was introduced. Status:
`PHASE 2.18 AI ROUTING / SAFETY FOUNDATION IMPLEMENTED — CHECKPOINT REVIEW READY`. See
`038-ai-capability-routing-safety-verification-report.md`.

The published trust boundary enforces exact runtime types: mutable collections, mutable/non-tuple
candidate sequences, wrong nested members, booleans/floats in integer fields, malformed enums, and
unsafe free-form model identities are rejected rather than coerced. Candidate evidence is valid on
the inclusive observation/exclusive expiry interval only.

## Phase 2.19 — Durable Result Quality Gate & Bounded Revision Governance

Stage A implemented source-only immutable contracts and a pure Orchestration-owned quality decision
over passed validation evidence, a matching non-authoritative review assessment, exact enabled
Capability Registry re-resolution, a Capability-owned versioned quality policy, and optional prior
quality-gate state. Acceptance derives only from the trusted required score and threshold. A
below-threshold result may reserve at most two automated revisions. The first
`REVISION_REQUIRED` reserves count `0 → 1`; the second reserves `1 → 2`; count `2` prohibits
another automated revision. A failed future execution does not refund a reservation, and exact
idempotent replay consumes no additional reservation. Non-improvement, exhausted budget, or a
conservative Reviewer human-escalation signal produces `needs_human_review` without approval or
execution authority. Free-form Reviewer diagnostics remain outside state and decision evidence.

Stage B adds Orchestration-owned durable state and append-only decision evidence with forced
Workspace RLS, optimistic concurrency, restart-safe command idempotency, and atomic safe Audit and
Outbox evidence. Reservation-time consumption durably enforces the two-cycle ceiling. Reviewer
diagnostic text is never persisted. No Capability invocation, provider call, revision execution,
human-review workflow, Temporal/worker/API path, Memory, retry, or fallback is implemented.
Migration head is `20260827_0005`. Status:
`PHASE 2.19 DURABLE QUALITY-GATE PERSISTENCE IMPLEMENTED — CHECKPOINT REVIEW READY`. See
`039-durable-result-quality-gate-design-report.md`.
