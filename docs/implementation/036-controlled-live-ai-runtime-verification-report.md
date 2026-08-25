# Phase 2.16 Controlled Live AI Runtime Verification Report

**Date:** 2026-08-17
**Scope:** Provider-neutral production-style composition and explicitly gated live smoke harnesses
**Status:** `PHASE 2.16 GROQ CANONICAL-INTENT GUIDANCE READY — FINAL FULL RUNTIME SMOKE PENDING`

## Source checkpoint

### Composition

`rightjob.ai_runtime.composition.build_ai_planning_stack` is the single production-style
composition seam. It accepts validated `Settings`, published Capability and Department catalogs,
and trusted ID/clock factories, then constructs:

```text
OpenAIProviderAdapter
  -> ProviderBackedPlanner
  -> PlanningApplicationService + PlanValidator
  -> ExecutivePlanningService
  -> ExecutiveIntakeService
```

It returns only `ExecutiveIntakeService`, the existing pre-authorization application boundary.
Construction performs no provider invocation. A narrow provider-factory argument permits
deterministic source tests and the live harness's bounded observation wrapper; production defaults
to `OpenAIProviderAdapter`.

The factory fails closed when AI is disabled, the adapter is not exactly `openai`, model/key are
missing, or timeout/output-token bounds are invalid. `Settings` continues to hide the API key from
`repr`, and composition errors never contain its value.

### Live smoke harness and gating

`tests/live/test_openai_planning_smoke.py` contains the only live smoke. Its module-level gate
requires both:

- `RIGHTJOB_LIVE_AI_TESTS=true`;
- a present `RIGHTJOB_OPENAI_API_KEY`.

The test then relies on existing settings validation for `RIGHTJOB_AI_ENABLED=true`,
`RIGHTJOB_AI_ADAPTER=openai`, a nonblank `RIGHTJOB_AI_MODEL`, and bounded timeout/token settings.
Absent either primary gate, pytest skips before constructing network-capable behavior. Key presence
alone and opt-in alone were each verified to skip in isolated subprocesses. Ordinary pytest ran
with both variables removed and skipped the live module.

The exact synthetic input is:

> Prepare, transform, and verify this synthetic content.

The harness exercises the application path, never the adapter directly:

```text
ExecutiveIntakeService
  -> observed production AIProvider
  -> structured intent
  -> ExecutivePlanningService
  -> ProviderBackedPlanner
  -> observed production AIProvider
  -> Registry re-resolution
  -> PlanValidator
  -> validated presentation
  -> STOP
```

The observation wrapper records only provider/model references, logical purpose, prompt/schema
versions, finish status, bounded token usage, elapsed duration, correlation ID, and invocation
count. It records no key, raw prompt/response, reasoning, SDK object, or credential.

Expected successful-path calls are exactly two: one intent request and one planning proposal. The
test asserts both prompt identities and the count. A source proof shows unsupported intent stops
after one call. No retry is implemented in the composition, services, or harness; the existing SDK
adapter retains `max_retries=0`.

### Network and authority boundaries

Source tests compose the complete stack with a deterministic sequence provider and prove a
validated three-step presentation after exactly two calls. Default OpenAI stack construction with
a synthetic test secret performs no generation. Existing fake-client OpenAI adapter tests cover
structured output, no tools, retry disablement, explicit timeouts, usage, and normalized failures.

The live requests continue to use `tools=[]`, non-streaming, non-background generation, disabled
truncation, request/response bounds, and strict structured schemas. Neither composition nor harness
imports the OpenAI SDK directly.

The path stops at a validated in-memory presentation. It imports or invokes no Policy, Approval,
authorization evidence, execution compiler, Orchestration, ExecutionRequest, Capability handler,
Temporal, repository, database, Audit/Outbox mutation, Memory, or tool facility.

### Architecture enforcement

`ai_runtime` is registered as a composition module. It is explicitly allowed to import Executive,
Planning, and provider-adapter composition surfaces, but is forbidden from importing Audit,
Identity, Policy, Orchestration, repositories, or tool interfaces. The global vendor rule still
permits the OpenAI SDK only inside `rightjob.provider_adapters`. Executive and Planning remain
unable to import provider adapters.

### File inventory

Created:

- `packages/core/src/rightjob/ai_runtime/__init__.py`
- `packages/core/src/rightjob/ai_runtime/composition.py`
- `tests/unit/test_ai_runtime_composition.py`
- `tests/live/test_openai_planning_smoke.py`
- `docs/implementation/036-controlled-live-ai-runtime-verification-report.md`

Modified:

- `scripts/check_architecture.py`
- `tests/architecture/test_boundaries.py`
- `docs/implementation/phase-status.md`

No Executive, Planning, provider adapter, configuration, Policy, Approval, Orchestration, database,
migration, Temporal, API, worker, dependency, or lock file changed in Phase 2.16.

### Source verification

| Gate | Result |
|---|---|
| Focused Phase 2.13–2.16 tests | PASS — 52 passed, 1 explicitly gated live skip |
| Runtime composition tests | PASS — 8 passed |
| Full ordinary pytest | PASS — 207 passed, 47 skipped |
| strict mypy | PASS — 99 core source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Ruff format | PASS |
| Ruff lint | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages, unchanged |
| `git diff --check` | PASS |

The existing Starlette/httpx deprecation warning remains unchanged and unsuppressed.

### Runtime state

- PostgreSQL remained stopped; its socket and port `55416` were absent.
- Temporal remained stopped; port `7233` was absent.
- API and worker remained stopped; port `8000` was absent.
- No database mutation or Alembic command occurred.
- Migration inventory remains headed by `20260812_0004`; no `20260814_0005` exists.
- No live OpenAI call occurred and no real key was read or used.
- No Policy/Approval/authorization/execution/Capability/Temporal action occurred.

## Pending live checkpoint

### First controlled live failure diagnosis

The first controlled live smoke returned `ExecutiveIntakeOutcome.FAILED` with
`ExecutiveIntakeFailure.PROVIDER_UNAVAILABLE` before planning continuation. No second model call
was made during diagnosis. The configured model remained `gpt-5.6-terra`; the model, prompt,
schema, timeout, and retry configuration were unchanged.

