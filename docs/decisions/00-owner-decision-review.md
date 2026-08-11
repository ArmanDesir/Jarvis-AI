# Rightjob AI OS Owner Decision Review

**Status:** PROPOSED — NOT YET APPROVED  
**Implementation status:** Blocked  
**Purpose:** Help the owner resolve D-002, D-006 through D-011, and D-016
through D-020 without silently adopting any option.

## Executive summary

Rightjob AI OS has an agreed ownership model, but six choices still affect
security, product scope, operating cost, and the shape of the first
implementation. Choosing them now prevents the team from building incompatible
assumptions into authentication, workflows, departments, approvals, database
isolation, and capacity planning.

The simplest safe proposed package is:

- one modular application codebase deployed as separate API and worker processes;
- PostgreSQL and S3-compatible object storage approved as foundational choices;
- short proofs before committing to Temporal, `pgvector`, and Clerk;
- no Redis until a measured need appears;
- Website, Marketing, and Operations departments, with Marketing as the sole MVP
  owner of Creative capabilities;
- conservative one-time approvals for external and destructive actions;
- `workspace_id` on every tenant-owned table, including child tables;
- built-in workflows only, with flexible per-request plans compiled by the
  Orchestrator;
- a measurable workload model, not a claim that the system already supports
  1,000 or 10,000 agencies.

These are recommendations, not decisions. Implementation remains blocked until
the owner approves, rejects, or modifies all six sections and accepted choices
are recorded through the governance process.

Relevant Constitution sources:
[Conflict Report](../constitution/00-architecture-conflict-report.md),
[Vision](../constitution/01-vision-and-product-boundary.md),
[Decision Log](../constitution/18-decision-log.md), and
[Change Governance](../constitution/20-change-governance.md).

---

## Decision 1: Technology baseline

### What must be decided

The technologies solve different problems and should not be approved as one
bundle. The owner must decide which are production foundations, which receive
only a proof of concept, and which remain deferred.

Relevant Constitution sources:
[Orchestration Rules](../constitution/06-orchestration-rules.md),
[Tool and Provider Standard](../constitution/09-tool-and-provider-standard.md),
[Data Ownership](../constitution/12-data-ownership-and-persistence.md), and
[Decision Log](../constitution/18-decision-log.md).

### Proposed disposition

| Technology | Proposed disposition | Recommendation strength |
|---|---|---|
| Modular monolith | Approve now | Strong recommendation |
| Independently scalable API and workers | Approve now | Strong recommendation |
| PostgreSQL | Approve now | Strong recommendation |
| S3-compatible object storage | Approve now | Strong recommendation |
| Temporal | Approve only for proof of concept | Dependent on proof results |
| `pgvector` | Approve only for proof of concept | Safe default for evaluation |
| Clerk | Approve only for proof of concept | Dependent on commercial/security fit |
| Redis | Defer | Safe default |
| Redis as durable workflow or business state | Reject | Strong recommendation |

No listed product is approved by this document.

### 1.1 Modular monolith

**Plain language.** Keep one well-structured application codebase with strict
modules instead of making every department a network service.

**Why it is needed.** Rightjob AI OS needs strong boundaries, not dozens of
deployments. A modular monolith keeps cross-cutting changes reviewable and avoids
distributed transactions while the product is young.

**Affected areas.** All domain modules, plugins, contracts, CI, repository
structure, and deployment.

**Options.**

1. Modular monolith: one codebase and release family with enforced module
   boundaries.
2. Microservices now: separate services and data ownership over a network.
3. Unstructured monolith: simplest initially but no enforceable boundaries.

**Advantages.** Option 1 has the lowest operating cost, easiest transactions and
testing, and preserves future extraction. Option 2 provides independent
deployment and isolation when those are actually needed. Option 3 is fast for a
prototype.

**Disadvantages and cost.** Option 1 requires architecture tests and discipline.
Option 2 adds service discovery, distributed tracing, network failure, contract
deployment, and more on-call load. Option 3 will create ownership overlap and is
constitutionally unacceptable.

**Hard to change later.** Untangling an unstructured monolith is difficult.
Extracting a well-bounded module later is manageable. Collapsing premature
microservices is expensive.

**Recommendation.** Approve the modular monolith. **Strong recommendation.**

**Workflow example.** “Build a website” can coordinate Work, Orchestration,
Website, Content, and Policy in one deployment while still crossing only
published interfaces. No network call is required between those modules.

### 1.2 Independently scalable API and worker processes

**Plain language.** Run user-facing requests separately from long-running AI and
department work, while using the same contracts and codebase.

**Why it is needed.** A slow image generation or website QA run must not consume
the capacity needed to accept chat messages or approval decisions.

**Options.** One combined process; separate API and worker processes; separate
services per module.

**Trade-offs.** A combined process is simpler locally but couples latency and
failure. Separate processes add queue/workflow operations but permit independent
scaling and safe deploys. Per-module services add unnecessary cost.

**Replacement boundary.** Application commands, Capability contracts, and
Orchestrator interfaces prevent process topology from entering business code.

**Hard to change later.** Separating a combined process after synchronous
assumptions spread is harder than starting with a small worker boundary.

**Recommendation.** Approve separate API and worker processes, not separate
module services. **Strong recommendation.**

**Workflow example.** The API accepts “prepare 30 social posts” immediately; a
bounded worker performs the plan while WebSockets show durable progress.

### 1.3 Temporal

**Plain language.** Temporal is a durable workflow engine that remembers where
long-running work stopped, waits for approvals, applies timers/retries, and
resumes after failures.

