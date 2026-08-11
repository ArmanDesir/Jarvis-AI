# Technical Architecture

**Status:** Architecture-reconciled draft; implementation not authorized

## 1. Architecture decision

Build a **modular monolith with durable workers**. The API, domain modules, and
plugin SDK share one versioned codebase; web, API, and worker processes deploy
independently. This gives clear boundaries and horizontal scaling without the
failure modes and operational cost of premature microservices.

Split a module into a service only when independent scaling, security isolation,
release cadence, or ownership is demonstrated.

## 2. System context

```text
Web / Voice Client
       |
   FastAPI Gateway ---- Identity Adapter / Webhooks
       |
 Executive Application Service
       |          \
 Context/Memory   Policy & Approval
       |              |
 Planner ---- Department Registry
       |              |
       +---- Workflow Engine Port ----+
                    |             |
              Core Workers   Plugin Workers
                    |             |
             Provider Adapters / External Systems
                    |
     PostgreSQL / Retrieval Adapter / Object Storage
```

The client never invokes a department or provider directly.

## 3. Bounded modules

| Module | Responsibility |
|---|---|
| Identity | User identity mapping, workspace membership, roles |
| Executive | Conversations, clarification, response composition, daily brief |
| Context | Reference resolution, retrieval evidence, confidence |
| Planning | Typed plan proposals and plan validation |
| Orchestration | Plans, runs, steps, schedules, retry/cancel/resume |
| Departments | Registry, manifests, capability/action resolution |
| Policy | Authorization, budgets, risk, approval decisions |
| Memory | Extraction, retrieval, ranking, retention, corrections |
| Work | Clients, projects, tasks, meetings, decisions |
| Content | Generic files, SOP sources, unclassified source assets |
| Marketing | Brand voice, visual identity, Creative capabilities |
| Integrations | Credentials, connections, inbound/outbound adapters |
| Audit | Append-only audit, tool-call evidence, compliance exports |
| Billing/Usage | Metering and quotas; payment billing is post-MVP |

Modules communicate in-process through application ports and across durable
boundaries through commands, queries, versioned events, and a Workflow Engine
Port. Direct cross-module table reads and writes are forbidden.

## 4. Executive request contract

The AI returns validated structured data:

```json
{
  "intent": "execute_work",
  "goal": "Create and schedule five Facebook posts",
  "context_refs": [{"type": "client", "id": "uuid"}],
  "required_capabilities": ["social.strategy", "social.copy", "social.publish"],
  "constraints": {"deadline": null, "channels": ["facebook"]},
  "confidence": 0.93
}
```

The planner converts this to a typed directed acyclic graph. It may choose only
currently enabled Capabilities from the registry. Schema validation, policy, budgets,
and dependency checks run before execution. The model cannot call arbitrary
Python functions, URLs, or credentials.

## 5. Department plugin contract

Each plugin publishes a versioned manifest:

```yaml
id: marketing
version: 1.0.0
name: Marketing Department
capabilities:
  - id: social.create_campaign
    input_schema: schemas/social-campaign-input.json
    output_schema: schemas/social-campaign-output.json
    handler: marketing.activities.create_campaign
    risk: low
    permissions: [content:write]
    dependencies: []
  - id: social.publish
    input_schema: schemas/social-publish-input.json
    output_schema: schemas/social-publish-output.json
    handler: marketing.activities.publish
    risk: high
    permissions: [social:publish]
    approval: policy
dependencies:
  services: [llm, social-provider]
```

The SDK supplies manifest validation, typed Capability context, cancellation,
heartbeat, idempotency, secrets references, logging, and result envelopes.
Handlers contain no orchestration logic. Workflows compose Capabilities,
not by importing plugin internals.

“No hardcoded workflows” means business processes are versioned declarative
workflow definitions and plans—not unvalidated model improvisation. The engine
and safety invariants remain code.

## 6. Orchestration

Orchestration depends on a durable Workflow Engine Port. Managed Temporal is the
approved adapter after the Phase 2.5 proof of approval waits, restart recovery,
retries, cancellation, idempotent effects, versioning, uncertain outcomes, and
independent workers. Temporal remains infrastructure behind the provider-neutral
port. Self-hosted production Temporal is prohibited.

Core workflow:

1. Resolve and snapshot context.
2. Build and validate plan.
3. Evaluate policy and reserve budget.
4. Execute ready steps with bounded concurrency.
5. Persist evidence and emit progress.
6. Run deterministic validation and optional AI review.
7. Wait for approval when required.
8. Commit external effect, compensate where supported, and deliver.

