# Phase 2.18 AI Capability Routing & Safety Verification Report

**Date:** 2026-08-27
**Scope:** Source-only provider-neutral AI candidate eligibility and deterministic ranking
**Status:** `PHASE 2.18 AI ROUTING / SAFETY FOUNDATION IMPLEMENTED — CHECKPOINT REVIEW READY`

## Architecture

Phase 2.18 implements one bounded in-memory decision path:

```text
typed AIRouteRequirements + resolved policy/workspace constraints
  + trusted immutable AIProviderCandidate snapshots
  -> independent deterministic eligibility checks
  -> stable deterministic ranking
  -> selected model reference OR typed unavailable decision
  -> STOP
```

The Router receives resolved typed constraints; it does not interpret Policy or user text. Candidate
profiles are trusted only at the snapshot boundary and contain versioned, expiring evidence. Runtime
provider output, model output, Planner metadata, user content, and stale evidence are not trusted
routing inputs.

The Router does not import or invoke provider adapters, select runtime implementations, retry,
execute fallback, weaken requirements, authorize work, mutate workflow state, or call Policy,
Approval, Authorization, Orchestration, repositories, tools, Temporal, or vendor SDKs.

## Published contracts

`rightjob.contracts.ai_routing` publishes frozen, slotted, provider-neutral contracts for:

- structured-output guarantee, provider qualification and availability, and modality;
- bounded route requirements and immutable provider candidate snapshots;
- closed rejection reasons, candidate rejection evidence, route outcome, and route decision;
- the provider-neutral `AICapabilityRouter` protocol.

All request and Workspace IDs are non-nil, timestamps are timezone-aware, evidence expiry follows
observation, regions are bounded keys, and context, retention, cost, latency, and quality values are
bounded exact integers that reject booleans and floats. Enum, UUID, datetime, model-reference, and
semantic-version runtime types are checked exactly. Collection fields accept only the declared
`frozenset` or tuple shape with exact member types; mutable collections are rejected rather than
copied. The Router accepts only an exact tuple of at most 128 exact `AIProviderCandidate` values,
and candidate models must be unique within that snapshot.

Routing-local provider/model identities use a closed alphanumeric identity syntax with only the
punctuation required by normal model names (`._:/+-`). Whitespace, assignments, multiline text,
shell/code punctuation, and credential-, prompt-, instruction-, or raw-provider-content components
are rejected. This leaves the shared `AIModelReference` contract unchanged.

Route decisions expose only the request identity, closed outcome, optional selected model reference,
and closed rejection evidence. They contain no approval, authorization, Policy decision, workflow
transition, credential, prompt, user content, raw provider response, SDK object, repository object,
retry instruction, or executable content. Selection means eligibility only.

## Eligibility

Every candidate is independently checked, without short-circuit relaxation, for:

- current evidence, declared availability, and required qualification;
- structured-output guarantee, tool support, context size, and required modalities;
- data-sensitivity support, retention maximum, and allowed region;
- cost maximum, latency maximum, and quality minimum;
- fallback eligibility.

All failed checks are preserved in a fixed closed-reason order. Unavailable, unknown, stale, or
insufficiently qualified candidates fail closed. Allowing fallback removes only the fallback-only
restriction; it never weakens another requirement and does not execute a fallback.

Evidence is current exactly when `observed_at <= evaluated_at < expires_at`: observation is
inclusive and expiry is exclusive. Future observations, the exact expiry instant, and every later
instant fail closed as `STALE_EVIDENCE`.

## Stable ranking

Only fully eligible candidates are ranked. The exact ascending comparison key is:

1. provider qualification rank, descending;
2. quality score, descending;
3. estimated cost micro-units, ascending;
4. estimated latency milliseconds, ascending;
5. provider key, ascending;
6. model key, ascending.

The final two keys provide an explicit deterministic tie-break, so selection does not depend on
candidate input order. The Router performs no randomness, dynamic health lookup, provider call, or
model judgment.

## Groq limitation evidence

No production Groq profile was added. Tests inject a synthetic `groq / openai/gpt-oss-20b`
candidate carrying the committed Phase 2.16 evidence: `LIMITED` qualification and
`STRICT_SUBSET` structured-output guarantee. It is rejected for a `CANONICAL_CONTRACT`
requirement and is eligible for a compatible `STRICT_SUBSET` requirement only when every other
constraint passes.

## Files

Added:

- `packages/core/src/rightjob/contracts/ai_routing.py`
- `packages/core/src/rightjob/ai_router/routing.py`
- `tests/unit/test_ai_routing.py`
- this report

Modified:

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/ai_router/__init__.py`
- `scripts/check_architecture.py`
- `tests/architecture/test_boundaries.py`
- `docs/implementation/phase-status.md`

No provider adapter, AI runtime, Executive, Planner, Validator, Reviewer, Policy, Approval,
Authorization, Orchestration, Temporal, worker, API, migration, dependency, lock, or configuration
file changed.

## Verification

| Gate | Result |
|---|---|
| Focused Phase 2.18 tests | PASS — 90 passed |
| Architecture tests | PASS — 9 passed |
| Full ordinary pytest | PASS — 422 passed, 49 gated skips |
| Ruff format | PASS — 275 files |
| Ruff lint | PASS |
| strict mypy | PASS — 126 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages, unchanged |
| `git diff --check` | PASS |

Live/provider gates remain disabled. No provider request or runtime service is required. Migration
head remains `20260812_0004`.

## Deferred work

- Runtime adapter selection, provider invocation, health polling, qualification, fallback, retry,
  and repair remain deferred.
- Candidate persistence, cost ledgers, API/UI controls, Memory, production tools/Capabilities, and
  orchestration integration remain deferred.
- A route decision never substitutes for Policy, Approval, Authorization, or execution authority.

## Recommendation

`PHASE 2.18 AI ROUTING / SAFETY FOUNDATION IMPLEMENTED — CHECKPOINT REVIEW READY`
