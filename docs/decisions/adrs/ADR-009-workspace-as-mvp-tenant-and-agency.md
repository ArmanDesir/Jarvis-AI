# ADR-009: Workspace as the MVP Tenant and Agency

**Status:** Accepted  
**Decision date:** 2026-08-06

## Context

Rightjob AI OS needs one canonical boundary for agency ownership, authorization,
tenant isolation, and data partitioning. Earlier implementation wording named
Tenant, Workspace, and Organization as separate models even though the approved
architecture defined only Workspace. Separate records would create ambiguous
ownership and competing tenant identifiers.

## Decision

For the MVP, Workspace is both the tenant boundary and the agency account.
`workspace_id` is the sole canonical tenant key. Tenant describes Workspace
isolation; organization and agency are informal product descriptions, not domain
or persistence entities.

Identity/Tenancy owns Workspace, platform User identity references, Membership,
role assignment, and workspace-scoped authorization relationships. A User may
belong to multiple Workspaces through Memberships. A Membership belongs to one
Workspace and one User, and that pair is unique.

Workspace is the tenant root and has no `workspace_id`. User is a platform identity
and has no `workspace_id`. Membership and every other tenant-owned production row
have non-null `workspace_id`; direct filtering and forced PostgreSQL RLS enforce
isolation.

## Reasons

- One identifier makes authorization, RLS, audit, export, deletion, and jobs
  unambiguous.
- It matches the accepted TenantContext and logical schema.
- It avoids duplicate agency records and speculative enterprise hierarchy.
- Membership naturally supports users participating in multiple agencies.

## Rejected alternatives

- **Separate Tenant and Workspace:** rejected because it duplicates the isolation
  boundary without an MVP requirement.
- **Separate Organization and Workspace:** rejected because parent organizations,
  franchises, resellers, and billing groups are not verified MVP requirements.
- **Agency record copied into another module:** rejected because it creates a second
  canonical owner.

## Consequences

- Workspace stores canonical agency name, slug, status, settings, timezone, locale,
  and lifecycle metadata.
- No `tenant_id`, `organization_id`, Tenant model, or Organization model is created.
- Memory may hold source-linked retrieval representations but cannot update the
  Workspace record.
- Workspace-root access must resolve an exact authorized workspace. User access must
  be limited to the authenticated identity or an authorized workspace-scoped query;
  User is not treated as an ordinary tenant row.

## Future expansion path

Parent organizations, multi-workspace enterprises, franchises, reseller accounts,
or billing groups require a new ADR, explicit ownership and cardinality, updated
TenantContext contracts, security review, and a backward-compatible migration plan.

## Migration considerations

Future hierarchy must preserve existing Workspace IDs as tenant keys. A new parent
record may reference Workspaces, but must not silently replace `workspace_id` or
weaken existing RLS. Backfill, compatibility, rollback, and authorization changes
must be proven before adoption.

## Ownership

Identity/Tenancy owns Workspace, User identity references, Membership, and their
repositories and migrations. Other modules consume published contracts and may not
duplicate or directly mutate these records.

## Tenant-isolation implications

Membership has non-null `workspace_id`, tenant-leading indexes, and forced RLS using
the transaction-local Workspace context. Missing context fails closed. Workspace is
accessed only by exact ID under authorized context. User is a platform root and is
accessed only through identity-owned queries that enforce self or authorized
workspace membership; ordinary tenant-row RLS is not falsely applied to it.
