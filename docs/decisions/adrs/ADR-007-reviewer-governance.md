# ADR-007: Reviewer Governance

**Status:** Accepted  
**Decision date:** 2026-07-28

## Decision

Reviewer evaluates quality only and returns structured scores, reasons and
evidence. It cannot approve permission, call Tools, mutate workflow state,
override Policy or choose external-effect approvers.

Orchestrator owns revision execution and state. A quality gate allows at most two
automated revision cycles. After two unsuccessful cycles, Orchestrator enters
`needs_human_review`; no further revision occurs without an authorized person or
approved workflow rule. The user or authorized Department owner may direct
resume, revision, acceptance or termination through an application command.

Attempt count is durable. Artifact/criteria versions, scores, reasons, evidence,
model/adapter metadata, cost and Orchestrator decisions are retained.

## Consequences

Provider transport retries use a separate bounded retry budget and do not reset
the content-revision count. Infinite qualitative loops are prohibited.