**Why it may be needed.** Rightjob workflows may last days, cross deployments,
wait for a person, call unreliable providers, and need safe retries or
compensation.

**MVP necessity.** Durable orchestration is necessary. Temporal specifically is
not yet proven necessary.

**Realistic options.**

1. Managed Temporal.
2. Self-hosted Temporal.
3. PostgreSQL-backed job table plus explicit application state machines.
4. A simple background queue designed for short jobs.

**Advantages.**

- Managed Temporal already provides durable timers, signals, replay, workflow
  versioning, retries, and operational visibility.
- Self-hosting reduces SaaS dependence but retains Temporal semantics.
- PostgreSQL jobs add no new data service and work well for short, simple tasks.
- A simple queue is fast for disposable work.

**Disadvantages and risks.**

- Temporal has a learning curve, workflow determinism rules, a vendor/service
  dependency, and added local/production operations.
- Self-hosting adds substantial database, upgrade, monitoring, and on-call work.
- A database queue appears simple but the team must correctly build leases,
  heartbeats, timers, deduplication, approval waits, state transitions,
  reconciliation, versioning, and recovery. That becomes a custom workflow
  engine.
- A short-job queue is unsafe for multi-day approvals and complex external
  effects unless scope is sharply reduced.

**Cost and complexity.** Managed Temporal adds subscription/usage cost but avoids
owning the engine. A database job system has low infrastructure cost and high
engineering/security cost as workflow features accumulate. Self-hosted Temporal
has the highest MVP operational burden.

**Lock-in and replacement.** Temporal workflow APIs can leak into application
code. Protect replacement by keeping domain plans, workflow definitions,
Capability contracts, and status models independent; put Temporal workflows and
activities in the Orchestration infrastructure boundary. Replacement is still a
material migration because active workflow histories cannot be moved trivially.

**What is difficult later.** Migrating active multi-day workflows between engines
is difficult. The safe method is usually to let old workflows drain while new
versions start on the new engine.

**Recommendation.** Approve a proof covering worker restart, a multi-day approval,
retry, cancellation, version replay, idempotent external effect, and uncertain
provider outcome. If it passes with acceptable team complexity, adopt managed
Temporal. If the owner narrows MVP workflows to short-lived work without durable
human waits, use PostgreSQL jobs and revisit. **Dependent on additional
information.**

**Workflow example.** A social campaign pauses Friday for owner approval and
resumes Monday after a deployment. Temporal should resume at the exact approved
step. A database job approach must explicitly implement that state machine,
lease recovery, approval signal, and content-hash validation.

### 1.4 PostgreSQL

**Plain language.** PostgreSQL stores the authoritative agency, workflow, policy,
memory, audit, and integration records.

**Why it is needed.** The product needs transactions, constraints, strong tenant
isolation, reliable queries, and durable records.

**Alternatives.** Another relational database; document database; multiple
databases from day one.

**Trade-offs.** PostgreSQL supplies transactions, RLS, JSON, full-text search, and
extensions in one mature system. A document database fits flexible objects but
makes relationships, constraints, and tenant policy harder. Multiple databases
create consistency and operating cost.

**Lock-in and replacement.** SQL, RLS, and `pgvector` are PostgreSQL-specific.
Module-owned Repository interfaces protect business code, but migrations and
operational procedures still make replacement expensive.

**Operational burden.** Low to moderate when managed; backups, migrations,
connection limits, RLS, indexes, and restore drills still require ownership.

**Recommendation.** Approve managed PostgreSQL as primary storage.
**Strong recommendation.**

**Workflow example.** Creating a project and its outbox event commits atomically,
so downstream task projections cannot observe a project that was never saved.

### 1.5 `pgvector`

**Plain language.** `pgvector` stores embeddings beside PostgreSQL data so Memory
can perform semantic similarity searches.

**Why it may be needed.** “Continue yesterday’s project” may need meaning-based
retrieval in addition to exact keywords.

**MVP necessity.** Hybrid retrieval is useful, but vector retrieval may not be
necessary for the earliest data volumes. PostgreSQL full-text search and strong
entity links should be the baseline.

**Alternatives.** Full-text search only; `pgvector`; dedicated vector database.

**Trade-offs.** `pgvector` avoids a new service and simplifies tenant deletion and
transactions. It adds index/tuning work and can pressure the primary database at
large scale. A dedicated vector database may improve specialized scale but adds
dual writes, consistency, deletion, security, and operations.

**Lock-in and replacement.** Retrieval Service hides query implementation.
Embedding records retain model/dimension/content hash so they can be re-created.
Moving large embedding corpora is still costly.

**Recommendation.** Run a proof with real retrieval evaluation. Enable `pgvector`
only if it materially improves context accuracy over full text/entity retrieval.
Do not consider a dedicated vector database. **Safe default for evaluation.**

**Workflow example.** A user says “the dental site we revised after the branding
meeting.” Structured project links may resolve it; embeddings help only when the
words do not match stored titles.

### 1.6 Redis

**Plain language.** Redis is a fast temporary store for cache entries, distributed
rate limits, short-lived presence, and ephemeral coordination.

**Why it may be needed.** Multiple API instances eventually need shared rate
limits and presence. It is not needed for durable workflow or business state.

**Alternatives.** In-process TTL caches/limits for one instance; PostgreSQL for
small shared counters; managed Redis when horizontal scale requires it.

**Trade-offs.** Redis is fast and familiar but adds a service, cost, eviction
behavior, security configuration, and cache-invalidation work. Starting without
it is simpler.

**Replacement boundary.** Cache, rate-limit, and presence ports. The system must
remain correct when Redis is unavailable or cleared.

