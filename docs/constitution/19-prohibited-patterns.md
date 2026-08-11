# Prohibited Patterns

The following block approval unless an explicit constitutional amendment applies:

- Free-form agent-to-agent conversations.
- Departments or plugins calling other departments/plugins.
- Prompts acting as workflow engines.
- Prompts containing authorization, approval, retention, pricing, or other
  authoritative business rules.
- Prompts knowing SQL, ORM models, tables, internal endpoints, secrets, or
  infrastructure details.
- AI-generated SQL executed directly.
- AI-generated code executed without an approved sandbox and policy.
- AI, Reviewer, or Provider mutating workflow state or database records directly.
- Shared mutable global business state.
- Cross-tenant retrieval, caches, projections, logs, or evaluation data.
- Cross-module database reads or writes.
- Provider SDKs in domain, capability, workflow, Executive, or tool-contract code.
- Tools containing business rules.
- Repositories containing business decisions.
- Duplicate client, project, task, contact, lead, brand, SOP, or decision systems
  of record across departments.
- Unversioned events, APIs, workflow definitions, or capability contracts.
- Untyped capability or provider inputs/outputs.
- External effects without idempotency and audit evidence.
- Workflow state stored only in process memory, cache, or WebSockets.
- Reviewer models authorizing or bypassing policy.
- Silent fallback to a provider that misses any mandatory requirement.
- Publishing, sending, deleting, purchasing, deployment, or financial action
  without applicable policy and approval checks.
- Arbitrary network, shell, filesystem, credential, or code access exposed to AI.
- Plugins importing other plugins or non-public module internals.
- New architectural layers, services, databases, queues, or buses without an
  approved need and ADR.
- Interfaces between private collaborators solely to satisfy a slogan when no
  boundary or replacement exists.
