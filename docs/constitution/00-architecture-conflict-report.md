# Architecture Conflict Report

> Historical review record. Owner decisions and later resolution status are
> recorded in `18-decision-log.md`, `docs/decisions/adrs/`, and
> `docs/validation/01-architecture-simulation-report.md`. Findings below are
> preserved rather than silently rewritten.

**Status:** Authoritative audit; corrections are proposed, not silently applied  
**Reviewed:** repository `README.md` and `docs/01` through `docs/07`  
**Implementation gate:** Blocked until owner decisions in this report are resolved

## Classification

- **Automatic:** clarification preserves approved product intent, removes an
  ownership overlap, or adds a missing safety invariant.
- **Owner approval:** changes product scope, technology, operating cost, risk
  appetite, or a previously listed approval decision.

## Conflicts

| ID | Conflicting statements and affected documents | Why this conflicts | Recommended correction | Automatic? | Owner approval? |
|---|---|---|---|---|---|
| C-01 | PRD says the Executive “turns requests into governed plans” and “coordinates execution”; FR-02 says it emits plans. Technical Architecture gives planning to Planner and execution to Orchestration. | Executive, Planner, and Orchestrator have overlapping authority. | Executive clarifies intent and communicates. Planner proposes typed plans. Orchestrator coordinates execution. | Yes | No |
| C-02 | PRD journey resolves context in Executive. Architecture describes Context/Memory but no Context Resolver owner. | Context ranking could drift into Executive prompts or Memory storage logic. | Make Context Resolver a public application service using Retrieval Service; it returns evidence and confidence. | Yes | No |
| C-03 | Technical Architecture calls plugin operations both `actions` and `capabilities`; schema uses `action_definitions`; PRD uses department actions. | Two names for one public execution contract create duplicate registries and APIs. | Canonical term is **Capability**. “Action” is reserved for policy/audit verbs and may remain only as a legacy schema name until migrated. | Yes | No |
| C-04 | Technical Architecture gives Memory a “Procedural” layer containing workflow definitions, policies, and playbooks. Current ownership rules prohibit Memory from owning workflow or policy state. | Memory would become a second Orchestrator and Policy store. | Remove procedural workflow/policy ownership. SOPs/playbooks remain canonical Content/Work knowledge exposed to Semantic Knowledge; workflows belong to Orchestration and policies to Policy. | Yes | No |
| C-05 | Integrations owns adapters; Provider abstraction groups LLM, speech, email, CRM, social, storage; no AI Router exists. | Tool contracts, vendor adapters, and AI routing have unclear boundaries. | Tool Interface is the vendor-neutral port. Provider Adapter implements a tool or AI port. AI Router selects eligible AI adapters only. | Yes | No |
| C-06 | Provider selection is described as “configuration plus policy.” The required model gives AI Router selection ownership and Policy eligibility authority. | Selection and authorization may be implemented twice. | Policy supplies constraints; AI Router ranks only eligible providers. Router cannot relax policy or capability requirements. | Yes | No |
| C-07 | Folder structure centralizes all migrations under `db/`; ownership rules say each module owns its migrations and data. | A shared directory can become shared ownership and cross-module schema edits. | Physical migrations may remain centrally executed, but every migration must declare one owning module; module manifests and CI enforce ownership. Move files under module namespaces when implementation begins. | Yes | No |
| C-08 | Folder structure allows “cross-module reads use queries or projections”; architecture prohibits only direct cross-module writes. New invariants prohibit both database reads and writes. | Direct reads couple consumers to another module’s schema. | Cross-module reads use the owner’s published query interface, event-built consumer projection, or approved read model contract—never the owner’s tables. | Yes | No |
| C-09 | Work owns clients/projects/tasks/decisions; Content owns SOPs/brands/files; Memory “owns” clients, brands, SOPs, preferences, and facts. Database schema stores all together without explicit owners. | Canonical records could be duplicated as memory records. | Work/Content own canonical entities. Semantic Knowledge owns derived, source-backed knowledge representations and references, not duplicate authoritative records. | Yes | No |
| C-10 | Billing/Usage owns metering and quotas; Policy owns budgets and quotas in the required ownership model. | Quota decisions could live in two modules. | Usage records measurements and cost. Policy owns enforcement decisions, reservations, budgets, and quotas using Usage queries. | Yes | No |
| C-11 | PRD success metric allows 95% of consequential effects to follow approval policy. Required invariants require every high-risk effect to pass policy/approval. | A 5% safety bypass is unacceptable and contradicts the mandatory gate. | Change architectural compliance target to 100% policy evaluation; product metrics may separately measure how often human approval is required. | Yes | No |
| C-12 | PRD allows provider failures to route to fallbacks; provider abstraction does not prohibit weaker fallback. | Silent fallback could violate privacy, schema, quality, geography, or cost constraints. | Fallback is allowed only when the candidate satisfies every declared capability and policy constraint; otherwise fail explicitly. | Yes | No |
| C-13 | “No hardcoded workflows” is described as declarative workflows, while Temporal workflow code must be deterministic. | Read literally, it would prohibit the workflow engine and safety logic from code. | Business workflow definitions are versioned data/contracts compiled deterministically. Engine semantics, invariants, and safety rules remain code. | Yes | No |
| C-14 | Reviewer is mentioned as an optional AI critic, but Validator and Reviewer ownership and authority are not defined. | An AI reviewer could accidentally authorize, persist, or mutate a run. | Validator performs deterministic checks first. Reviewer emits a typed assessment only. Policy/authorized humans approve; Orchestrator alone changes workflow state. | Yes | No |
| C-15 | Core workflow shows policy once before execution and approval near completion. Required lifecycle requires policy again before consequential commitment when context changes. | Long-running workflows can outlive permissions, budgets, content, or credentials. | Evaluate policy before execution and re-evaluate immediately before consequential commitment where risk/context can change. | Yes | No |
| C-16 | Plugin risk control says “manifest validation and process isolation first”; deployment says plugin workers are optional. | The isolation guarantee is stronger than the deployment decision. | Trusted first-party plugins may share a worker with strict contracts. Untrusted/external executable plugins remain prohibited until a separately approved isolation model exists. | Yes | No |
| C-17 | Database schema gives `plans.approved_at` while approvals are separately modeled per workflow/step. | “Plan approval” and “external-action approval” can be confused or bypass each other. | Define distinct `plan_acceptance` and `action_approval` concepts. Plan acceptance never substitutes for a policy-required commitment approval. | Yes | No |
| C-18 | Architecture requires every domain row to contain `workspace_id`, but child tables such as `message_parts` and `memory_sources` omit it in the logical schema. | RLS and tenant-safe indexing become inconsistent or depend entirely on joins. | Decide whether every tenant child row carries `workspace_id` or whether narrowly approved parent-join RLS is allowed. Prefer explicit workspace IDs for high-volume/security-critical children. | No | Yes |
| C-19 | PRD targets 10,000 workspaces; review checklist requires at least 1,000 agencies. | Not a direct contradiction, but capacity acceptance is ambiguous. | Use 1,000 agencies as the mandatory feature review floor and 10,000 workspaces as the product architecture target; define workload assumptions before load-test approval. | Yes | No |
| C-20 | README proposes Redis, Temporal Cloud, Clerk, and S3-compatible storage while PRD lists core choices as awaiting approval. | Proposed infrastructure may be mistaken for an accepted decision. | Keep all as candidates in the Decision Log until owner approval. No implementation may assume them. | No | Yes |
| C-21 | API exposes creating and publishing workflow definitions; MVP non-goal excludes a no-code workflow builder. | Public authoring may create a workflow product surface earlier than intended. | Limit workflow-definition write APIs to internal/admin use in MVP, or defer them. Workspace users consume approved definitions. | No | Yes |
| C-22 | Initial departments include Website, Marketing, Operations; Creative is embedded as capabilities in Website/Marketing. | Brand and graphic design ownership could be duplicated across two departments. | Define a capability ownership map before implementation. Extract Creative only when one cohesive owner is needed; do not duplicate creative capabilities. | No | Yes |