**Recommendation.** Defer Redis until multiple instances or measured rate-limit/
cache pressure requires it. Reject Redis as authoritative state.
**Safe default.**

**Workflow example.** Online-user presence may temporarily disappear during a
Redis outage, but an approved workflow and its progress remain intact.

### 1.7 Clerk

**Plain language.** Clerk supplies sign-in, sessions, account recovery, and
identity-provider features. Rightjob still owns workspaces, memberships, roles,
and permissions.

**Why it may be needed.** Building secure authentication, recovery, MFA, and
session management is risky and distracts from the agency OS.

**Alternatives.** Clerk; Auth.js with selected identity providers; another managed
identity service; fully custom authentication.

**Trade-offs.** Clerk accelerates delivery and handles difficult identity flows.
It adds per-user cost, external availability/privacy dependence, frontend/backend
integration conventions, and migration work. Auth.js reduces SaaS dependence but
leaves more security and account lifecycle responsibility. Custom authentication
is not a safe MVP shortcut.

**Lock-in and replacement.** Store an internal user ID and map external issuer/
subject identities through an Identity Provider port. Never use Clerk user IDs as
domain foreign keys. Exportability, region, retention, MFA, organizations, SLA,
webhook semantics, and price must be reviewed.

**Recommendation.** Approve a Clerk proof and commercial/security review, with
Auth.js as the comparison. Adopt Clerk only if requirements and exit path pass.
Reject custom authentication. **Dependent on additional information.**

**Workflow example.** An owner approves a deployment. Policy checks the internal
principal and workspace role, not a Clerk-specific ID; replacing Clerk does not
rewrite approval records.

### 1.8 S3-compatible object storage

**Plain language.** Object storage holds uploaded files and generated artifacts;
PostgreSQL stores metadata and ownership.

**Why it is needed.** Application disks are ephemeral, databases are poor stores
for large binaries, and workers need shared durable access.

**Alternatives.** S3-compatible managed storage; cloud-vendor object store;
database byte columns; shared local filesystem.

**Trade-offs.** Object storage is durable, scalable, and inexpensive per byte, but
requires signed URLs, malware scanning, encryption, lifecycle rules, region
choice, and orphan cleanup. Database blobs increase backup and database pressure.
Local disks do not support resilient multi-instance deployment.

**Lock-in and replacement.** A Storage Tool Interface owns put/get/delete/signed
URL semantics. Store provider-neutral object keys and checksums. Provider-specific
retention and event features can still increase migration cost.

**Recommendation.** Approve S3-compatible object storage, with the provider and
data region selected later. **Strong recommendation.**

**Workflow example.** Website QA stores screenshots and reports as artifacts.
Workers can access them after restarts without writing binary data into workflow
history.

### Decision 1 consequences

The proposed package minimizes services while protecting the two hard-to-reverse
boundaries: primary persistence and long-running workflow history. Temporal and
Clerk remain proof decisions because replacement later is possible but costly.

### Decision 1 approval question

Do you approve, reject, or modify each disposition in the Technology Baseline
table—especially the Temporal proof gate rather than immediate production
adoption?

---

## Decision 2: Departments and Creative ownership

### What must be decided

One Creative capability must have one owner. Website and Marketing may consume
the same artifact, but they cannot implement duplicate “graphic design” or “visual
direction” capabilities.

**Affected system.** Department manifests, Registry discovery, Planner choices,
Capability contracts, brand/creative data ownership, workflow handoffs, quality
review, and future team ownership.

Relevant Constitution sources:
[Component Ownership](../constitution/03-component-ownership.md),
[Department Standard](../constitution/07-department-and-capability-standard.md),
and [Conflict C-22](../constitution/00-architecture-conflict-report.md).

### Options

| Option | Advantages | Disadvantages and risks | Cost/complexity | Hard to change later |
|---|---|---|---|---|
| A. Creative split across Website and Marketing | Few departments; local work is convenient | Duplicates creative rules, brand context, prompts, tools, and quality criteria; ownership disputes | Low initially, high drift cost | Consolidating duplicate capabilities/data |
| B. Separate Creative Department now | Clear creative owner; reusable across channels | Adds a department, registry surface, workflow handoffs, tests, and operations before volume proves the boundary | Medium | Easier to merge than split duplicated owners, but still premature |
| C. Marketing owns Creative in MVP; Website consumes artifacts through Orchestrator | One owner, only three departments, natural campaign/brand home, reusable artifacts | Marketing becomes broader; Website needs an orchestrated handoff | Lowest safe option | Extracting Creative later requires contract/version migration but not data deduplication |
| D. Content/Brand shared service outside departments | May appear reusable | Creates another business owner and violates the Department/Capability model | Unnecessary | Removing the extra layer |

### Proposed MVP capability ownership map

| Capability | Owning Department | Consuming Departments | Cross-department orchestration? | Why this owner |
|---|---|---|---|---|
| Brand strategy | Marketing | Website, Operations | Yes when used outside Marketing | Brand positioning drives all marketing and creative decisions |
| Visual direction | Marketing | Website | Yes | One source for brand-consistent visual decisions |
| Graphic design brief | Marketing | Website | Yes for website briefs | Brief standards should not be duplicated |
| Social media graphics | Marketing | None | No | It is a marketing channel deliverable |
| Website visual assets | Marketing | Website | Yes | Marketing creates/approves the asset; Website integrates it |
| Video concepts | Marketing | Website when embedded | Yes when consumed by Website | Campaign/content strategy owns the concept |
| Image-generation prompts | Marketing | Website | Yes when used for website assets | One quality/safety/brand standard for generated imagery |
| Campaign creative direction | Marketing | None | No | It belongs directly to campaign strategy |
| Website information architecture | Website | Marketing may consult | Yes only if campaign inputs are required | This is a website structure capability, not Creative |
| Website UI composition | Website | None | No | Website owns placement, responsive behavior, and implementation |