Workflow code must be deterministic. Network/database/model calls live in
activities. Each side effect uses a stable idempotency key derived from run and
step IDs. Workflow definitions are versioned; running instances stay compatible.

## 7. Events

Events use an envelope:

```json
{
  "event_id": "uuid",
  "event_type": "workflow.step.completed.v1",
  "occurred_at": "ISO-8601",
  "workspace_id": "uuid",
  "actor": {"type": "service", "id": "actual-producing-service"},
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "payload": {}
}
```

Domain changes and outbox events commit in one PostgreSQL transaction. A relay
publishes them to interested consumers. Temporal signals handle live workflow
control; WebSockets carry user-facing projections. Kafka is not needed initially.

## 8. Memory architecture

Memory is not raw chat stuffed into prompts. It has four layers:

- **Working:** current turn, plan, and active run.
- **Episodic:** conversations, meetings, completed work, and decisions.
- **Semantic:** clients, brands, SOPs, preferences, facts, and embeddings.
- **Retrieval:** source-backed SOPs and playbooks only; Orchestration owns
  workflow definitions and Policy owns policies.

Retrieval filters by workspace, permissions, subject, recency, validity, and
sensitivity before hybrid keyword/vector ranking. Returned memories include
provenance and confidence. A compaction job summarizes old conversations while
retaining source links. Corrections supersede records; retention jobs delete
eligible data and derived embeddings.

Canonical preference routing is deterministic: Work owns client/contact,
contractual/engagement, and project-delivery preferences; Identity/Tenancy owns
workspace-member communication preferences; Marketing owns brand/visual
preferences; Website owns website functional/structure preferences. Corrections
go to the owner first and propagate to Memory through versioned events.

Start with PostgreSQL full-text and entity retrieval. A limited `pgvector` proof
may proceed; adoption requires measured accuracy, latency, isolation, deletion,
and cost evidence.

## 9. Security and tenancy

- Every tenant-owned table, including children and joins, includes non-null
  `workspace_id`, tenant-aware composite foreign keys, and enabled/forced RLS.
- A provider-neutral identity adapter maps external subjects to internal users.
  Clerk is only an authorized proof against Auth.js.
- RBAC controls broad access; policy rules evaluate resource, action, risk,
  workspace settings, and approval.
- Provider credentials are encrypted references in a secret manager, never model
  context or plugin configuration.
- Webhooks use signature verification, timestamp tolerance, replay protection,
  and idempotency.
- Untrusted content is marked and cannot alter system/tool policy.
- Support access is time-bound, reasoned, and audited.

## 10. Provider abstraction

Domain ports define model inference, embeddings, STT, TTS, email, calendar,
social, CRM, storage, and notifications. Adapters own vendor SDKs and normalize
errors, usage, and capabilities. Provider selection is configuration plus policy.

Avoid an abstraction that pretends all models are identical. The AI port exposes
capability metadata (structured output, tools, context window, streaming) so
routing can fail clearly.

## 11. Realtime and voice

- WebSockets stream conversation tokens and run events; reconnect uses a cursor.
- Durable state remains in PostgreSQL/Temporal, never only in a socket.
- Browser audio streams to an STT adapter; finalized transcripts enter the same
  command path as chat.
- TTS consumes the final or sentence-buffered Executive response.
- Transcripts and audio retention are independently configurable.

## 12. Deployment and operations

Containers: `web`, `api`, `worker-core`, optional `worker-plugin-*`, `outbox-relay`,
and scheduled maintenance workers. Managed PostgreSQL and provider-neutral
S3-compatible storage and Managed Temporal are accepted. Redis is deferred and
never authoritative.

GitHub Actions runs formatting, type checks, unit tests, contract tests, migration
checks, container scans, and integration tests. Deployments use expand/migrate/
contract database changes and Temporal worker versioning.

## 13. Testing strategy

- Domain unit tests for invariants and policy.
- JSON Schema contract tests for every action.
- Repository integration tests against real PostgreSQL with RLS.
- Workflow-engine contract, restart/replay where supported, and failure-injection tests.
- Provider adapter tests with recorded/fake boundaries.
- End-to-end tests for request, approval, restart, cancellation, and isolation.
- AI evaluations for intent, routing, context resolution, and safe refusal.

AI evaluation scores gate prompt/model releases; ordinary unit tests must not
depend on live AI providers.

## 14. Architecture fitness rules

- Core/domain packages cannot import vendor SDKs or framework modules.
- A plugin cannot query another plugin’s tables.
- All external effects require idempotency keys and audit evidence.
- No action executes without workspace, actor, authorization, and correlation.
- Every new event and Capability schema is versioned and backward-compatible.
- A workflow cannot be marked complete until validation and required approvals
  have passed.
