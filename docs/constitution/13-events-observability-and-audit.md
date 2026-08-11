# Events, Observability, and Audit

## Event standard

Events are immutable facts named in past tense and versioned independently. The
envelope contains event ID, type/version, occurred time, workspace, actor,
correlation ID, causation ID, producer, schema version, sensitivity, and typed
payload.

`actor` identifies the actual initiator or executor and distinguishes user, AI,
system, service, and provider actors. Causation links delegated work; it must not
misattribute a provider or service action to the Executive.

Producers own event semantics and compatibility. Consumers are idempotent and
cannot rely on delivery order across aggregate streams. Breaking changes require
a new version and migration/dual-publish plan.

## Correlation

One correlation chain must cover inbound request, conversation message, plan,
workflow, step, capability, tool call, provider request, external operation,
approval, result, and Executive response. Child work also records causation.
Missing correlation is a production-blocking defect.

## Audit

Audit/Observability owns the audit-evidence schema, acceptance policy, retention,
and append-only audit service. The module performing an operation owns production
of truthful evidence; Orchestrator owns workflow execution evidence. Audit
records observe and never become writable substitutes for source aggregates.

Audit is append-only and records who/what acted, workspace, action, resource,
policy/approval references, before/after summary where safe, evidence reference,
outcome, correlation, and time. It must cover mutations, sensitive reads, policy
decisions, approvals, plugin activation, tool calls, external effects, support
access, configuration, and security events.

Audit failure blocks consequential commitment unless an owner-approved resilient
buffer preserves the record durably. Audit cannot contain secrets or unrestricted
sensitive payloads.

## Observability

- Structured logs describe operational facts, not business authority.
- Distributed traces connect interfaces and provider calls.
- Metrics cover latency, throughput, saturation, queue age, error classes,
  retries, approval wait, provider health, tokens, cost, and tenant fairness.
- Execution evidence links inputs/outputs by safe hashes or controlled artifacts.
- Alerts map to owned runbooks and SLOs.

Workspace and global views must prevent cross-tenant leakage. High-cardinality
identifiers are controlled; sensitive values are not metric labels.

## Scale and retention

Audit, events, messages, and usage are high-growth data. Partitioning, archiving,
and retention are driven by measured volume and legal requirements. Kafka is not
introduced while PostgreSQL outbox plus current consumers meet verified
throughput and recovery needs.