“Website visual assets” means the reusable image/graphic artifact. “Website UI
composition” means how Website places and implements that artifact. This avoids
two owners for design generation.

### Recommendation

Choose Option C for MVP. Keep Website, Marketing, and Operations. Marketing owns
all listed Creative capabilities; Website consumes approved artifacts only
through Orchestrator-managed typed steps. Reassess a Creative Department when
there is a dedicated team/roadmap, independent release cadence, substantial
non-marketing demand, or Marketing becomes incohesive.

**Recommendation classification:** Strong recommendation.

### Workflow example

For “build a landing page for the dental campaign,” Orchestrator asks Marketing
for visual direction and website assets, then passes the approved artifact IDs
to Website for UI composition and implementation. Website never calls Marketing
and never reimplements image prompting.

### Decision 2 approval question

Do you approve Option C and the proposed ownership map, reject it, or modify a
specific capability owner?

---

## Decision 3: Risk and approval matrix

### What must be decided

The system needs a conservative default for what can happen automatically, what
requires a role grant, and what requires a person to approve the exact effect.
Workspace policies may become stricter; they cannot silently become weaker than
the constitutional minimum.

**Affected system.** Every command and workflow, Policy, approvals, roles,
Capability contracts, Tool Interfaces, provider calls, audit evidence, retries,
and the user approval experience.

Relevant Constitution sources:
[Policy and Security](../constitution/11-policy-approval-and-security.md) and
[Approval Lifecycle](../constitution/24-external-action-approval-lifecycle.md).

### Approval concepts

- **Plan approval:** accepts the proposed approach and cost envelope. It does not
  authorize a later external effect.
- **Specific external-action approval:** approves exact content, target, amount,
  and operation hash immediately before commitment.
- **Reusable permission:** a role/policy grant for a bounded action category,
  scope, amount, and time. It is not blanket consent.
- **One-time approval:** applies once to one immutable operation. Changing content,
  target, amount, provider, or risk invalidates it.

### Risk levels

| Level | Meaning | Default control |
|---|---|---|
| Low | Read-only or local draft action with minimal impact | Authorized role; no human prompt |
| Medium | Internal mutable action, limited and usually reversible | Reusable scoped permission or manager approval |
| High | External communication, live content, sensitive data, destructive action, or provider connection | One-time approval of exact effect |
| Critical | Financial, contractual, access-control, production deployment, bulk/irreversible, or severe confidentiality impact | Owner/admin approval; second approver where supported; some actions blocked in MVP |

### Matrix legend

- **Approver:** M = authorized member, PM = project/operations manager, OA =
  workspace owner/admin, SA = security/admin role, 2P = two authorized people.
- **Remembered:** `Role` means reusable role permission; `Scoped` means an explicit
  time/resource/value-bounded grant; `No` means one-time only.
- **Audit evidence:** all rows include principal, workspace, policy decision,
  correlation ID, time, inputs/result, and affected resource. Extra evidence is
  listed.
- **Retry:** `Read` = ordinary bounded read retry; `Safe` = retry only with stable
  idempotency key; `None` = human re-evaluation; `Reconcile` = verify provider
  outcome before retry.

### Proposed default matrix