The locked OpenAI Python SDK version is `2.54.0`. The adapter maps `APITimeoutError` to `TIMEOUT`,
`APIConnectionError` to `CONNECTION`, `RateLimitError` to `RATE_LIMIT`, `InternalServerError` to
`INTERNAL`, and other `APIStatusError` instances with status 502, 503, or 504 to `UNAVAILABLE`.
All five are transient `AIProviderFailure` values and Executive intake collapses every transient
failure to `PROVIDER_UNAVAILABLE`. `AIProviderError` retains only that provider-neutral failure;
it does not retain the SDK exception class, a bounded status code, or a safe diagnostic reason.
Consequently the exact underlying class/status from the consumed live attempt cannot be recovered
from the observed Executive result.

Presence-only inspection found `RIGHTJOB_AI_ENABLED`, `RIGHTJOB_AI_ADAPTER`,
`RIGHTJOB_AI_MODEL`, and `RIGHTJOB_OPENAI_API_KEY` present; no values or credential metadata were
printed. A sandboxed DNS attempt was restricted, so the authoritative unauthenticated check was
repeated outside that network sandbox without an API key. `api.openai.com` resolved over IPv4,
TLS certificate verification succeeded, and the host returned HTTP 421 to an unauthenticated
request to `/`. This proves DNS and TCP/TLS reachability at diagnosis time only; it does not prove
the conditions at the time of the smoke.

Because the retained result is compatible with a timeout, connection failure, rate limit, provider
5xx/internal error, or 502/503/504 availability response, the most specific supported
classification is `LOCAL_ADAPTER_ERROR_MAPPING_TOO_COARSE`. It is not possible to determine
whether authentication, an HTTP status, model validation, or structured-output validation was
reached during the consumed attempt. The smallest next step is a source correction that preserves
bounded non-secret diagnostic metadata (SDK category and, for `APIStatusError`, status code) before
any separately authorized rerun.

### Bounded live-diagnostic source correction

Owner approval accepted `LOCAL_ADAPTER_ERROR_MAPPING_TOO_COARSE` and authorized a source-only
correction. The existing `AIProviderFailure` remains the provider-neutral diagnostic category;
creating a duplicate enum was unnecessary. It gained only the missing `PERMISSION` and
`BAD_REQUEST` values. `AIProviderError` now optionally retains an integer `http_status`, validated
to the closed HTTP range 100 through 599. It retains no body, headers, URL, SDK exception, provider
message, credential, or request ID. Status is diagnostic evidence only and does not drive Executive
behavior.

The OpenAI adapter now normalizes errors as follows:

| OpenAI SDK error | Provider-neutral failure | HTTP status retained | Retryable |
|---|---|---:|---:|
| `APITimeoutError` | `TIMEOUT` | no | yes |
| `APIConnectionError` | `CONNECTION` | no | yes |
| `RateLimitError` | `RATE_LIMIT` | yes | yes |
| `AuthenticationError` | `AUTHENTICATION` | yes | no |
| `PermissionDeniedError` | `PERMISSION` | yes | no |
| `BadRequestError` | `BAD_REQUEST` | yes | no |
| `NotFoundError` | `UNSUPPORTED_MODEL` | yes | no |
| `APIStatusError` with 502, 503, or 504 | `UNAVAILABLE` | yes | yes |
| other `InternalServerError` | `INTERNAL` | yes | yes |

Normalization raises the bounded error outside the SDK exception handler, so the raw SDK error is
retained in neither `__cause__` nor `__context__`. Executive behavior is unchanged: transient
failures remain publicly `PROVIDER_UNAVAILABLE`; authentication, permission, configuration, and
unsupported model remain provider configuration failures; bad requests remain invalid provider
output.

The live harness now retains safe failure evidence containing provider/model references, `INTENT`
or `PLANNING` stage, invocation count, provider-neutral failure, provider-neutral kind, retryability,
and optional bounded status. Its failed assertion includes only that safe record. Fake-provider
tests prove both stage classifications without provider payloads.

Tests cover timeout, connection, rate limit, authentication, permission, bad request, internal 500,
and explicit 502/503/504 normalization; status presence/absence and range validation; retryability;
raw SDK exception/body exclusion; safe string/repr behavior; unchanged Executive presentation; and
intent/planning harness stage capture.

During the first focused test command after the correction, the terminal's already-present live
opt-in and credential caused the live-marked test to run unintentionally. This violated the
source-only rerun boundary. The attempt failed during invocation 1 at `INTENT`; the corrected safe
record identified `CONNECTION`, transient/retryable, with no HTTP status. No prompt, response,
credential, SDK exception, or provider payload was printed or retained. All later pytest commands
explicitly removed both the live opt-in and credential and made no live request. No further live
attempt is authorized or performed by this checkpoint.

### Source-correction verification

| Gate | Result |
|---|---|
| Diagnostic adapter/contracts/harness tests | PASS |
| Focused Phase 2.13–2.16 tests | PASS — 60 passed, 1 live skip |
| Runtime composition tests | PASS |
| Full ordinary pytest | PASS — 218 passed, 47 skipped |
| strict mypy | PASS — 119 source files |
| Ruff format | PASS — 259 files |
| Ruff lint | PASS |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

PostgreSQL ports `5432` and `55416`, Temporal port `7233`, and API port `8000` were not listening;
no matching PostgreSQL, Temporal, API, or worker process was present. No database mutation or
migration command occurred. Migration head remains `20260812_0004`.

### Owner-authorized second controlled live attempt

The owner acknowledged the unintended prior call and explicitly authorized one new controlled
live smoke attempt. Presence-only inspection confirmed `RIGHTJOB_LIVE_AI_TESTS`,
`RIGHTJOB_AI_ENABLED`, `RIGHTJOB_AI_ADAPTER`, `RIGHTJOB_AI_MODEL`, and
`RIGHTJOB_OPENAI_API_KEY`; no values or credential metadata were printed.

