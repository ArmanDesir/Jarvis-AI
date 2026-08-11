# Product Requirements Document

**Product:** Rightjob AI OS  
**Status:** Architecture-reconciled draft; implementation not authorized  
**Audience:** Product, engineering, operations, security

## 1. Product definition

Rightjob AI OS is a multi-tenant SaaS operating system for digital agencies. A
user communicates with one Executive AI by chat or voice. The Executive owns
clarification and communication. Context Resolver resolves references, Planner
proposes typed plans, Policy governs permission, and Orchestrator coordinates
execution.

It is not a general-purpose chatbot and does not expose specialist agents to the
user.

## 2. Goals

- Provide one conversational control plane for agency work.
- Preserve context across conversations, clients, projects, and tasks.
- Delegate work through discoverable, replaceable department actions.
- Make every important action observable, auditable, and recoverable.
- Support human approval before consequential external actions.
- Isolate agency data and configuration in a multi-tenant system.
- Allow capabilities, providers, and departments to be added without modifying
  the Executive core.

## 3. Non-goals for MVP

- Fully autonomous financial transactions or contract execution.
- A no-code workflow builder.
- A marketplace for third-party plugins.
- Training proprietary foundation models.
- Replacing full CRM, accounting, or project-management products.
- Microservice-per-department deployment.

## 4. Personas

| Persona | Needs |
|---|---|
| Agency owner | Daily brief, prioritization, approvals, portfolio visibility |
| Operations manager | Workload, deadlines, exceptions, client coordination |
| Team member | Assigned tasks, evidence, status, clear handoffs |
| Agency administrator | Users, roles, providers, departments, policies |
| Auditor/support | Traceable decisions and safe diagnostic access |

The Executive is the only AI persona visible in the primary user experience.

## 5. MVP scope

### Executive experience

- Text conversations with streaming responses.
- Voice input/output behind provider-neutral interfaces.
- Daily brief generated from tasks, meetings, leads, and exceptions.
- Context resolution for recent clients, projects, conversations, and decisions.
- Plan preview and explicit approval when policy requires it.
- Progress timeline, cancellation, retry, and final delivery.

### Core operating system

- Agency workspaces, membership, roles, and tenant isolation.
- Client, project, task, meeting, file, SOP, brand, and decision records.
- Department registry and versioned Capability manifests.
- Dynamic department selection based on capabilities and policy.
- Durable workflow execution, retries, timeouts, and compensating actions.
- Human approval inbox.
- Audit log, tracing, usage, and cost records.

### Initial department plugins

1. **Website:** requirements, architecture, implementation task creation, QA.
2. **Marketing:** campaign strategy, social content, SEO briefs, reporting.
3. **Operations:** CRM lead follow-up drafting, email/calendar assistance.

Marketing solely owns Creative capabilities. Website owns information
architecture and UI implementation and consumes approved Marketing artifacts
only through Orchestrator.

## 6. Core journeys

### Execute a request

1. User submits text or voice.
2. Context Resolver resolves workspace and conversational context.
3. Planner produces a typed goal and proposed Capability graph.
4. Policy engine validates permissions, risk, budget, and approval requirements.
5. Orchestrator invokes only departments whose capabilities match the plan.
6. Outputs pass deterministic Validator checks, then optional qualitative
   Reviewer assessment. Reviewer cannot authorize or mutate workflow state.
7. Sensitive actions pause for approval.
8. Executive delivers a consolidated result with evidence and status.

### Continue prior work

1. User says, “Continue yesterday’s project.”
2. Resolver uses active conversation, recency, participants, project state, and
   semantic retrieval to rank candidates.
3. A high-confidence match continues; ambiguity produces one concise question.
4. The resolution and evidence are recorded for audit and future context.

### Daily brief

The Executive summarizes due and overdue work, meetings, unresolved approvals,
new leads, project risks, and recent failures. Every count links to its source.

## 7. Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | All business data is scoped to an agency workspace. |
| FR-02 | The Executive emits typed intents and plans, never raw tool execution. |
| FR-03 | Department capabilities are discovered from enabled manifests. |
| FR-04 | Workflows are versioned and durable across process restarts. |
| FR-05 | External side effects are idempotent and policy checked. |
| FR-06 | Approval can be required by action, role, value, client, or workspace. |
| FR-07 | Users can inspect plan, progress, evidence, result, and failure reason. |
| FR-08 | Memory records provenance, scope, retention, and sensitivity. |
| FR-09 | Users can correct or delete eligible remembered information. |
| FR-10 | Provider failures can be retried or routed to configured fallbacks. |
| FR-11 | Every mutation and tool invocation produces an audit event. |
| FR-12 | Departments can be enabled, disabled, and version-pinned per workspace. |

## 8. Non-functional requirements

- **Availability:** 99.9% monthly target after general availability.
- **Durability:** acknowledged tasks are not lost during deploys or worker failure.
- **Latency:** chat acknowledgement under 1 second p95; first streamed token under
  3 seconds p95 excluding provider degradation.
- **Scale planning:** review boundaries against the 1,000-agency expected-normal
  floor. Treat 10,000 workspaces as a long-term projection, not achieved capacity.
- **Security:** least privilege, encryption in transit/at rest, tenant isolation,
  secret management, signed webhooks, and immutable security audit trail.
- **Accessibility:** WCAG 2.2 AA for core web workflows.
- **Observability:** correlated logs, metrics, traces, token/cost usage, and SLOs.
- **Portability:** core domain cannot import vendor SDKs.

## 9. Success metrics

- At least 70% of supported requests complete without manual re-planning.
- 100% of consequential effects receive Policy evaluation; required human
  approvals are measured separately.
- Fewer than 1% of completed workflows require recovery from duplicate effects.
- Median time from request to approved plan is under 30 seconds.
- At least 50% of weekly active agencies use the daily brief.
- User correction rate for automatic project/context resolution is under 5%.

## 10. Risks and controls

| Risk | Control |
|---|---|
| Hallucinated action or context | Typed outputs, retrieval evidence, confidence gate |
| Cross-tenant data leak | Database RLS, scoped repositories, isolation tests |
| Unsafe external action | Policy engine, approval gates, least-privilege credentials |
| Duplicate email/post/update | Idempotency keys and recorded external operation IDs |
| Runaway cost | Per-workspace budgets, quotas, model routing, usage ledger |
| Prompt injection in files/web | Untrusted-content labels, tool allowlists, sandboxing |
| Plugin compromise | Trusted first-party Department plugins only; third-party executable plugins prohibited in MVP |

## 11. MVP acceptance

MVP is accepted when a test workspace can complete one end-to-end workflow in
each initial department, survive worker restart, pause and resume on approval,
resolve a prior project with evidence, enforce tenant isolation, and expose a
complete audit timeline.

## 12. Recorded architecture decisions

Owner decisions are recorded in `docs/decisions/adrs/`. Managed Temporal, Clerk,
and `pgvector` are proof authorizations only; Redis is deferred. ADR-008 assigns
Work as canonical owner of client/contact, contractual, and project-delivery
preferences, and Identity/Tenancy as owner of workspace-member communication
preferences. Memory holds only source-linked retrieval representations.
