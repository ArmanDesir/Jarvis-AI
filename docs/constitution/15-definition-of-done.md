# Definition of Done

A feature or architecture change is complete only when all applicable items pass.

## Product and ownership

- Acceptance criteria and non-goals are documented.
- Exactly one module owns every rule, record, write, and event.
- The architecture review status is `approved`.
- No duplicate capability, department, repository, or workflow owner exists.

## Contracts and behavior

- Inputs, outputs, errors, versions, permissions, risks, dependencies, and
  failure behavior are typed.
- Retry, timeout, cancellation, compensation, reconciliation, and idempotency are
  defined where applicable.
- Deterministic business rules are in the owning code, not prompts.
- Provider fallback and degradation behavior is explicit.

## Security and tenancy

- Authentication, authorization, policy, approval, tenant isolation, data
  classification, retention, and secret handling are reviewed.
- External effects have pre-commit policy, idempotency, and audit evidence.
- Threat-model changes are resolved.

## Verification

- Required domain, contract, integration, workflow, security, architecture,
  evaluation, and end-to-end tests pass.
- Provider replaceability is demonstrated with a fake.
- Capacity impact is evaluated against the approved workload model.
- Accessibility requirements pass for user-facing work.

## Operations

- Correlation, logs, traces, metrics, usage, cost, evidence, alerts, and runbooks
  exist at the required boundaries.
- Migration, compatibility, rollback/roll-forward, and recovery are documented.
- Documentation and decision records are updated.

## Review

Product accepts the outcome; owning engineers accept operability; security accepts
material trust-boundary changes; architecture confirms constitutional compliance.
“Works in a demo” is not Done.