| Action | Risk | Human approval / approver | Remembered / expiry | Change invalidates? | Extra audit evidence | Reversible? | Idempotency | Safe retry |
|---|---|---|---|---|---|---|---|---|
| Read project information | Low | No; authorized M | Role; membership lifetime | N/A | Resource IDs and query scope | N/A | Request ID for trace | Read |
| Search memory | Low | No; authorized M | Role; membership lifetime | N/A | Filters, source IDs, confidence; not raw secrets | N/A | Request ID | Read |
| Create a draft | Low | No; authorized M | Role; membership lifetime | N/A | Prompt/schema/model version, source refs | Yes | Draft creation key | Safe |
| Edit an internal draft | Low | No; authorized M | Role; membership lifetime | N/A | Before/after version or hash | Yes through versions | Expected version + operation key | Safe on conflict-aware update |
| Generate an image prompt | Low | No; authorized M | Role; membership lifetime | N/A | Sources, policy/brand checks, model metadata | Yes | Generation request key | Safe if duplicate output acceptable |
| Create a project or task | Medium | PM or scoped role | Scoped; max 90 days | Scope change yes | Created fields, parent, assignee, due date | Usually | Creation key | Safe |
| Change a task status | Medium | PM or scoped role | Scoped; max 90 days | Target/state change yes | Old/new status and expected version | Usually | Transition key | Safe if transition remains valid |
| Modify client information | Medium; High for sensitive fields | PM; OA for sensitive fields | Scoped; max 30 days | Yes | Field-level safe diff, reason | Usually through history | Expected version + key | Safe only after conflict check |
| Send an email | High | PM/OA one-time for exact message and recipients | No; expires 24 hours | Yes—subject/body/recipient/attachment | Final content hash, recipients, provider operation ID | No recall guaranteed | Required per message | Reconcile before retry |
| Publish a social post | High | PM/OA one-time for exact content/account/time | No; expires 24 hours or scheduled publish time | Yes | Content/media hash, account, schedule, external ID | Sometimes editable/deleteable | Required per post | Reconcile |
| Update a live website | High; Critical for security/payment/core settings | PM/OA one-time; OA for critical | No; expires 4 hours | Yes | Diff/build artifact, target URL, backup/rollback reference | Often with rollback | Required per release/change | Reconcile |
| Deploy code | Critical | OA + 2P where available | No; expires 1 hour | Yes—commit/artifact/environment | Commit, artifact signature, tests, environment, approvers | Rollback possible, not guaranteed | Required per deployment | Reconcile; never blind |
| Delete files | High; Critical if bulk/legal record | OA one-time | No; expires 1 hour | Yes—target set | Exact IDs/hashes, retention/legal-hold check | Only if trash/versioning | Required per deletion set | No blind retry; reconcile |
| Delete records | Critical | OA; 2P for bulk where available | No; expires 1 hour | Yes | Exact IDs, dependencies, retention/legal basis, export/backup ref | Often not fully | Required | None/reconcile |
| Purchase services | Critical | OA; 2P above owner-set threshold | No; expires 30 minutes | Yes—vendor/item/amount | Quote, currency, tax, terms, payment reference | Vendor-dependent | Required per order | Reconcile only |
| Spend advertising budget | Critical | OA; 2P above threshold | Scoped campaign grant allowed; max 7 days and hard cap | Amount/audience/channel change yes | Campaign, cap, currency, audience, provider IDs, actual spend | Partly stoppable | Required per budget operation | Reconcile |
| Sign or accept an agreement | Critical | Blocked for AI commitment in MVP; human OA acts in provider UI | No | Always | Document hash, signer identity, explicit handoff | Usually no | Provider reference | None |
| Export sensitive client data | Critical | OA/SA one-time | No; expires 30 minutes | Yes—dataset/recipient/destination | Query scope, fields, row count, encrypted destination, download expiry | Disclosure not reversible | Required export key | None; regenerate after approval |
| Change user permissions | Critical | OA/SA; 2P for owner/security elevation where available | No | Yes | Before/after roles, affected user, reason, session revocation | Usually | Expected version + key | Safe only after current-state check |
| Connect a new external provider | High; Critical for broad/admin scopes | OA/SA one-time | Connection remains until revoked; approval is not reusable for another account | Scope/account/provider change yes | Requested/granted scopes, external account, secret reference, webhook verification | Yes by revoke | Connection attempt key | Restart OAuth; do not replay secrets |

### Common control rules

1. Every action passes current authorization and Policy even when no human prompt
   is required.
2. Workspace owners may make defaults stricter.
3. Approval is bound to an immutable effect snapshot/hash.
4. “Remember” never means remembering arbitrary content approval. It means a
   bounded reusable permission recorded as Policy.
5. Unknown provider outcome enters reconciliation; it is never blindly retried.
6. Bulk scope, sensitive fields, unusual value, external exposure, or failed
   rollback can raise the risk level.
7. Critical contractual commitment remains outside AI execution in MVP.

### Cost and complexity

This conservative matrix adds an approval inbox, immutable snapshots, expiry,
role checks, operation idempotency, evidence, and reconciliation. Relaxing it is
cheaper initially but creates duplicate sends, unauthorized publication, data
loss, and legal/financial exposure. Tight defaults can later be relaxed only
through explicit owner-approved policies; recovering from an unsafe default is
much harder.

The hardest later change is correcting records and external effects created under
an unsafe policy. Tightening a matrix also invalidates existing reusable grants
and may require re-approval of active workflows, so policy and approval versions
must be retained.

### Recommendation

Adopt this as the proposed default, with owner-configured monetary and bulk
thresholds still to be supplied. Keep contractual signing blocked in MVP.

**Recommendation classification:** Strong recommendation for the control model;
dependent on additional information for currency amounts, bulk thresholds, and
two-person availability.

### Workflow example

“Follow up all leads” may create email drafts automatically. It cannot send them
from plan approval alone. The owner reviews the exact recipient/content set,
approves it for 24 hours, and each message uses its own idempotency key. Edited
copy invalidates the affected approval.

### Decision 3 approval question

Do you approve, reject, or modify this default matrix? Please specify monetary
thresholds, bulk thresholds, and whether two-person approval is required or only
recommended for Critical actions.

---

## Decision 4: Tenant isolation strategy

### What must be decided

The database needs one unambiguous rule for placing `workspace_id`. Inconsistent
rules are dangerous because developers, background jobs, RLS policies, caches,
and indexes may assume different isolation paths.

**Affected system.** Every tenant-owned schema, Repository, migration, index, RLS
policy, background job, cache/object key, audit query, export/delete workflow, and
future partitioning plan.

Relevant Constitution source:
[Data Ownership and Persistence](../constitution/12-data-ownership-and-persistence.md).

### Options

| Option | Safety/RLS | Query and developer complexity | Storage/index cost | Scale and migration |
|---|---|---|---|---|
| A. Every tenant-owned table has `workspace_id` | Strongest direct RLS and audit scope | Simpler predicates; must maintain composite consistency | More repeated UUID/index bytes | Easiest partitioning and background-job safety; adding later is costly |
| B. Only roots have it; children use parent joins | Isolation depends on correct joins/policies | Complex RLS and easy mistakes | Smaller rows/indexes | Join cost and parent hotspots grow; later backfill is difficult |
| C. Hybrid by sensitivity/volume/access | Can be safe with strict classification | Highest policy and review complexity | Optimizable per table | Exceptions accumulate and drift across teams |

### Specific recommended rule

Choose Option A:

1. Every tenant-owned table contains non-null `workspace_id`, including child,
   join, event, audit, message-part, memory-source, artifact, approval-decision,
   external-operation, and projection tables.
