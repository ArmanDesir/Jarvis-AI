# Change Governance

## Change classes

| Class | Examples | Approval |
|---|---|---|
| Routine | Internal implementation within an approved contract | Module owner; CI |
| Material | New capability, event, provider adapter, schema owner change, policy behavior | Architecture review and affected owners |
| Constitutional | New module/service, ownership transfer, invariant exception, new infrastructure, prohibited-pattern exception | CTO/owner-approved ADR plus security/operations review |

## Proposal requirements

Every material proposal states the problem, verified requirement, owner, affected
modules, alternatives, simplest solution, contracts, data, security/tenancy,
scale model, failure behavior, observability, tests, migration, rollback, and
unresolved decisions. Complete the Architecture Review Checklist.

New infrastructure additionally documents:

- why existing components cannot satisfy the measured need;
- operating and on-call cost;
- migration and rollback impact;
- security and data-residency impact;
- simpler alternatives and why they fail.

## Decision process

1. Search existing capabilities, modules, contracts, and ADRs.
2. Stop on duplicate or unclear ownership.
3. Publish conflict and proposed correction.
4. Obtain required owners/security/operations approval.
5. Record ADR and update Constitution/contracts/diagrams.
6. Add or update CI enforcement before implementation depends on the boundary.
7. Implement only after review status is `approved`.

## Compatibility and deprecation

Public contracts use semantic/API/event versioning. Breaking changes require a
migration plan, compatibility window, telemetry, rollback, and removal criteria.
Running workflows and pinned plugins cannot be abandoned.

## Exceptions

Exceptions are narrow, time-bound, owned, risk-assessed, audited, and have an
expiry/remediation plan. “Temporary” without a date and owner is not an exception.
Security and tenant-isolation invariants cannot be waived by ordinary feature
approval.

## Drift control

Every future AI coding session must read this README, Conflict Report, Decision
Log, relevant standards, and repository-local agent guidance before proposing
work. Reviews cite Constitution sections. CI and code review templates link the
same checklist. If code and Constitution disagree, implementation stops.