Before model access, `api.openai.com` resolved, TCP port 443 connected, TLS certificate validation
succeeded, and an unauthenticated request to `/` returned HTTP 421. `HTTP_PROXY`, `HTTPS_PROXY`,
`ALL_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, and `REQUESTS_CA_BUNDLE` were absent, so
no repository/runtime evidence indicated a curl-versus-SDK proxy or CA configuration difference.
The network-independent OpenAI adapter, AI runtime composition, and Executive intake regressions
passed: 37 tests. PostgreSQL port `55416` and its project socket were absent; Temporal port `7233`
and API port `8000` were not listening; and no relevant PostgreSQL, Temporal, API, or worker process
was present.

Exactly one live test process was started. It failed closed on provider invocation 1 during
`INTENT` with the following bounded evidence:

- provider: `openai`;
- model: `gpt-5.6-terra`;
- failure: `RATE_LIMIT`;
- failure kind: `TRANSIENT`;
- retryable: yes;
- HTTP status: 429;
- invocation count: 1.

Planning was not reached, so there was no second provider call, usage record, trusted-provenance
presentation, Registry re-resolution, or `PlanValidator` result. The existing request configuration
still used strict structured output, `tools=[]`, no SDK retries, and the unchanged model, prompt,
schema, timeout, and token limits. No Policy, Approval, authorization evidence, execution compiler,
ExecutionRequest, Orchestration, Capability handler, Temporal, database, or persistence path was
invoked. No raw provider payload, prompt, response, SDK exception, hidden reasoning, or credential
was recorded. Because the live smoke failed, post-live success regressions were not run and the
smoke was not rerun.

The result is `LIVE_RATE_LIMIT`. It does not prove a local production defect and does not mark the
phase failed. Status remains:

`PHASE 2.16 LIVE SMOKE READY — LIVE PROVIDER VERIFICATION PENDING`

The live smoke still requires local presence of:

- `RIGHTJOB_LIVE_AI_TESTS=true`;
- `RIGHTJOB_AI_ENABLED=true`;
- `RIGHTJOB_AI_ADAPTER=openai`;
- `RIGHTJOB_AI_MODEL` set to the owner-approved structured-output-capable model;
- `RIGHTJOB_OPENAI_API_KEY` supplied through the existing secret seam.

The exact future command, with the secret value intentionally omitted, is:

```bash
RIGHTJOB_LIVE_AI_TESTS=true RIGHTJOB_AI_ENABLED=true RIGHTJOB_AI_ADAPTER=openai \
  .venv/bin/pytest -x -vv tests/live/test_openai_planning_smoke.py
```

`RIGHTJOB_AI_MODEL` and `RIGHTJOB_OPENAI_API_KEY` must already be exported locally. The command is
not authorized or executed by this source checkpoint.

## Free-provider source checkpoint

### Provider status

#### OpenAI

- `OpenAIProviderAdapter` remains accepted and unchanged by the Groq checkpoint.
- The controlled live attempt reached OpenAI and returned HTTP 429 `RATE_LIMIT` on invocation 1.
- OpenAI live success remains pending; no OpenAI request was made during the Groq source checkpoint.

#### llama.cpp

- Official release `b10453`, asset `llama-b10453-bin-macos-x64.tar.gz`, was downloaded from the
  upstream `ggml-org/llama.cpp` GitHub release and its SHA-256 matched the published digest.
- Static Mach-O inspection found `llama-server` is x86_64 but declares minimum macOS 13.3. The
  development host reports macOS 10.15.8.
- The binary was not executed, no model was downloaded, and no local adapter was implemented.
- Local status is `BLOCKED — CURRENT OFFICIAL X64 BINARY REQUIRES MACOS 13.3+`.

#### Groq

- Groq Free was selected with the exact model `openai/gpt-oss-20b`; provider identity remains
  `groq`.
- `GroqProviderAdapter` uses one non-streaming `httpx` POST per invocation to the fixed official
  `https://api.groq.com/openai/v1/chat/completions` endpoint, with no retry or configurable host.
- Configuration requires only `RIGHTJOB_GROQ_API_KEY` for Groq and only
  `RIGHTJOB_OPENAI_API_KEY` for OpenAI. Unknown adapters and any Groq model other than the approved
  free model fail closed.
- Groq receives messages and the strict structured-output schema only. The request explicitly sets
  `tool_choice=none`, supplies neither tools nor functions, and has no authority or access to
  Policy, Approval, execution, Orchestration, Capability handlers, databases, filesystems, or
  shells.
- The provider-local wire copy recursively translates JSON Schema `const` to an equivalent
  single-value `enum`. Deterministic tests prove nested translation, preservation of all other
  schema fields, and byte-equivalent canonical schema input before and after generation.
- Response envelopes are bounded to 65,536 bytes. Content must be non-empty JSON object text.
  Usage and finish status map into provider-neutral contracts. Timeout, connection, 400, 401, 403,
  404, 413, 422, 429, and 5xx failures normalize without retaining bodies, headers, raw exceptions,
  requests, responses, or credentials.
- The Groq live harness requires every explicit live/configuration/key gate and skips before
  network-capable construction when any gate is absent. No Groq API key was read and no Groq live
  request was made. Live status remains pending separate owner approval.

### First controlled Groq live attempt diagnosis

The owner-authorized Groq Free live smoke reached invocation 1 at `INTENT` and returned
`ExecutiveIntakeOutcome.FAILED` with `ExecutiveIntakeFailure.INVALID_PROVIDER_OUTPUT`. Planning was
not reached, so no second provider invocation occurred. The attempt was not rerun during diagnosis.

The Groq harness retained only the bounded `AIRequest` list. It proves one invocation using provider
`groq` and model `openai/gpt-oss-20b`, but it retained no `AIResponse`, finish reason/status, usage,
provider-neutral failure, HTTP status, or decode-stage classification. Therefore the consumed result
cannot distinguish an HTTP `BAD_REQUEST` or other invalid-output provider error from an HTTP 200
response rejected for refusal, truncation, envelope/content/JSON shape, or canonical intent-schema
validation. In particular, it cannot establish whether content existed, was syntactically JSON, was
an object, or failed schema-version, enum, field, or cross-field validation.

Static source review found no schema-translation semantic change. The canonical intent schema is a
closed object requiring `schema_version`, `outcome`, `reason`, `goal`, `planning_input`,
`clarification_question`, and `missing_fields`; nested planning-input objects are also closed. The
wire schema preserves required fields, enums, nullable types, nested structure, and
`additionalProperties`, changing only `const: 1` to the equivalent `enum: [1]`. The top-level name
is `executive_intent-result` and strict mode is true.

