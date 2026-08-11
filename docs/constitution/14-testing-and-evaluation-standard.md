# Testing and Evaluation Standard

## Required test layers

- Domain tests for deterministic invariants and policy rules.
- Application tests for commands, queries, validation, and failure behavior.
- Contract tests for capabilities, tools, providers, plugins, APIs, and events.
- Repository tests against real PostgreSQL and RLS.
- Workflow replay/failure tests for retry, timeout, cancellation, compensation,
  approval, uncertain outcomes, and version changes.
- Integration tests at external boundaries using fakes, sandboxes, or recordings
  with secrets removed.
- End-to-end tests for representative user outcomes and tenant isolation.
- Load/resilience tests using documented agency workloads and noisy tenants.
- Security tests for authorization, injection, webhooks, secrets, plugins, and
  cross-tenant access.

## AI evaluation

AI behavior is evaluated separately from deterministic correctness. Versioned
datasets cover command classification, intent clarification, context resolution,
planning, routing requirements, qualitative review, safe refusal, prompt
injection, and result presentation.

Evaluation records model/adapter, prompt and schema versions, dataset version,
parameters, score, cost, latency, and regressions. Release thresholds are explicit.
Live-provider tests are not required for ordinary unit tests.

## Replaceability

Every provider/tool port has a fake that implements the same contract. Contract
tests run against fakes and each supported adapter. Replacing an adapter in test
configuration must not change Executive, Planner, Orchestrator, Department, or
domain code.

## Architecture tests

CI rejects:

- forbidden module imports;
- provider SDKs outside adapters;
- plugin dependencies outside SDK/contracts;
- unowned or cross-module migrations;
- unversioned/breaking contract changes;
- missing tenant/correlation context at declared boundaries;
- direct repository access from AI/provider/plugin outsiders.

Where static enforcement is impossible, targeted integration tests and runtime
guards are mandatory.

## Scale acceptance

“Supports 1,000 agencies” requires an approved workload model: active users,
requests, workflows, steps, retained events, documents, embeddings, provider
limits, and hot-tenant distribution. Passing a user-count-only test is invalid.