2. High-volume child tables always contain it.
3. Security-sensitive child tables always contain it.
4. Composite foreign keys such as `(workspace_id, parent_id)` reference a matching
   parent key, preventing a child from naming a parent in another workspace.
5. Primary access indexes begin with or otherwise explicitly include
   `workspace_id` according to the query.
6. Parent-join isolation is not allowed for tenant-owned production tables.
7. Omission is allowed only for truly global immutable reference data with no
   tenant-specific content, and for database/system catalogs outside application
   ownership. Any other exception requires an ADR and security approval.
8. Temporary migration staging may use parent joins only while offline from
   application roles and must populate/validate `workspace_id` before exposure.

### Why this is the simplest safe rule

Option A spends modest storage to remove judgment calls from every table review.
At thousands of agencies, the UUID repetition is usually cheaper than complex
RLS joins, accidental cross-tenant access, and later backfills. It improves
auditing, tenant deletion/export, background jobs, partitioning, and noisy-tenant
analysis.

### Enforcement

- Schema lint rejects a tenant-owned table without non-null `workspace_id`.
- A table-ownership manifest distinguishes tenant-owned from global tables.
- RLS denies access when transaction-local workspace context is absent.
- Repository integration tests run as application roles against two or more
  workspaces and attempt cross-tenant reads/writes.
- Composite foreign-key tests reject mismatched workspace/parent pairs.
- Migration checks verify RLS is enabled/forced where required.
- Background-job tests prove explicit tenant context and no privileged bypass.
- Cache/object keys include workspace and tests attempt collisions.
- Security tests enumerate every tenant-owned table and fail on missing policy.

### Cost and what is hard to change later

Rows and indexes are larger, and composite keys require care. This is predictable
engineering work. Adding tenant IDs after billions of child rows, rewriting RLS,
and correcting polluted data is far harder. Removing redundant IDs later is
possible but provides little benefit.

### Recommendation

Adopt Option A with the narrow global/staging exceptions above.
**Recommendation classification:** Strong recommendation.

### Workflow example

When a worker loads an email attachment artifact, it filters directly by
`workspace_id` and artifact ID. RLS does not need to join artifact → step →
workflow → plan to discover the tenant, and a mismatched parent cannot be saved.

### Decision 4 approval question

Do you approve Option A and the stated exception rule, reject it, or modify which
tenant-owned tables may omit `workspace_id`?

---

## Decision 5: Workflow authoring scope

**Affected system.** Public API scope, workflow schemas, Compiler, Orchestrator,
Policy, version compatibility, product UI, support/debugging, and the security
surface exposed to each workspace.

### Terms

- **Workflow engine:** runtime that durably schedules, waits, retries, and resumes.
- **Workflow definition:** versioned typed description of steps, dependencies,
  policy checkpoints, and failure behavior.
- **Workflow Compiler:** deterministic Orchestration component that converts a
  validated plan into an executable definition.
- **No-code workflow builder:** user interface for manually designing definitions.
- **User-authored workflow:** reusable definition created or changed by a
  workspace user.
- **Built-in system workflow:** reviewed definition shipped through the controlled
  product release process.

Relevant Constitution sources:
[Orchestration Rules](../constitution/06-orchestration-rules.md) and
[Conflict C-21](../constitution/00-architecture-conflict-report.md).

### Options

| Option | Advantages | Disadvantages/risks | MVP cost | Hard to change later |
|---|---|---|---|---|
| A. Workspace users author/publish | Maximum customization; reusable agency SOPs | Requires builder/editor, schema UX, validation, permissions, versioning, debugging, support, migration, abuse controls | Very high | Unsafe definitions and compatibility commitments |
| B. Internal admins/developers author | Controlled extension without public builder | Still needs authoring API, publishing lifecycle, internal tooling, compatibility and support | Medium | Public exposure later is manageable |
| C. Authoring deferred; approved built-ins only | Smallest secure surface; workflows reviewed and tested | Users cannot manually save arbitrary reusable workflows | Lowest | Add authoring later over stable definition/compiler contracts |

### How flexibility still works under Option C

The Executive accepts natural-language goals. Context Resolver, Registry, and
Planner create a typed per-request plan from approved Capabilities. Workflow
Compiler converts that validated plan into a durable execution definition for
that run. This is dynamic composition, not a reusable user-authored workflow and
not prompt-controlled runtime behavior.

Examples:

- **Build a website:** Planner selects approved Website capabilities and creates a
  project-specific dependency graph.
- **Create and approve a social campaign:** Marketing produces strategy/content;
  the built-in approval-and-publish pattern supplies the commitment gate.
- **Prepare a weekly client report:** A built-in report pattern takes the client,
  period, sources, and recipients as typed parameters.
- **Update tasks after a meeting:** Context Resolver identifies the meeting/project
  and a built-in task-update pattern validates proposed changes before applying
  them.

If a repeated pattern proves valuable, internal developers can add a reviewed
built-in definition through the normal release process. That does not require an
MVP workflow-authoring product.

### Recommendation

Choose Option C. Ship the engine, definition contract, compiler, and approved
built-in patterns; do not ship workflow authoring APIs or a no-code builder.
Revisit Option B after repeated workflows and operational debugging needs are
measured. Option A requires a separate product/security project.

**Recommendation classification:** Strong recommendation.

### Workflow example

An owner asks, “Every Friday prepare a report for Client A.” The MVP may create a
schedule referencing an approved report definition with typed client/day
parameters. It does not let the user inject arbitrary steps or executable code.

### Decision 5 approval question

Do you approve Option C, reject it, or modify the MVP to allow controlled
internal authoring under Option B?

---

## Decision 6: Workload model

### What must be decided

