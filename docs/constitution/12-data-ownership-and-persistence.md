# Data Ownership and Persistence

## Ownership

Each module owns its aggregates, write use cases, Repository interfaces, schema
objects, migrations, and domain events. Physical colocation in one PostgreSQL
database does not create shared ownership.

Indicative owners:

| Data | Owner |
|---|---|
| workspaces, users, memberships, roles | Identity/Tenancy |
| conversations, messages | Executive |
| context resolutions, memory items/indexes | Context/Memory |
| clients, contacts, projects, tasks, meetings, leads, decisions | Work |
| contractual/engagement requirements and project delivery preferences | Work |
| workspace-member communication preferences | Identity/Tenancy |
| generic files, SOP source documents, unclassified source assets | Content |
| brand voice, messaging, visual identity, asset rules | Marketing |
| website structure and functional preferences | Website |
| plans, definitions, runs, steps, schedules, artifacts | Orchestration |
| department packages, activation, capability metadata | Department Registry |
| policies, approvals, budget/quota decisions | Policy/Approval |
| integration connections and external-operation records | Integrations |
| audit, outbox, usage, cost, operational projections | Owning audit/usage module as defined by contract |

The owner for audit/outbox infrastructure may store copies of event evidence, but
these are not writable substitutes for source aggregates.

## Repository rules

Repositories load/save only the owning module’s aggregates and enforce its
transaction boundaries. They map storage but cannot decide business outcomes.
Application services invoke repositories; AI, prompts, departments outside the
owner, and provider adapters do not.

## Cross-module access

Direct reads and writes across ownership boundaries are prohibited. Consumers use
published queries or build read-only projections from versioned events. Joins
across owned schemas are allowed only inside an explicitly owned reporting
projection, never inside transactional business logic.

## Tenant isolation

Every tenant operation carries an explicit workspace context. Every tenant-owned
production table—including child, join, workflow, event, audit, memory-source,
retrieval, artifact, approval, external-operation, projection, and
security-sensitive tables—contains non-null `workspace_id`. Tenant-aware
composite foreign keys prevent cross-workspace references. RLS is enabled and
forced on every tenant table.

Parent-join-only isolation is prohibited for production tenant data. Exceptions
are limited to truly global immutable reference data and controlled offline
migration staging. Tenant IDs lead relevant indexes, caches and object keys are
tenant-scoped, and background jobs establish tenant context before access. CI
checks schema declarations, RLS, tenant-aware relationships, and cross-tenant
denial for repositories, jobs, retrieval, caches, and object storage.

## Transactions and events

Aggregate changes and owned outbox events commit atomically. Distributed
transactions are not introduced. Cross-module consistency uses durable events,
idempotent consumers, explicit status, and compensation where possible.

## Lifecycle

Data has classification, provenance, retention, deletion, export, backup, restore,
and legal-hold behavior. Derived summaries, embeddings, caches, and projections
must follow source correction/deletion policy. Secrets never reside in domain
tables or execution evidence.