The adapter expects the repository-tested OpenAI-compatible Chat Completions shape:
`choices[0].message.content` as non-empty JSON-object text and `finish_reason == "stop"`; it handles a
non-empty `message.refusal` and `finish_reason == "length"` as bounded failures. Repository evidence
does not prove which wire shape the consumed live response used because that evidence was discarded.

The most specific supported classification is `GROQ_LIVE_DIAGNOSTICS_TOO_COARSE`. Before another
live call, the smallest source-only correction is to extend the Groq observation boundary with the
same bounded failure evidence pattern already used by the OpenAI live harness, plus a bounded decode
stage/reason category. It must retain no raw response, content, prompt, provider body, headers,
reasoning, or credential. Phase 2.16 remains pending.

### Bounded Groq diagnostic source correction

Owner approval accepted `GROQ_LIVE_DIAGNOSTICS_TOO_COARSE` and authorized a source-only correction.
The first live result remains preserved as ambiguous: invocation 1 reached `INTENT`, failed closed
as `INVALID_PROVIDER_OUTPUT`, and did not reach planning. Nothing retained from that attempt can
identify its HTTP, envelope, content, JSON, or canonical-decode cause.

The provider-neutral contract now has two closed diagnostic enums. `AIProviderDiagnosticStage`
separates HTTP, response envelope, finish status, content, JSON parsing, JSON shape, and canonical
decoding. `AIProviderDiagnosticReason` supplies bounded reason codes for transport/status,
choices/message/content shape, refusal/truncation, oversized output, JSON failures, intent fields and
invariants, and planning proposals. `AIProviderError` optionally carries those values and an existing
finish-status enum while preserving its failure, kind, retryability, and bounded HTTP status. It
retains no text, body, content, headers, prompt, vendor object, or transport exception.

`GroqProviderAdapter` now assigns bounded stage/reason evidence to non-2xx responses, timeout and
connection failures, missing/invalid choices and messages, missing/invalid content, refusal,
truncation, unexpected finish, oversized responses, envelope/content JSON failures, non-object JSON,
invalid usage, and schema translation rejection. Exception creation occurs outside JSON/httpx
handlers so raw response bodies and parse/transport exceptions do not survive through exception
context or cause. Endpoint, model, strict schema, `const` translation, timeout, token bounds,
tool-free request, retry count, and functional response behavior are unchanged.

The canonical Executive intent decoder keeps the same schema and invariants while distinguishing
JSON non-object, exact-field mismatch, schema version, outcome/reason enums, planning goal/input,
clarification shape, unsupported reason, and cross-field invariant failures. Planning proposal JSON
parse, top-level shape, and canonical proposal rejection also carry provider-neutral bounded codes.
The public Executive result remains unchanged.

The Groq live observer records only stage (`INTENT` or `PLANNING`), invocation count, provider/model,
provider failure/kind/retryability/status, finish category, diagnostic stage/reason, and successful
finish/usage metadata. For successful provider responses it invokes the same canonical decoder only
to classify bounded live evidence, retains no content, and leaves normal Executive decoding and
PASS/FAIL behavior unchanged. A later planning failure without provider/decode evidence is safely
classified as a bounded planning-proposal validation failure.

Deterministic coverage includes HTTP 400, 401, 403, 404, 413, 422, 429, and 500; timeout and
connection; missing/empty/invalid choices, message, and content; refusal, truncation, oversized
response, malformed and non-object JSON; exact intent fields, schema version, outcome, goal, planning
input, clarification, unsupported reason, and outcome invariants. Tests also prove bounded immutable
diagnostics, unchanged Executive failures, and exclusion of keys, bodies, raw payloads, and exception
chains.

Source verification after the correction:

| Gate | Result |
|---|---|
| Diagnostic/Groq/Executive focused tests | PASS — 69 passed, 1 gated live skip |
| Focused Phase 2.13–2.16 tests | PASS — 130 passed, 2 gated live skips |
| Full ordinary pytest with AI/live environment removed | PASS — 270 passed, 48 skipped |
| Ruff format | PASS — 262 files |
| Ruff lint | PASS |
| strict mypy | PASS — 120 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

PostgreSQL ports `5432` and `55416`, Temporal port `7233`, and API port `8000` had no listeners; no
project PostgreSQL, Temporal, API, or worker process was present. No database mutation or Alembic
operation occurred. Migration head remains `20260812_0004`. No Groq, OpenAI, Gemini, or other
provider request occurred during this correction.

Status remains:

`PHASE 2.16 GROQ LIVE VERIFICATION PENDING`

### Second controlled Groq live attempt and HTTP 400 diagnosis

The second owner-authorized Groq Free live smoke reached exactly invocation 1 at `INTENT` and
failed closed with the corrected bounded evidence:

- provider/model: `groq` / `openai/gpt-oss-20b`;
- failure/kind: `BAD_REQUEST` / `INVALID_OUTPUT`;
- retryable: no;
- HTTP status: 400;
- diagnostic stage/reason: `HTTP` / `HTTP_STATUS`;
- planning: not reached;
- retries: zero.

The rejected request used the documented Chat Completions endpoint, system/user message roles,
`max_completion_tokens`, `n=1`, `temperature=0`, non-streaming operation, and strict
`json_schema` response format. Official Groq documentation lists `openai/gpt-oss-20b` as supporting
strict Structured Outputs. The translated intent schema satisfies the documented subset: every
object is closed, every property is required, nullable fields use unions with `null`, and its
primitive, object, array, enum, and `anyOf` constructions are supported. The only documented
request mismatch was the simultaneous explicit `tool_choice: "none"`: Groq states that tool use is
not supported with Structured Outputs. The field was redundant because Groq also documents `none`
as the default when no tools are supplied.

The smallest provider-local correction removes only `tool_choice` from Groq structured-output
requests. No `tools` or `functions` array is supplied, so tool exposure remains impossible and the
documented default preserves the same no-tool semantics. Endpoint, provider/model, messages,
canonical schemas, `const` to single-value `enum` translation, strict mode, token/timeout bounds,
temperature, streaming, and retry behavior are unchanged. A deterministic adapter assertion proves
that `tool_choice`, `tools`, and `functions` are all absent.

