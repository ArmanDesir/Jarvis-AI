# Decision Log

This summary does not replace the ADRs in `docs/decisions/adrs/`. Proof
authorization permits evaluation only; it does not adopt the evaluated
technology for production.

| ID | Decision | Status | Rationale / approval needed |
|---|---|---|---|
| D-001 | Constitution is the normative architecture source | Adopted for this documentation phase | Prevent session drift |
| D-002 | Start with a modular monolith and independently scalable API/worker processes | Accepted | ADR-001 |
| D-003 | Orchestrator coordinates; capabilities execute domain operations | Adopted | Removes duplicate execution ownership |
| D-004 | Workflow Compiler is logical and belongs to Orchestration | Adopted | Avoids a second workflow owner/service |
| D-005 | Canonical public operation term is Capability, not Action | Adopted | Removes duplicate terminology |
| D-006 | Workflow engine selection | Accepted | Managed Temporal adopted after the completed Phase 2.5 proof; provider-neutral orchestration boundary retained. ADR-001 |
| D-007 | PostgreSQL is primary storage | Accepted | Managed PostgreSQL, forced RLS. ADR-001/004 |
| D-007A | `pgvector` semantic retrieval | Proof authorized | Adoption requires measured accuracy, latency, isolation, deletion, and cost. ADR-001 |
| D-008 | Identity provider | Proof authorized | Compare Clerk with Auth.js; internal IDs remain provider-neutral. ADR-001 |
| D-009 | Redis | Deferred | Add only for measured distributed ephemeral needs; never authoritative. ADR-001 |
| D-010 | S3-compatible object storage | Accepted | Provider/region/retention/security configuration remains separate. ADR-001 |
| D-011 | Trusted first-party Department plugins only in MVP | Accepted | Third-party executable plugins prohibited. ADR-002 |
| D-012 | AI routing is capability- and policy-based | Adopted | Prevents vendor/model hardcoding |
| D-013 | PostgreSQL outbox precedes Kafka | Adopted as constraint | Kafka needs measured justification |
| D-014 | Domain modules own canonical records; Memory owns indexed/derived representations | Accepted | ADR-008 |
| D-015 | 100% of consequential effects receive policy evaluation | Adopted | Corrects unsafe 95% metric |
| D-016 | Every tenant-owned production table has `workspace_id` and forced direct RLS | Accepted | ADR-004 |
| D-017 | MVP ships reviewed built-in workflow definitions only | Accepted | ADR-005 |
| D-018 | Website, Marketing, Operations; Marketing solely owns Creative capabilities | Accepted | ADR-002 |
| D-019 | Four-level default risk and approval matrix | Accepted | ADR-003 |
| D-020 | 1,000-agency review floor and 10,000-workspace projection | Accepted as planning assumptions | Not achieved capacity. ADR-006 |
| D-021 | Reviewer revision governance | Accepted | Two automated cycles, then `needs_human_review`. ADR-007 |
| D-022 | Canonical preference taxonomy | Accepted | Work owns client/contact, contractual, and project-delivery preferences; Identity/Tenancy owns member communication preferences. ADR-008 |
| D-023 | Workspace is the canonical MVP tenant and agency boundary | Accepted | No separate Tenant or Organization model. ADR-009 |

## ADR trigger

Create a full ADR for any new infrastructure, module/service boundary, data owner,
public contract, provider exception, security exception, or reversal of a
constitutional decision.