“Supports 1,000 agencies” is meaningless without behavior, retention, and noisy
tenant assumptions. These numbers are planning hypotheses for design and load
tests—not claims of current capacity.

**Affected system.** API/worker sizing, provider quotas and cost controls,
PostgreSQL and object-storage growth, retrieval design, audit retention,
WebSockets, load tests, SLOs, and evidence for any future infrastructure change.

Relevant Constitution sources:
[Vision scale boundary](../constitution/01-vision-and-product-boundary.md),
[Testing scale acceptance](../constitution/14-testing-and-evaluation-standard.md),
and [Events/retention](../constitution/13-events-observability-and-audit.md).

### Scenario definitions

- **Conservative MVP:** low initial adoption but safety and storage behavior are
  representative.
- **Expected normal:** target planning load at the 1,000-agency review floor.
- **Stress:** a deliberate burst above normal plus one noisy tenant.
- **10,000 target:** architecture projection using normal per-workspace behavior;
  it is not an acceptance result.

### Workload assumptions

| Measure | Conservative MVP: 1,000 agencies | Expected normal: 1,000 agencies | Stress: 1,000 agencies | 10,000-workspace target projection |
|---|---:|---:|---:|---:|
| Registered users/workspace | 8 | 12 | 30 | 12 (120,000 total) |
| Daily active users/workspace | 2 | 4 | 10 | 4 (40,000 total) |
| Conversations/active user/day | 1 | 3 | 6 | 3 |
| Messages/conversation, both sides | 6 | 8 | 12 | 8 |
| Messages/day | 12,000 | 96,000 | 720,000 | 960,000 |
| Plans/workspace/day | 1 | 4 | 15 | 4 (40,000/day) |
| Workflow runs/workspace/day | 2 | 5 | 20 | 5 (50,000/day) |
| Average steps/workflow | 5 | 8 | 15 | 8 |
| Peak concurrent workflows | 150 | 500 | 2,000 | 5,000 planning target |
| Provider calls/workflow | 4 | 8 | 25 | 8 |
| Provider calls/day | 8,000 | 40,000 | 500,000 | 400,000 |
| External Tool calls/workflow | 1 | 3 | 10 | 3 |
| External Tool calls/day | 2,000 | 15,000 | 200,000 | 150,000 |
| Peak WebSocket connections | 1,000 | 3,000 | 10,000 | 30,000 |
| Peak/average traffic ratio | 3× | 5× | 10× | 5× |
| Files/workspace retained | 500 | 2,000 | 10,000 | 2,000 |
| Average file size | 1 MB | 2 MB | 5 MB | 2 MB |
| Total object storage | ~0.5 TB | ~4 TB | ~50 TB | ~40 TB |
| Memory items/embeddings/workspace | 10,000 | 50,000 | 250,000 | 50,000 |
| Total embeddings | 10 million | 50 million | 250 million | 500 million |
| Audit events/day | 100,000 | 500,000 | 5 million | 5 million |

### AI token and cost assumption

For planning only—not a vendor quote:

| Scenario | Estimated AI tokens/month | Planning cost range |
|---|---:|---:|
| Conservative MVP, 1,000 | 1–2 billion | USD 2,000–20,000/month |
| Expected normal, 1,000 | 5–10 billion | USD 10,000–100,000/month |
| Stress, 1,000 | 40–80 billion | USD 80,000–800,000/month |
| Normal projection, 10,000 | 50–100 billion | USD 100,000–1,000,000/month |

The broad range assumes a blended USD 2–10 per million tokens across input,
output, embeddings, and model tiers. It is a budgeting sensitivity, not current
provider pricing. Before adoption, replace it with current quotes, caching and
prompt measurements, model routing, and quality thresholds.

### Noisy tenant assumption

At least one workspace generates 50 times the normal workspace workload for one
hour, holds 5% of stored files/embeddings, opens 500 WebSockets, and reaches a
provider’s rate limit. The platform must throttle that tenant without exposing
data or exhausting global worker/API/database capacity. Fair queues, per-tenant
concurrency, quotas, cost budgets, and backpressure are required; a dedicated
service is not assumed.

### Retention assumptions for capacity planning

These are assumptions, not approved retention policy:

- workflow operational detail: 12 months hot;
- conversation content: retained while active, subject to workspace policy and
  deletion;
- audit/security records: 24 months queryable, then archive as legally required;
- provider request/response bodies: minimized; safe metadata retained with audit;
- WebSocket replay events: 24–72 hours;
- generated temporary artifacts: 30 days unless attached to a project;
- embeddings: life of the valid source; deletion/correction propagates;
- backups: 35 days plus periodic restore tests.

Legal, contractual, regional, and customer requirements may change these and
therefore change capacity.

### Database-growth estimate

These are order-of-magnitude hypotheses excluding object files:

- Conservative 1,000: 0.5–1.5 TB after one year.
- Expected 1,000: 2–6 TB after one year, driven by messages, audit, execution
  evidence, and 50 million embeddings.
- Stress sustained for a year: not an accepted operating mode; it could exceed
  20 TB and must trigger quotas/archival before then.
- Normal 10,000 projection: 20–60 TB after one year if every workspace reaches
  the normal profile.

Actual embedding dimensions, index amplification, JSON/evidence size, audit
payload policy, deletion, and compression can change these estimates severalfold.
Object storage is calculated separately.

### Important unknowns to measure

