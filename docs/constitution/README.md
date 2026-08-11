# Rightjob AI OS Architecture Constitution

**Authority:** This directory is the normative architecture source of truth.  
**Status:** Owner decisions recorded and active architecture documents reconciled.  
**Implementation:** Governed by the final readiness verdict in
`docs/validation/02-final-architecture-readiness-report.md`.

If an older PRD, architecture document, schema, roadmap, sprint plan, prompt, or
code comment conflicts with this Constitution, stop work and open an Architecture
Decision Record (ADR). Do not choose silently.

## Reading order and file list

1. [Conflict Report](00-architecture-conflict-report.md)
2. [Vision and Product Boundary](01-vision-and-product-boundary.md)
3. [Architecture Principles](02-architecture-principles.md)
4. [Component Ownership](03-component-ownership.md)
5. [Module Boundaries](04-module-boundaries.md)
6. [Executive and Planning Rules](05-executive-and-planning-rules.md)
7. [Orchestration Rules](06-orchestration-rules.md)
8. [Department and Capability Standard](07-department-and-capability-standard.md)
9. [Plugin Contract](08-plugin-contract.md)
10. [Tool and Provider Standard](09-tool-and-provider-standard.md)
11. [Memory and Context Standard](10-memory-and-context-standard.md)
12. [Policy, Approval, and Security](11-policy-approval-and-security.md)
13. [Data Ownership and Persistence](12-data-ownership-and-persistence.md)
14. [Events, Observability, and Audit](13-events-observability-and-audit.md)
15. [Testing and Evaluation](14-testing-and-evaluation-standard.md)
16. [Definition of Done](15-definition-of-done.md)
17. [Architecture Review Checklist](16-architecture-review-checklist.md)
18. [Naming and Terminology](17-naming-and-terminology.md)
19. [Decision Log](18-decision-log.md)
20. [Prohibited Patterns](19-prohibited-patterns.md)
21. [Change Governance](20-change-governance.md)
22. [Responsibility Matrix](21-responsibility-matrix.md)
23. [Dependency Direction Diagram](22-dependency-direction-diagram.md)
24. [Request Lifecycle Diagram](23-request-lifecycle-diagram.md)
25. [External-Action Approval Lifecycle](24-external-action-approval-lifecycle.md)
26. [Architecture Review Summary](25-architecture-review-summary.md)

## Constitutional priority

1. Security, tenant isolation, legal obligations, and data integrity.
2. Explicit owner-approved ADRs.
3. This Constitution.
4. Approved product and architecture documents.
5. Module documentation and contracts.
6. Implementation details and prompts.

Lower levels cannot override higher levels.

## Mandatory working rule

Before implementation, complete the review template in
[16-architecture-review-checklist.md](16-architecture-review-checklist.md).
Status must be `approved`; `revise` or `blocked` prohibits implementation.

## Amendment rule

Constitutional changes require a conflict analysis, affected-owner review,
security/tenancy review where applicable, an ADR, and updates to every affected
normative document and enforcement check. Conversation approval alone is not a
durable amendment until recorded.