## Missing rules added by the Constitution

- Command classification and a deterministic fast path that can bypass AI.
- AI Router ownership and capability-based provider selection.
- Explicit module-owned writes, migrations, repositories, and events.
- Free-form agent-to-agent communication prohibition.
- Correlation propagation across request, workflow, step, tool, and effect.
- Commit-time policy re-evaluation and approval freshness.
- Failure taxonomy, cancellation, compensation, and uncertain-outcome handling.
- Architecture tests and CI enforcement rather than documentation-only rules.
- Data sensitivity, retention, secret redaction, and support-access constraints.
- Load assumptions, noisy-neighbor controls, bounded concurrency, and quotas.

## Rules not enforceable by prose alone

These require implementation and CI controls before production:

- Import/dependency boundaries.
- Module migration and table ownership.
- Cross-module database-access prohibition.
- Provider SDK location.
- Schema/event/API compatibility.
- Plugin dependency isolation.
- Tenant isolation and RLS.
- Correlation and audit completeness.
- Prompt content scanning and prompt-to-tool restrictions.
- Fake-adapter replaceability.

The Constitution defines the required checks; it does not falsely claim they
exist yet.

## Complexity review

The modular monolith, PostgreSQL outbox, and PostgreSQL hybrid retrieval are the
simplest current choices. Microservices, Kafka, a separate vector database,
multi-region active-active, a visual workflow builder, and an executable plugin
marketplace remain deferred. A separate Workflow Compiler is a logical component
inside Orchestration, not a deployment unit. Memory layers are logical
responsibilities, not mandatory services.

## Scale risks for many agencies

- Missing workload assumptions can make “10,000 workspaces” meaningless.
- Hot tenants can exhaust worker slots or provider budgets without quotas and
  fair scheduling.
- Large audit, event, message, and embedding tables need retention/partition
  plans based on measurements.
- Provider rate limits require per-workspace and global backpressure.
- WebSocket fan-out must be projection-based; sockets cannot be durable state.
- RLS mistakes and unscoped caches can create cross-tenant leaks.
- Long workflows need version compatibility and deterministic replay.

## Owner decisions required

1. Approve the initial deployment baseline: Temporal, Clerk, PostgreSQL with
   `pgvector`, Redis scope, and S3-compatible storage.
2. Approve the initial departments and the home of creative capabilities.
3. Approve the default high-risk action and approval matrix.
4. Choose the tenant-column strategy for child tables.
5. Decide whether workflow-definition authoring is internal-only or deferred.
6. Approve the target workload assumptions used to validate 1,000 and 10,000
   agency scale.

Until these are decided, the Constitution is authoritative for boundaries, but
application implementation remains blocked.
