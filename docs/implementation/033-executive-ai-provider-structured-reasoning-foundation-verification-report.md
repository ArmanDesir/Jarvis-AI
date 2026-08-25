# Phase 2.13 Executive AI Provider & Structured Reasoning Foundation Verification Report

**Date:** 2026-08-14
**Scope:** Source-only provider-neutral AI planning and one isolated OpenAI adapter
**Status:** `PHASE 2.13 EXECUTIVE AI PROVIDER & STRUCTURED REASONING FOUNDATION IMPLEMENTATION CANDIDATE PASSED`

## Architecture and ownership

The implementation preserves the constitutional ownership correction established during the
read-only assessment. Executive remains unchanged and owns conversation, clarification,
explanation, and presentation only. Planning owns decomposition, prompt/schema construction,
provider invocation through the published `AIProvider` contract, trusted planning identity
injection, Registry enrichment, and construction of an untrusted `ProposedPlan`.

Department and Capability Registries remain authoritative. The existing `PlanValidator` remains
the deterministic acceptance authority. Policy, Approval, durable authorization, Orchestration,
Audit/Outbox persistence, and Temporal were not invoked or modified.

The implemented source-only path is:

```text
PlanningRequest + PlanningContext
  -> deterministic Registry snapshot
  -> provider-neutral AIRequest
  -> untrusted structured AI response
  -> AIPlanProposal decoding
  -> trusted ID injection and exact Registry re-resolution
  -> untrusted ProposedPlan
  -> existing PlanValidator
  -> validated in-memory ExecutionPlan
  -> STOP
```

No model or provider output can authorize, approve, persist, compile, execute, call a Capability,
or launch a workflow.

## Provider-neutral contracts

`rightjob.contracts.ai` publishes frozen, slotted contracts for `AIProvider`, `AIRequest`,
`AIResponse`, `AIMessage`, `AIMessageRole`, `AIModelPurpose`, `AIModelReference`, `PromptReference`,
`StructuredOutputReference`, `AIUsage`, `AIFinishStatus`, `AIProviderFailure`,
`AIProviderFailureKind`, `AIProviderError`, `AIPlanProposal`, and `AIPlanProposalStep`.

The only logical model purpose is `EXECUTIVE_PLANNING`. Contracts contain no credential, SDK,
provider client, Policy, Approval, execution, Temporal, ORM, repository, persistence, or tool type.
Provider failures expose stable `TRANSIENT`, `CONFIGURATION`, `REJECTED_OUTPUT`, and
`INVALID_OUTPUT` classes plus explicit retryability without exposing raw vendor payloads.

## Structured proposal and trusted identity

The model may propose only step sequence, objective, WorkCategory, exact Department key/version,
exact Capability key/version, bounded scalar key/value input records, and dependency sequences. The model cannot
provide UUIDs, Workspace, actor, request/plan/step/correlation/causation identity, planner identity,
canonical timestamps, immutable definition IDs, output/effect metadata, handler keys, workflow,
Policy, Approval, authorization, execution, Temporal, code, or tools.

`ProviderBackedPlanner` uses injected ID and clock factories. It generates invocation, plan, and
step identities in trusted application code and converts dependency sequence numbers to trusted
step UUIDs only after deterministic sequence validation. Workspace, actor provenance, request,
correlation, and causation come only from matching `PlanningRequest` and `PlanningContext`.

## Registry snapshot and enrichment

The prompt receives an immutable deterministically sorted snapshot of the exact enabled references
available in `PlanningContext`. It contains Department keys/versions, work categories, assigned
Capability key/version pairs, Capability input/output contract references, and descriptive effect
metadata. It excludes handlers, credentials, provider configuration, and implementation details.

After generation, Planning independently resolves every exact enabled Department and Capability,
verifies context availability, immutable reference identity, Capability membership, and WorkCategory
membership, then copies canonical output-contract and effect metadata. The existing `PlanValidator`
performs the independent final validation. Unknown, disabled, stale, mismatched, unavailable, or
incorrectly owned references fail closed.

