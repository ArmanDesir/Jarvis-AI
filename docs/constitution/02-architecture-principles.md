# Architecture Principles

## Mandatory invariants

1. Modules may communicate only through published interfaces, commands, queries,
   or versioned events.
2. A module may not import another module’s internal implementation.
3. Each module owns its domain model, write operations, repositories, migrations,
   and events.
4. Cross-module database reads and writes are prohibited.
5. No AI component may directly write to the database.
6. AI output is an untrusted typed proposal until validated by deterministic
   application code.
7. No Department may invoke another Department directly.
8. Cross-department workflows are coordinated only by Orchestrator.
9. Plugins may depend only on Plugin SDK and published contracts.
10. Plugins must not know another plugin’s internal implementation.
11. Provider-specific code may exist only inside Provider Adapters.
12. Prompts must not contain authoritative business rules.
13. Prompts must not know SQL, ORM models, table names, internal API endpoints,
    secrets, or infrastructure details.
14. Business rules live in deterministic code owned by the appropriate domain or
    Capability.
15. External effects must use idempotency keys.
16. External effects must create audit evidence.
17. High-risk or irreversible actions must pass Policy and approval checks before
    commitment.
18. Policy must run before execution and again before consequential commitment
    when risk or context may have changed.
19. Deterministic validation must happen before AI-based review.
20. Reviewers cannot approve permissions or bypass Policy.
21. Workflow definitions, Capability contracts, APIs, and events are versioned.
22. Provider outputs must be schema-validated.
23. Memory retrieval is workspace-scoped, permission-filtered, source-backed, and
    confidence-aware.
24. Every request, workflow, step, tool call, and external effect has a
    correlation ID.
25. Replaceability is demonstrated through contract tests and fake adapters.
26. Architecture boundaries are enforced in CI, not only documented.
27. Interfaces are required at module and external-system boundaries; unnecessary
    interfaces inside a cohesive private implementation are avoided.
28. Prefer the simplest architecture satisfying current verified requirements.
29. Microservices, Kafka, separate vector databases, and third-party executable
    plugin marketplaces remain deferred until measurable requirements justify
    them.
30. No implementation begins while ownership conflicts or architecture blockers
    remain unresolved.

## Design rules

- Keep one authoritative owner for every decision and record.
- Prefer composition over inheritance.
- Keep domain behavior cohesive and vendor-free.
- Fail closed when permissions, tenant, schema, provider eligibility, or outcome
  certainty is unknown.
- Make state durable before acknowledging durable work.
- Treat all external content and AI/provider output as untrusted input.
- Optimize measured bottlenecks; do not distribute speculative ones.

## Enforceability

Each invariant must map to one or more of: type/schema validation, dependency
checks, database permissions/RLS, contract tests, integration tests, workflow
tests, security tests, evaluation gates, or runtime policy. A rule without a
planned enforcement mechanism is an unresolved architecture task.
