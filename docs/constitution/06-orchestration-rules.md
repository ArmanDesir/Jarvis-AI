# Orchestration Rules

## Ownership

The Orchestration module owns plan persistence after validation, Workflow
Compiler, workflow definitions, runs, steps, schedules, retries, timeouts,
cancellation, compensation, approval pauses, progress, and execution evidence.

It coordinates execution; Department Capabilities perform business operations.

## Workflow Compiler

The compiler is a deterministic application component inside Orchestration. It
converts a validated typed plan into a versioned executable definition. It checks
schemas, capability versions, dependencies, policy checkpoints, cancellation,
retry, timeout, compensation, and compatibility. It is not a separate service or
workflow owner.

## Workflow requirements

- Definitions and running instances are versioned and replay-compatible.
- Durable work is persisted before acknowledgement.
- Network, database, model, and provider calls occur outside deterministic
  workflow logic through activities/interfaces.
- Every step has bounded input/output, timeout, retry eligibility, cancellation
  semantics, and a stable correlation chain.
- External effects use operation-scoped idempotency keys.
- Parallelism is bounded per workflow, workspace, provider, and platform.
- Retries use normalized failure categories and cannot retry permanent failures.
- Unknown provider outcomes enter reconciliation; they are not blindly retried.

## Failure states

Supported classes are validation, authorization, approval denied/expired,
transient dependency, rate limited, permanent provider, timeout, cancelled,
compensation failed, uncertain external outcome, incompatible version, quota,
and internal defect.

The Orchestrator may commit, retry, wait, compensate, reconcile, cancel, or fail
only according to the compiled definition and current policy. Silent partial
success is prohibited.

## Hardcoded workflow rule

Business process composition is represented by versioned plan/workflow contracts
and compiled deterministically. Engine semantics and safety invariants remain
code. Prompts cannot act as workflow engines, invent runtime transitions, or
override a compiled definition.

## Cross-department coordination

Only the Orchestrator may sequence capabilities from multiple departments.
Departments exchange data only through typed step results and Orchestrator-owned
workflow state, never direct calls or free-form conversations.
