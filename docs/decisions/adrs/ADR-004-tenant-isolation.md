# ADR-004: Tenant Isolation

**Status:** Accepted  
**Decision date:** 2026-07-28

## Decision

Every tenant-owned production table has non-null `workspace_id`, including child,
join, message, workflow, event, audit, memory/retrieval, artifact, approval,
external-operation, projection and security-sensitive tables.

Composite tenant-aware foreign keys prevent cross-workspace references. RLS is
enabled and forced for tenant-owned tables. Parent-join-only isolation is
prohibited. Exceptions are limited to truly global immutable reference data and
controlled offline migration staging.

CI must verify workspace columns, enabled/forced RLS, tenant-aware relationships,
table ownership, cross-tenant denial, background-job/retrieval isolation and
cache/object-key isolation.

## Consequences

Rows and indexes are larger, but tenant queries, jobs, audit, deletion/export and
future partitioning follow one enforceable rule.