The HTTP 400 body remains intentionally discarded. Although the body cannot independently confirm
the provider's validation message, source plus official documentation establish the request-parameter
incompatibility and leave no other documented incompatibility in the emitted request. Classification:
`GROQ_REQUEST_PARAMETER_INCOMPATIBLE`, caused by a `LOCAL_GROQ_ADAPTER_DEFECT`.

Offline verification after the provider-local correction:

| Gate | Result |
|---|---|
| Focused Phase 2.13–2.16 tests | PASS — 130 passed, 2 gated live skips |
| Full ordinary pytest with AI/live environment removed | PASS — 270 passed, 48 skipped |
| Ruff format | PASS — 262 files |
| Ruff lint | PASS |
| strict mypy | PASS — 120 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

No Groq, OpenAI, Gemini, or other provider request occurred during diagnosis or correction. Phase
2.16 remains `GROQ LIVE VERIFICATION PENDING`; the correction has not been verified by another live
attempt.

### Repeated post-correction HTTP 400 and root-cause retraction

The owner manually executed the post-`tool_choice` smoke twice accidentally. Both runs produced the
same bounded result: provider/model `groq` / `openai/gpt-oss-20b`, stage `INTENT`, invocation count
one per run, `BAD_REQUEST` / `INVALID_OUTPUT`, non-retryable, HTTP 400, no finish status, diagnostic
`HTTP` / `HTTP_STATUS`, and Executive `FAILED` / `INVALID_PROVIDER_OUTPUT`. Planning was not reached
and neither run performed an internal retry. These were two Groq requests total.

Current source proves that `tool_choice`, `tools`, `functions`, and `function_call` are absent from
the serialized request. Therefore the earlier conclusion that explicit `tool_choice: "none"` caused
the HTTP 400 is retracted and classified as a `DISPROVEN ROOT-CAUSE HYPOTHESIS`. Its removal was
semantics-preserving but did not correct the provider rejection.

An offline reconstruction of the exact intent wire schema found only `type`, `properties`,
`required`, `additionalProperties`, `enum`, `items`, and `anyOf`. The root object and the nested
planning-input item object both set `additionalProperties: false` and require every declared
property; there are no object branches inside `anyOf`. Nullable string and array fields use type
unions with `null`; the planning-input value uses `anyOf` over string, integer, number, boolean, and
null; the goal enum includes null consistently with its nullable type. Official Groq strict
Structured Outputs documentation lists the exact model, response-format envelope, these schema
features, nullable unions, and `anyOf` as supported.

The remaining request fields are the documented Chat Completions endpoint, model, two string-content
messages with system/user roles, `max_completion_tokens: 2048`, `n: 1`, `temperature: 0`,
`stream: false`, and the documented strict `json_schema` envelope. Official model examples accept
system/user messages, the API permits temperature 0 through 2, `n=1`, non-streaming operation, and
`max_completion_tokens`; the model limit exceeds 2048. No official Groq documentation found in this
audit states a schema-name restriction violated by `executive_intent-result`.

Groq documents an error-body `error.type` string such as `invalid_request_error`, but does not
publish an exhaustive closed set that would safely preserve a more specific stable cause. That
general value would not distinguish schema, parameter, model, or message rejection from the
retained HTTP 400. No error-body capture was added.

The most specific supported classification is `GROQ_PROVIDER_REJECTED_REQUEST_UNKNOWN_REASON`.
The root cause is not conclusive with the deliberately discarded error body, so no further
functional source correction is justified and no further live attempt is justified at this
checkpoint. No additional Groq, OpenAI, or Gemini request occurred during this audit. Phase 2.16
remains `GROQ LIVE VERIFICATION PENDING` pending owner review.

### Safe Groq HTTP-error diagnostic enrichment

Owner approval accepted the unresolved repeated HTTP 400 classification and authorized bounded
machine-readable diagnostics before any future call. Current official Groq error documentation
defines an `error` object containing only human-readable `message` and machine-oriented string
`type`; it does not document `code` or `param`. Accordingly, the provider-neutral `AIProviderError`
gained only optional `provider_error_type`. No code/param fields were added.

The value is accepted only when it is an ASCII identifier beginning with a letter, followed by at
most 63 letters, digits, underscores, or hyphens. Invalid, non-string, empty, non-ASCII, or oversized
values become `None`; arbitrary text is never truncated into acceptance. `error.message`,
undocumented fields, the parsed object, response body, response object, headers, request, schema,
prompt, and credential are never retained.

For non-2xx Groq responses, the adapter first checks the existing 65,536-byte response bound. It
attempts JSON parsing only within that bound, inspects only `error.type`, discards the parsed value,
and raises the existing normalized failure with unchanged kind, retryability, HTTP status, and
diagnostic stage/reason. Malformed, non-object, missing, invalid, or oversized error bodies preserve
the existing HTTP classification with `provider_error_type=None`. Parsing failures do not survive
through exception cause or context. No Groq request field or functional behavior changed.

The Groq live harness's bounded failure evidence now includes only the optional validated provider
error type in addition to its existing provider/model, stage/count, failure/kind/retryability,
status, finish, and diagnostic stage/reason. It retains no message, body, content, prompt, schema,
key, header, or provider object.

Offline verification:

| Gate | Result |
|---|---|
| Diagnostic focused tests | PASS — 91 passed, 1 gated live skip |
| Focused Phase 2.13–2.16 tests | PASS — 145 passed, 2 gated live skips |
| Full ordinary pytest with AI/live environment removed | PASS — 285 passed, 48 skipped |
| Ruff format | PASS — 262 files |
| Ruff lint | PASS |
| strict mypy | PASS — 120 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

Ports `5432`, `55416`, `7233`, and `8000` had no listeners; the project PostgreSQL socket and PID
files were absent. No service was started or stopped, no database mutation or Alembic operation
occurred, and migration head remains `20260812_0004`. All live opt-ins and credentials were removed
from pytest subprocesses; no Groq, OpenAI, Gemini, or other provider call occurred.

The repeated HTTP 400 cause remains unresolved and the `tool_choice` hypothesis remains disproven.
Status remains `PHASE 2.16 GROQ LIVE VERIFICATION PENDING`. One separately owner-authorized
diagnostic Groq attempt is now technically justified because it can retain the documented bounded
`error.type`; it is not authorized or executed by this source checkpoint.

