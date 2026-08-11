# Component Ownership

An owner controls a responsibility’s rules and public contract. It does not
imply a separate deployment or permission to access another owner’s data.

| Component | Owns | Must not own |
|---|---|---|
| Executive AI | Conversation, intent clarification, explanations, progress summaries, result presentation | Decomposition, workflow state, policy, business rules, tools, persistence |
| Context Resolver | Reference identification, ranking, evidence, confidence | Planning, execution, policy |
| Planner | Typed plan proposal, task decomposition, capabilities, step dependencies | Execution, authorization, persistence, arbitrary tools |
| Policy Engine | Authorization, permissions, risk, budgets, quotas, approvals, restrictions | Execution, department rules, quality review |
| Department Registry | Manifests, discovery, activation, version pinning, capability metadata | Planning or execution |
| Workflow Compiler | Deterministic compilation and compatibility validation inside Orchestration | Independent workflow ownership |
| Orchestrator | Workflow lifecycle, schedule, coordination, retry, timeout, cancellation, compensation, pauses, progress, evidence | Domain rules, communication, vendor logic |
| Department | One business domain, its capabilities, deterministic domain rules and quality requirements | Cross-department work, user communication, direct provider choice |
| Capability | One typed operation, contracts, validation, requirements, risk, declared dependencies | Whole workflows, unrelated operations, vendor code |
| Tool Interface | Vendor-neutral external/technical contract | Policy, workflows, vendor code |
| Provider Adapter | Vendor authentication, mapping, normalized errors, metadata, usage/cost | Business rules, user communication, policy |
| AI Router | Eligible AI provider selection using declared requirements and policy constraints | Business decisions, decomposition, department selection |
| Working Memory | Current conversation and active-work context | Durable workflow authority |
| Episodic Memory | Historical conversations, meetings, work, decisions | Canonical Work records |
| Semantic Knowledge | Source-backed durable facts and knowledge representations | Duplicate canonical client/project records |
| Retrieval Service | Filtering, ranking, provenance, confidence, hybrid retrieval | Planning, policy, execution |
| Repository | Persistence port, aggregate load/save, owner transaction boundary, mapping | Business decisions, another module’s data |
| Database | Storage, constraints, transactions, indexes, RLS infrastructure | Application behavior |
| Validator | Deterministic schema, invariant, required-field, technical acceptance checks | Qualitative authorization |
| Reviewer | Typed qualitative assessment against declared criteria | Permission, policy bypass, state mutation, commit |
| Audit and Observability | Audit, logs, traces, metrics, correlation, evidence, usage, cost, failure visibility | Workflow ownership |

Canonical business records remain with their domain owner. Memory references and
derives knowledge from those records; it does not become a second system of
record. Usage measures consumption; Policy decides whether consumption is
allowed.

See [Responsibility Matrix](21-responsibility-matrix.md) for lifecycle-level
accountability.