- Percentage of messages that require Planner or AI at all.
- Token input/output by Capability and cache effectiveness.
- Workflow duration, step fan-out, retry rate, and approval wait time.
- Provider rate limits, latency, failure, and uncertain outcomes.
- Embedding dimensions, retrieval hit rate, and vector-index growth.
- Evidence/audit bytes per step and retention obligations.
- File type/size distribution and duplicate ratio.
- Active/idle WebSocket behavior and reconnect bursts.
- Agency size distribution; a “typical” agency may not exist.
- Data-region, backup, restore, and legal-hold requirements.

### Metrics required from first release

- Requests, messages, plans, workflows, steps, and queue age by workspace tier.
- Active workflow concurrency and worker saturation.
- Capability/provider latency, errors, retries, rate limits, and uncertain
  outcomes.
- Tokens, cost, and quality score by workspace, capability, model, and version.
- Tool calls, idempotency hits, reconciliation, and external-effect failures.
- Database CPU, memory, connections, IOPS, locks, table/index bytes, slow queries,
  replication lag, and RLS-query latency.
- Memory corpus size, retrieval latency/quality, vector/full-text contribution,
  and re-embedding backlog.
- Object bytes/count, upload/download rates, scan backlog, and orphan rate.
- Audit/event throughput, outbox lag, consumer lag, and archive backlog.
- WebSocket connections, fan-out, reconnect rate, and replay volume.
- Per-tenant concurrency, quota denials, and noisy-neighbor impact.

### Evidence-based capacity triggers

These are review triggers, not automatic purchases:

| Change | Measurement that justifies review |
|---|---|
| Add worker capacity | Queue age or workflow-start SLO breached for 15 minutes while worker CPU/concurrency is ≥70%, after removing pathological retries and hot-tenant abuse |
| Add API capacity | Request latency SLO breached with sustained ≥70% CPU/event-loop saturation and database/provider latency not dominant |
| Add PostgreSQL read replica | Read workload is ≥60% of database capacity, read latency threatens SLOs, queries/indexes are optimized, and eventual consistency is acceptable for identified queries |
| Partition large tables | A table/index reaches operationally painful maintenance or query ranges—typically hundreds of millions of rows or >100–500 GB—and most access/retention follows workspace/time partitions |
| Dedicated vector database | `pgvector` misses retrieval latency/recall SLO at representative corpus after indexing/query tuning, consumes >30% of primary database resources, or independent vector scaling materially lowers total cost; tenant deletion/security plan must pass |
| Extract module into service | The module has stable contracts and ownership, and measured independent scaling/security/release needs cannot be met by a separate process or database role; network/consistency/on-call cost is accepted |
| Introduce Kafka/event platform | PostgreSQL outbox/consumers cannot meet measured throughput, fan-out, retention, or replay recovery after batching/partitioning, and sustained event volume/consumer count justifies a staffed platform |

No threshold alone mandates the change. An ADR must show the verified bottleneck,
alternatives, migration, rollback, security, and operating cost.

The model itself is inexpensive; collecting trustworthy telemetry and running
representative tests requires engineering and test-environment cost. The hard
later changes are tenant-key backfills, retention reductions after customers
expect longer history, moving large embedding corpora, and migrating active
workflows. Early quotas, lifecycle metadata, and provider-neutral contracts keep
those options open.

### Recommendation

Adopt the **Expected normal: 1,000 agencies** column as the mandatory architecture
review and load-test model, with Conservative MVP for early cost planning and
Stress for resilience tests. Use the 10,000 column only as a boundary projection,
not a launch promise. Recalibrate quarterly from production telemetry.

**Recommendation classification:** Dependent on additional information. The
numbers are concrete enough for an initial model, but agency behavior, retention,
embedding dimensions, and provider costs require measurement.

### Workflow example

A noisy workspace requests 1,000 social posts. Its plan is rejected or batched by
declared limits, its worker concurrency is capped, and its provider rate limit
does not delay another workspace’s lead-follow-up approvals. Metrics show whether
more workers are justified; the system does not immediately create a new service.

### Decision 6 approval question

Do you approve, reject, or modify this workload model as the initial review and
load-test assumption? Please note any expected agency size, retention, file, or
AI-budget reality that differs materially.

---

## Recommended default package

**PROPOSED — NOT YET APPROVED**

1. Approve the modular monolith, separate API/workers, managed PostgreSQL, and
   S3-compatible object storage.
2. Approve proofs only for Temporal, `pgvector`, and Clerk; choose production use
   only after their stated evidence gates. Defer Redis and reject it as durable
   state.
3. Start with Website, Marketing, and Operations. Marketing is the sole MVP owner
   of the listed Creative capabilities; Website consumes creative artifacts
   through Orchestrator.
4. Use the proposed four-level risk matrix, one-time approval for exact external
   effects, 100% policy evaluation, and no AI contractual signing in MVP.
5. Put non-null `workspace_id` on every tenant-owned table and enforce matching
   tenant composite relationships and RLS.
6. Defer user/internal workflow authoring; ship reviewed built-in patterns and
   compile flexible per-request plans.
7. Use the Expected 1,000-agency model for architecture/load review, Conservative
   for early cost, Stress for resilience, and 10,000 only as a projection.

Accepting this package still does not authorize implementation. Accepted choices
must first be recorded as ADRs and reconciled into the Constitution and existing
architecture documents under the change-governance process.

## Owner response template

```text
Decision 1:
Approved / Modified / Rejected
Notes:

Decision 2:
Approved / Modified / Rejected
Notes:

Decision 3:
Approved / Modified / Rejected
Notes:

Decision 4:
Approved / Modified / Rejected
Notes:

Decision 5:
Approved / Modified / Rejected
Notes:

Decision 6:
Approved / Modified / Rejected
Notes:
```

Implementation remains blocked pending the completed owner response and the
subsequent documented architecture reconciliation.