Preserved provider status:

- OPENAI LIVE: `PENDING — HTTP 429 RATE_LIMIT`
- LLAMA.CPP: `BLOCKED — CURRENT OFFICIAL X64 BINARY REQUIRES MACOS 13.3+`
- GROQ: `LIVE ATTEMPT REACHED PROVIDER`; `INTENT FAILED CLOSED — INVALID_PROVIDER_OUTPUT`;
  `PLANNING NOT REACHED`

### Isolated minimal strict-output compatibility result

The owner manually ran the explicitly gated isolated compatibility harness once. Probe
`1-minimal` made exactly one Groq request using `openai/gpt-oss-20b`, two short string-content
system/user messages, and only the documented strict `json_schema` response format. Its schema was
a closed object with one required boolean property. Groq returned HTTP 400 with bounded
`provider_error_type=invalid_request_error`, no finish status or usage, and no successful JSON
content. The harness stopped immediately; probes 2 through 6 and the full RightJob live smoke were
not run.

This result eliminates the Executive intent schema, provider-local `const` translation, nullable
unions, `anyOf`, Executive, Planning, Registry resolution, and PlanValidator as the immediate cause.
Current official Groq documentation still lists `openai/gpt-oss-20b` under Free-plan limits and as
supporting Chat Completions strict Structured Outputs with the same `response_format` nesting used
by Probe 1. It documents no paid tier, service-tier parameter, account opt-in, beta, preview, or
deprecation requirement for strict mode. The minimal request therefore contradicts documented
capability but does not distinguish account/model access or general request failure from strict-mode
availability because no ordinary-chat or JSON Object Mode baseline has been run.

The most specific current classification is `GROQ_MINIMAL_STRICT_STRUCTURED_OUTPUT_REJECTED`; the
underlying root cause remains inconclusive. A separately approved isolated diagnostic should use at
most three sequential, zero-retry requests: ordinary chat without `response_format`, JSON Object
Mode, then the exact documented minimal strict JSON Schema form, stopping at the first meaningful
failure. No adapter, Executive, Planning, schema, prompt, timeout, or token-limit change is justified
before that capability isolation. No additional Groq, OpenAI, or Gemini request occurred during this
documentation/source diagnosis.

Status remains `PHASE 2.16 GROQ LIVE VERIFICATION PENDING`.

### Three-probe Groq capability baseline harness

The prior isolated minimal strict Probe 1 remains preserved as HTTP 400
`invalid_request_error`; its root cause remains inconclusive. The existing isolated harness now uses
the narrower sequential capability baseline: (A) ordinary Chat Completions without
`response_format`, (B) JSON Object Mode with only `response_format.type=json_object`, and (C) the
documented minimal strict JSON Schema request. Each request contains only the approved model and two
short synthetic messages plus the probe-specific response format. No probe includes tools,
functions, `tool_choice`, streaming, reasoning settings, temperature, token limits, or `n`.

The harness has a hard three-call counter, zero retry path, and stops on the first failed probe. Its
bounded evidence contains only probe/provider/model, HTTP status, validated provider error type,
finish status, usage, elapsed time, content-presence, JSON-validity, and expected-structure flags. It
does not retain prompts, generated ordinary-chat text, keys, headers, error messages or bodies, raw
responses, or reasoning. The existing live opt-in, adapter, exact-model, and credential gates remain
mandatory before the network-capable test body is entered.

Offline verification after this diagnostic-only change:

| Gate | Result |
|---|---|
| Compatibility harness | PASS — 5 passed, 1 gated live skip |
| Full ordinary pytest with live/provider environment removed | PASS — 290 passed, 49 skipped |
| Ruff format | PASS — 263 files |
| Ruff lint | PASS |
| strict mypy | PASS — 120 source files |
| Architecture boundaries | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV lock consistency | PASS — 56 packages |
| `git diff --check` | PASS |

Ports `55416`, `7233`, and `8000` had no listeners, the project PostgreSQL socket was absent, and
the migration set still ends at `20260812_0004`. No service was started or stopped and no Alembic or
database operation occurred. All live activation and credentials were removed from test
subprocesses; no Groq, OpenAI, Gemini, or other provider request occurred during implementation.

Status remains `PHASE 2.16 GROQ LIVE VERIFICATION PENDING`. The three-probe live run requires
separate owner approval.

### Groq baseline capability proof and production-request delta

The owner ran the verified three-probe isolated harness once. Ordinary Chat Completions, JSON Object
Mode, and minimal strict JSON Schema mode all passed using `openai/gpt-oss-20b` on the Groq Free
plan. The harness made exactly three sequential provider calls with zero retries. This confirms the
credential, account, model, ordinary inference, and basic strict Structured Outputs capability. No
Executive, Planning, Registry, PlanValidator, Policy, Approval, execution, Temporal, or database path
was involved.

The outstanding HTTP 400 is therefore narrowed to `PRODUCTION REQUEST DELTA`. Offline reconstruction
found that known-good Probe C serializes only model, two string messages, and the minimal strict
response format (393 compact JSON bytes). The production INTENT request adds
`max_completion_tokens: 512`, `n: 1`, `temperature: 0`, and `stream: false`; replaces the 103-byte
minimal schema and `probe` name with the 896-byte provider-local intent schema and
`executive_intent-result`; and replaces the 48/41-byte synthetic messages with 202/73-byte
production system/user strings. The production payload is 1,457 compact JSON bytes. It sends no
reasoning, service-tier, stop, seed, top-p, tool, function, or tool-choice field. Both requests remain
well below RightJob's 65,536-byte bound.

No definite serialization defect is present in that diff. Current Groq documentation accepts each
generation field, lists a 65,536-token model output limit, and documents the schema constructs in the
intent wire schema; it publishes no smaller schema-byte, property-count, nesting, enum, or `anyOf`
limit violated here. The isolated harness therefore now contains four cumulative, zero-retry deltas:
(D1) add the actual 512-token cap; (D2) add `n`, temperature, and non-streaming defaults; (D3) replace
the response format with the exact production schema/name; and (D4) replace messages with the exact
production synthetic INTENT messages. It stops on the first failure and cannot exceed four calls.
No live delta probe was run during this source checkpoint.