## Prompt and schema

The code-owned immutable references are:

- prompt: `planning.structured-proposal@1.0.0`;
- structured output: `planning.ai-plan-proposal@1.0.0`.

The JSON Schema is deterministically encoded with sorted keys. The system instruction permits only
structured planning data. The user goal/input is serialized as untrusted data. No prompt contains
Policy rules, Approval internals, SQL, tables, credentials, endpoints, handler keys, or execution
instructions. There is no dynamic prompt loading, persistence, tenant editing, or self-modification.

## Fake provider

`FakeAIProvider` implements the same `AIProvider` protocol. Tests use it for valid structured
output, malformed output, refusal, truncation, normalized failure, usage, and response-bound paths.
It introduces no alternative planning architecture.

## OpenAI adapter

`OpenAIProviderAdapter` is the sole real provider adapter and uses the OpenAI Responses API. It is
non-streaming, non-background, sends `tools=[]`, disables storage, disables automatic truncation,
uses strict JSON Schema structured output, and provides no web/file search, shell, filesystem,
computer use, code execution, database access, Memory, Capability handler, workflow, or Temporal
control.

The adapter constructs the SDK client with `max_retries=0` and explicit `httpx.Timeout` values. It
rejects refusal, incomplete/truncated responses, missing content, malformed JSON, oversized output,
and unexpected terminal states. Detailed planning-schema validation remains Planning-owned and is
performed immediately after adapter decoding. All SDK exceptions and response objects terminate at
the adapter boundary.

OpenAI tests inject a fake SDK client/Responses resource. No test constructs a live client except a
constructor monkeypatch that captures configuration. No live provider request occurred and ordinary
pytest requires no API key.

## Dependency and lock impact

The approved dependency declaration is `openai>=2.46,<3`; uv resolved exact version `2.54.0`.
The lock added exactly:

- `openai==2.54.0`;
- `distro==1.9.0`;
- `jiter==0.16.0`;
- `sniffio==1.3.1`;
- `tqdm==4.70.0`.

Existing `httpx`, `pydantic`, `anyio`, `typing-extensions`, and unrelated major dependency versions
were not forced to change. The workspace remains Python 3.11 compatible. `uv lock --check` passes
with 56 resolved packages.

## Configuration, timeouts, bounds, and retry

The existing `Settings` seam now supports `RIGHTJOB_AI_ENABLED`, `RIGHTJOB_AI_ADAPTER`,
`RIGHTJOB_AI_MODEL`, `RIGHTJOB_AI_TIMEOUT_SECONDS`, `RIGHTJOB_AI_MAX_OUTPUT_TOKENS`, and
`RIGHTJOB_OPENAI_API_KEY`. AI remains disabled by default. Enabled OpenAI configuration requires a
model and key. The secret field has `repr=False` and never enters a published contract, prompt,
exception, report, Audit record, or Outbox event.

Initial bounds are:

- encoded AI request: at most 65,536 bytes;
- accepted AI response: at most 65,536 bytes;
- output token default: 2,048, with a hard configuration/contract ceiling of 8,192;
- plan steps: existing maximum 16;
- overall request: at most 30 seconds;
- connect: 5 seconds;
- pool: 5 seconds;
- write: 10 seconds;
- read: 30 seconds at the approved default and never beyond the overall approved ceiling.

There is one provider invocation and no automatic adapter, Planning, Executive, API, or Temporal
retry. Retryability is metadata for future durable coordination only.

Usage captures nonnegative input, output, total, and cached-input tokens when supplied. Cached input
cannot exceed input tokens and total cannot be smaller than input plus output. Cost estimation and
billing are absent.

## Architecture enforcement