Offline verification passed: the differential harness had 6 passing tests and 1 gated live skip;
the focused Phase 2.13–2.16 selection had 143 passing tests and 3 live skips; and full ordinary
pytest had 291 passing tests and 49 skips. Ruff format/lint, strict mypy (120 source files),
architecture boundaries, phase scope, migration safety, secret hygiene, Python compilation, UV lock
consistency (56 packages), and `git diff --check` all passed with live activation and provider
credentials removed.

Status remains `PHASE 2.16 GROQ LIVE VERIFICATION PENDING`.

### D3 production response-format failure and E-series isolation

The owner ran the four-step production-delta harness once. D1 (`max_completion_tokens: 512`) and D2
(`n: 1`, `temperature: 0`, `stream: false`) returned HTTP 200 and passed. D3, which changed only the
strict response format's schema name and schema body while retaining the D2 model, messages,
generation fields, strict flag, and envelope nesting, returned HTTP 400 with bounded
`provider_error_type=invalid_request_error`. D4 was correctly not reached. The production failure is
therefore conclusively narrowed to the schema name and/or exact production intent wire-schema body.

Official Groq documentation publishes examples of `json_schema.name` but no allowed-character,
starting-character, hyphen/underscore, or maximum-length constraint. No name correction is therefore
justified offline. The isolated harness now implements at most four E-series calls: E1 changes only
the known-good minimal schema name to `executive_intent-result`; E2 retains name `probe` and changes
only the body to the exact production wire schema. If E1 fails, the harness stops. If E1 and E2 both
pass, it stops because the combined name/body interaction is isolated. If E1 passes and E2 fails, E3
tests the production scalar enum/nullable subset; a passing E3 permits E4, which uses the exact
production schema except that the nested planning-input value `anyOf` is replaced with a string leaf.
This makes an E4 pass, against the already failed exact E2 body, specific to that `anyOf`
combination. The harness remains direct HTTP diagnostic code, has zero retries, and cannot exceed
four calls.

No production adapter, canonical Executive schema, Executive/Planning behavior, prompt, runtime,
database, or migration was changed. No Groq, OpenAI, Gemini, or other provider request occurred
during this source checkpoint. Status remains `PHASE 2.16 GROQ LIVE VERIFICATION PENDING`.

Offline verification passed: compatibility harness 6 passed with 1 gated live skip; Groq adapter 45
passed; focused Phase 2.13–2.16 selection 143 passed with 3 live skips; full ordinary pytest 291
passed with 49 skips. Ruff format/lint, strict mypy (120 source files), architecture boundaries,
phase scope, migration safety, secret hygiene, Python compilation, UV lock consistency (56
packages), and `git diff --check` passed with all live activation and credentials removed.

### E-series anyOf boundary and provider-local compatibility investigation

The owner ran the E-series harness once with exactly four calls and zero retries. E1 production name
returned HTTP 200; E2 exact production body returned HTTP 400 with bounded
`provider_error_type=invalid_request_error`; E3 scalar enum/nullable returned HTTP 200; and E4 exact
production body with only the nested planning-input value `anyOf` replaced by a string leaf returned
HTTP 200. No call was repeated. This establishes a live incompatibility at
`$.properties.planning_input.items.properties.value.anyOf` or its interaction with the complete
strict schema, without claiming that Groq globally rejects `anyOf`.

That canonical node has five bare branches: string, integer, number, boolean, and null. It contains
no enum, object, array, additional branch constraint, or unconstrained branch. RightJob's domain and
decoder accept exactly `str | int | float | bool | None`.

The owner ran F1 once. Its Groq-only multi-type-array translation returned HTTP 400 with bounded
`provider_error_type=invalid_request_error`; exactly one request was made and there was no retry.
That translation is therefore `UNVERIFIED / LIVE-REJECTED` and is not an accepted production
compatibility solution.

The next narrow hypothesis is the overlap between the bare `integer` and `number` branches. Under
JSON Schema instance semantics, every integer is already accepted by `number`, so removing only an
unconstrained bare `integer` branch when the same `anyOf` contains an unconstrained bare `number`
branch preserves the accepted JSON value set. The Groq-only translator now retains `anyOf` and
performs only that normalization. Constrained numeric branches and unrelated unions remain
unchanged. Existing recursive `const` to single-value `enum` translation remains intact. Canonical
schema input remains deep/byte equal before and after translation, and OpenAI continues to receive
the unchanged canonical schema.

The owner executed the isolated `G1-non-overlapping-production-anyof` harness once. G1 passed with
the exact canonical Executive INTENT schema passed through the narrow Groq translator, production
schema name and generation settings, baseline synthetic messages, strict mode, and no tools. It
made exactly one Free-plan request with zero retries and $0 inference cost. Canonical schema input
remained unchanged and OpenAI retained the canonical five-branch `anyOf`.

Together, D1 PASS, D2 PASS, D3 HTTP 400, E1 PASS, E2 HTTP 400, E3 PASS, E4 PASS, F1 type-array
HTTP 400, and G1 non-overlapping `anyOf` PASS isolate the compatibility boundary sufficiently for
the provider-local production normalization. The accepted classification is: Groq strict
Structured Outputs rejects the overlapping bare `integer` plus `number` primitive union in this
production schema context. This does not claim that Groq rejects `anyOf`, `integer`, or `number`
generally; the provider-internal reason remains undocumented.

Offline verification passed: translation/Groq/OpenAI/harness tests 73 passed with 1 gated live skip;
focused Phase 2.13–2.16 tests 130 passed with 3 live skips; and full ordinary pytest 298 passed with
49 skips. Ruff format/lint, strict mypy (120 source files), architecture boundaries, phase scope,
migration safety, secret hygiene, Python compilation, UV lock consistency (56 packages), and
`git diff --check` passed with all live activation and provider credentials removed. PostgreSQL,
Temporal, API, and worker remained stopped; migration head remained `20260812_0004`. No Groq,
OpenAI, Gemini, or other provider request occurred after G1 during the post-G1 source gates.

No Policy, Approval, authorization, execution, capability, orchestration, Temporal, or persistence
path was invoked by G1. Status:
`PHASE 2.16 GROQ NON-OVERLAPPING ANYOF FIX VERIFIED — FULL RUNTIME SMOKE PENDING`.

### Full-runtime message boundary and convergence correction

The owner ran the full Groq runtime smoke once after G1. INTENT made one request and returned HTTP
400 `invalid_request_error`; Planning was not reached and no retry occurred. Offline comparison
proved that G1 and runtime INTENT used identical endpoint, model, translated schema, schema name,
strict flag, generation parameters, headers, timeout, and all non-message fields. H1 then replaced
only G1's system message with the exact production INTENT system instruction and reproduced HTTP
400. I1 used only its first classification sentence and also reproduced HTTP 400. These results
establish a Groq strict-output compatibility boundary at the production system-message wording or
its interaction with the production schema. They do not establish a semantic defect in the
canonical prompt, schema, or decoder; further phrase-level probing is closed.

The smallest convergent correction is provider-local: Groq replaces wire-level system-message text
with the exact short instruction already accepted by live G1 and preserves user messages verbatim.
Canonical AI requests and prompts are not mutated; OpenAI continues receiving the original system
instructions. Groq still uses strict translated schemas, including the live-verified removal of
only a redundant bare integer branch when an unconstrained number branch exists. No tools are
exposed and retries remain zero.

This substitution adds no application authority. Untrusted content remains in the user role;
strict schemas and canonical decoders remain fail closed; Registry references are re-resolved
locally; PlanValidator remains authoritative; trusted provenance and identifiers remain
application-owned; and no Policy, Approval, authorization, execution, capability, orchestration,
Temporal, or persistence path is added. The retired phrase diagnostic is hard-skipped.

Offline verification after the correction passed: 138 focused tests with 2 gated live skips; full
ordinary pytest 300 passed with 49 skips; Ruff format/lint, strict mypy (120 source files),
architecture boundaries, phase scope, migration safety, secret hygiene, Python compilation, UV lock
consistency (56 packages), and `git diff --check` passed. No provider request occurred.

Status: `PHASE 2.16 GROQ WIRE-PROMPT COMPATIBILITY FIX READY — FINAL FULL RUNTIME SMOKE PENDING`.

### Canonical clarification boundary

The next owner-run full smoke advanced past HTTP request acceptance and returned a structured INTENT
response. Canonical decoding failed closed with `SCHEMA_VIOLATION`, stage `CANONICAL_DECODE`, reason
`INVALID_CLARIFICATION`; Planning was not reached, one request was made, and no retry occurred. The
Groq HTTP/wire compatibility issue is therefore considered resolved for INTENT.

The strict schema requires the seven fields and constrains their individual types and enum values,
but cannot currently enforce the canonical outcome-dependent relationships. A
`clarification_required` intent is valid only with reason `missing_information`, null goal and
planning input, a non-blank question no longer than 500 characters, and 1 to 8 unique lowercase
field keys. The schema alone permits a wrong reason, planning data, a null or blank question, empty
or oversized fields, invalid field keys, and duplicates. The bounded live diagnostic cannot identify
which subcondition the discarded payload violated; it conclusively identifies the aggregate
clarification invariant.

The production correction preserves the canonical decoder and schema value set. Only the Groq wire
schema for `executive.intent-classification` receives a bounded description spelling out the
existing canonical shapes for planning-ready, clarification-required, and unsupported outcomes.
Canonical schema input remains unmodified and OpenAI remains unchanged. Deterministic tests prove
schema-valid but canonical-invalid clarification combinations still fail closed and prove the Groq
wire guidance preserves required fields and closed-object rules.

Offline verification passed: 129 focused tests with 1 gated live skip; full ordinary pytest 304
passed with 49 skips; Ruff format/lint, strict mypy (120 source files), architecture boundaries,
phase scope, migration safety, secret hygiene, Python compilation, UV lock consistency (56
packages), and `git diff --check` passed. No provider request occurred.

Status: `PHASE 2.16 GROQ CANONICAL-INTENT GUIDANCE READY — FINAL FULL RUNTIME SMOKE PENDING`.

### Groq source verification

| Gate | Result |
|---|---|
| Groq adapter/config focused tests | PASS — 33 passed |
| Focused Phase 2.13–2.16 tests | PASS — 100 passed, 2 live skips |
| Full ordinary pytest with complete AI namespace removed | PASS — 252 passed, 48 skipped |
| Ruff format | PASS — 262 files |
| Ruff lint | PASS |
| strict mypy | PASS — 120 source files |
| Architecture boundaries | PASS |
| Phase scope | PASS |
| Migration safety | PASS |
| Secret hygiene | PASS |
| Python compilation | PASS |
| UV dependency/lock inputs | UNCHANGED — existing `httpx` reused; no package or lock edit |
| `git diff --check` | PASS |

The first full-suite command deliberately removed provider credentials but inherited an existing
enabled OpenAI adapter/model environment, so API modules correctly failed closed during collection.
No test or provider request ran from those modules. The ordinary suite was rerun with the complete
AI configuration namespace removed and passed as recorded above.

PostgreSQL ports `5432` and `55416`, Temporal port `7233`, and API port `8000` were not listening.
No service, database, Alembic operation, provider request, or external action was started. Migration
head remains `20260812_0004`.

The exact future Groq command, with the secret intentionally omitted, is:

```bash
RIGHTJOB_LIVE_AI_TESTS=true RIGHTJOB_AI_ENABLED=true RIGHTJOB_AI_ADAPTER=groq \
  RIGHTJOB_AI_MODEL=openai/gpt-oss-20b \
  .venv/bin/python -m pytest -x -vv tests/live/test_groq_planning_smoke.py
```

`RIGHTJOB_GROQ_API_KEY` must already be exported locally. This command was not authorized or
executed by the source checkpoint.

## Risks and deferred work

- Model structured-output compatibility and provider behavior remain unproven until the separately
  approved live call.
- The success prompt is intentionally synthetic; no business-quality claim will follow from it.
- Production API activation requires bounded provider invocation observability integrated with the
  accepted Audit/Observability architecture. No persistence is warranted for this development
  smoke.
- Provider fallback, layered retries, Memory/RAG, tools, Policy/Approval continuation, execution,
  cost accounting, load testing, and adversarial live cases remain deferred.

## Recommendation

`PHASE 2.16 GROQ CANONICAL-INTENT GUIDANCE READY — FINAL FULL RUNTIME SMOKE PENDING`