The architecture checker now restricts OpenAI SDK imports to `rightjob.provider_adapters` and
continues prohibiting adapter imports from Planning, Policy, Registry implementation,
Orchestration, Identity, and repositories. Planning depends only on published contracts. Executive
still cannot import Planner or provider adapters. AI paths reject direct dynamic execution calls.

The Phase 1 proof-gate check was narrowed rather than removed: OpenAI is permitted only in
`packages/core/pyproject.toml`; Anthropic and other proof-gated dependencies remain prohibited.
Architecture tests independently scan for OpenAI imports outside provider infrastructure. No SDK
type is exported through `rightjob.contracts`.

## Files created

- `packages/core/src/rightjob/contracts/ai.py`
- `packages/core/src/rightjob/planner/provider_backed.py`
- `packages/core/src/rightjob/provider_adapters/fake_ai.py`
- `packages/core/src/rightjob/provider_adapters/openai.py`
- `tests/unit/test_ai_contracts.py`
- `tests/unit/test_provider_backed_planner.py`
- `tests/unit/test_openai_adapter.py`
- `docs/implementation/033-executive-ai-provider-structured-reasoning-foundation-verification-report.md`

## Files modified

- `packages/core/src/rightjob/contracts/__init__.py`
- `packages/core/src/rightjob/planner/__init__.py`
- `packages/core/src/rightjob/provider_adapters/__init__.py`
- `packages/core/src/rightjob/shared/config.py`
- `packages/core/pyproject.toml`
- `uv.lock`
- `scripts/check_architecture.py`
- `scripts/check_phase1_scope.py`
- `tests/architecture/test_boundaries.py`
- `tests/unit/test_config.py`
- `docs/implementation/phase-status.md`

No Executive, Policy, Approval, authorization, Orchestration, database, migration, API route,
worker, or Temporal production file changed for Phase 2.13.

## Verification

| Gate | Result |
|---|---|
| Ruff format | PASS — 244 files conformant |
| Ruff lint | PASS |
| strict mypy | PASS — 112 source files |
| Focused Phase 2.10–2.13 tests | PASS — 66 passed |
| Provider-neutral/OpenAI focused tests | PASS — 32 passed |
| Full pytest with runtime integrations gated | PASS — 176 passed, 46 skipped |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Runtime, persistence, and execution confirmation

- PostgreSQL remained stopped; port `55416` and its Unix socket were absent.
- Temporal remained stopped; no listener on `7233` appeared.
- API and worker remained stopped; no listener on `8000` appeared.
- No live OpenAI or other provider call occurred.
- No API key was used.
- No database mutation or provider persistence occurred.
- No migration was created or modified; migration head remains `20260812_0004`.
- No Policy evaluation, Approval, durable authorization issuance, `ExecutionPlanCompiler`,
  `ExecutionRequest`, `OrchestrationApplicationService`, `DurableWorkflowEngine`, Capability, tool,
  or Temporal workflow was invoked.

## Deferred work and risks

- Live-provider smoke verification requires separate approval, a dedicated non-production key,
  explicit cost bounds, and opt-in gating.
- API composition and an Executive presentation façade remain deferred; neither may acquire
  decomposition or provider-adapter ownership.
- Provider retries, routing, fallback, workspace provider settings, provider-call observability,
  prompt persistence, Memory/RAG, tools, production Departments/Capabilities, multimodal behavior,
  fine-tuning, autonomous loops, and external effects remain deferred.
- The provider is nondeterministic and potentially compromised; deterministic Registry enrichment,
  PlanValidator, Policy, Approval, durable authorization, and Orchestration enforcement must remain
  mandatory downstream controls.
- Detailed structured-output validation intentionally remains Planning-owned rather than being
  duplicated as provider-specific business logic. The adapter enforces strict provider schema
  request mode and rejects malformed transport output; Planning validates the decoded schema.

## Verdict

`PHASE 2.13 EXECUTIVE AI PROVIDER & STRUCTURED REASONING FOUNDATION IMPLEMENTATION CANDIDATE PASSED`
