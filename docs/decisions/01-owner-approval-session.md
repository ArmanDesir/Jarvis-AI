# Rightjob AI OS Owner Approval Session

**Status:** PROPOSED — REQUIRES OWNER APPROVAL  
**Implementation:** BLOCKED — WAITING FOR OWNER DECISIONS

This is the concise approval form for the recommendations in
[00-owner-decision-review.md](00-owner-decision-review.md). Approval here permits
the next architecture phase: recording accepted choices in ADRs and reconciling
the architecture documents. It does not authorize full implementation.

## Decision 1: Technology baseline

This decision controls the initial application and infrastructure shape. Each
technology is independent and must be selected separately.

### Technology: Modular monolith

#### What this controls

Controls whether Rightjob AI OS begins as one strictly modular codebase or as
multiple network services. It does not remove module ownership boundaries.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve a modular monolith. Do not start with microservices or an unstructured
monolith.

#### Why this is recommended

- Lowest safe operating complexity.
- Easier transactions, testing, and cross-cutting releases.
- Module boundaries remain enforceable.
- Cohesive modules can be extracted later when measurements justify it.

#### What happens if approved

An ADR may formalize the modular-monolith deployment boundary and the architecture
documents may be reconciled around it.

#### What happens if rejected

The service boundaries, data ownership, network contracts, deployment cost, and
failure model must be redesigned before implementation.

#### What remains replaceable

Well-defined module interfaces, commands, queries, and events allow a module to
be extracted into a service later.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: Separate API and worker processes

#### What this controls

Controls whether fast user requests and long-running workflow work can scale and
fail independently while sharing the same modular codebase.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve separate API and worker processes. Do not create a service per module.

#### Why this is recommended

- Slow AI/provider work cannot block chat and approval requests.
- API and worker capacity can scale independently.
- Worker restarts do not require changing domain contracts.
- It is much simpler than microservices.

#### What happens if approved

An ADR may define separate composition roots and deployment processes without
selecting the final workflow engine yet.

#### What happens if rejected

The MVP must accept coupled API/worker capacity and failure or define another
process model.

#### What remains replaceable

Application and Capability contracts isolate process placement. Processes may be
combined or split later without changing business ownership.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: PostgreSQL

#### What this controls

Controls the primary durable store for tenants, agency work, policy, workflows,
memory metadata, and audit records.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve managed PostgreSQL as the primary database.

#### Why this is recommended

- Strong transactions and constraints.
- PostgreSQL Row-Level Security supports tenant defense in depth.
- Relational data, JSON, full-text search, and outbox records fit one system.
- Avoids multiple databases in the MVP.

#### What happens if approved

An ADR may formalize PostgreSQL, Repository boundaries, managed-operation
requirements, backup/restore expectations, and RLS usage.

#### What happens if rejected

The transaction, tenant-isolation, outbox, relationship, migration, and backup
models must be redesigned around another database.

#### What remains replaceable

Module-owned Repository interfaces protect domain code. SQL migrations, RLS, and
operational data remain costly to move later.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: `pgvector`

#### What this controls

Controls whether semantic embeddings are initially searched inside PostgreSQL.
It does not control Memory ownership or Retrieval Service contracts.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve only a retrieval proof. Enable `pgvector` only if it measurably improves
context accuracy over structured links and PostgreSQL full-text search.

#### Why this is recommended

- Avoids a separate vector database.
- Keeps tenant filtering and deletion close to source records.
- Semantic retrieval may help ambiguous project references.
- Evaluation prevents adding vectors without demonstrated value.

#### What happens if approved

A proof and evaluation plan may be formalized. Production use still requires the
proof to pass its accuracy, latency, tenancy, and cost criteria.

#### What happens if rejected

The MVP uses structured references and full-text search, or another retrieval
proposal must be reviewed.

#### What remains replaceable

Retrieval Service hides search implementation. Model, dimensions, and content
hashes allow re-embedding; moving a large corpus later still has cost.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: Redis

#### What this controls

Controls temporary shared caching, distributed rate limits, and presence. Redis
must never hold authoritative workflow or business state.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Defer Redis until multiple instances or measured cache/rate-limit pressure
requires it. Reject Redis as durable state.

#### Why this is recommended

- Removes an unnecessary MVP service.
- In-process temporary controls are sufficient at initial scale.
- System correctness cannot depend on an evictable cache.
- A cache/rate-limit port preserves later adoption.

#### What happens if approved

Architecture documents may remove Redis from the required baseline and retain it
only as a measured future option.

#### What happens if rejected

The owner must specify the verified MVP requirement that justifies Redis and its
failure, security, and operating model.

#### What remains replaceable

Cache, rate-limit, and presence interfaces permit Redis or another ephemeral
store later. Clearing the implementation must not lose durable work.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: Clerk

#### What this controls

Controls user sign-in, sessions, recovery, MFA, and external identity. Rightjob
AI OS still owns workspaces, memberships, roles, and permissions.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve only a Clerk proof and commercial/security review, compared with Auth.js.
Reject custom authentication for the MVP.

#### Why this is recommended

- Authentication is security-sensitive and expensive to build safely.
- Clerk may accelerate delivery.
- A proof checks price, privacy, region, export, MFA, and webhook requirements.
- Internal user IDs prevent identity-provider lock-in.

#### What happens if approved

An evaluation ADR may compare Clerk and Auth.js. Clerk is not formalized for
production until the exit path and security/commercial requirements pass.

#### What happens if rejected

Another managed or library-based identity option must be reviewed. Custom
authentication requires a substantially stronger security justification.

#### What remains replaceable

An Identity Provider interface and internal user IDs isolate external
issuer/subject identifiers from domain records.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: S3-compatible storage

#### What this controls

Controls durable storage for uploaded files, screenshots, generated media, and
workflow artifacts. PostgreSQL stores their metadata and ownership.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve S3-compatible object storage. Select the provider and data region later.

#### Why this is recommended

- Application disks are not durable shared storage.
- Large binaries should not burden the primary database.
- Workers need shared access after restarts.
- Standard object operations keep provider choice open.

#### What happens if approved

An ADR may define the Storage Tool Interface, encryption, signed access, scanning,
lifecycle, and region-selection requirements.

#### What happens if rejected

A durable multi-process file strategy must be proposed, including backup,
security, scaling, and artifact-sharing behavior.

#### What remains replaceable

A Storage Tool Interface, provider-neutral keys, and checksums protect
replaceability. Provider-specific retention/event features require review.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

### Technology: Workflow engine

#### What this controls

Controls how multi-step work survives restarts, waits for approvals, retries
providers, handles timers, and resumes safely.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Approve a focused managed-Temporal proof, not immediate production adoption. If
the proof passes, prefer managed Temporal; if the MVP is narrowed to short-lived
work without durable human waits, use PostgreSQL jobs and explicit state machines.
Do not self-host Temporal for the MVP.

#### Why this is recommended

- Durable approvals and multi-day workflows are core requirements.
- Building correct leases, timers, replay, and recovery becomes a custom engine.
- Temporal has material learning and lock-in costs that should be proven.
- The proof tests the hardest failure and approval cases before commitment.

#### What happens if approved

An ADR may authorize only the proof scope: restart, approval pause, retry,
cancellation, version replay, idempotent effect, and uncertain-outcome handling.

#### What happens if rejected

The owner must either narrow the MVP workflow requirements or approve a detailed
PostgreSQL job/state-machine design review.

#### What remains replaceable

Provider-neutral plans, definitions, Capability contracts, and status models keep
engine code inside Orchestration infrastructure. Active histories remain hard to
migrate and would normally drain on the old engine.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

## Decision 2: Departments and Creative ownership

#### What this controls

Controls the initial business-domain plugins and the single owner of each
Creative capability. It prevents Website and Marketing from duplicating design
rules, prompts, tools, and quality standards.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Start with Website, Marketing, and Operations. Marketing is the sole MVP owner of
all listed Creative capabilities; Website consumes approved creative artifacts
through Orchestrator.

| Capability | Owner | Consumers | Orchestrator required? |
|---|---|---|---|
| Brand strategy | Marketing | Website, Operations | Yes when consumed outside Marketing |
| Visual direction | Marketing | Website | Yes |
| Graphic design brief | Marketing | Website | Yes for website use |
| Social media graphics | Marketing | None | No |
| Website visual assets | Marketing | Website | Yes |
| Video concepts | Marketing | Website when embedded | Yes when consumed by Website |
| Image-generation prompts | Marketing | Website | Yes for website assets |
| Campaign creative direction | Marketing | None | No |

Website separately owns website information architecture and UI composition. It
does not own generation of the Creative artifacts above.

#### Why this is recommended

- One capability has one owner.
- Retains only three MVP departments.
- Marketing is the natural owner of brand and campaign creative.
- Website can reuse artifacts without direct department calls.
- Creative can be extracted later if it becomes a cohesive independent domain.

#### What happens if approved

An ADR and updated capability ownership map may formalize the three departments
and the Orchestrator handoff contracts.

#### What happens if rejected

The Creative boundary must be redesigned. A replacement must still assign exactly
one owner per capability and cannot duplicate it across Website and Marketing.

#### What remains replaceable

Versioned Capability and artifact contracts permit later extraction into a
Creative Department without changing consumers at once.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

## Decision 3: Risk and approval matrix

#### What this controls

Controls which actions may run automatically, which require bounded permissions,
and which require a person to approve the exact effect. It governs Policy,
approvals, external actions, audit, and safe retries.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Use four default levels:

| Level | Normal behavior | Examples |
|---|---|---|
| Low | Authorized role; no human prompt | Read projects, search Memory, create/edit drafts, generate image prompts |
| Medium | Reusable scoped permission or manager approval | Create projects/tasks, change task status, ordinary client edits |
| High | One-time approval of exact effect | Send email, publish social posts, update live websites, delete files, connect providers |
| Critical | Explicit owner/admin approval; two people where supported; some actions blocked | Deploy code, delete records, spend/purchase, export sensitive data, change permissions, agreements |

Contract signing or agreement acceptance by AI remains prohibited during MVP.
Unknown external outcomes must be reconciled and never blindly retried.

Approval meanings:

- **Plan acceptance:** approves the intended approach; it does not authorize an
  external effect.
- **Reusable permission:** a recorded, bounded grant for role, scope, value, and
  time.
- **One-time action approval:** approves exact content, target, amount, provider,
  and operation hash.
- **External-effect commitment:** happens only after current Policy and any
  required one-time approval pass again.

Proposed expiry defaults:

- email/social action: 24 hours or scheduled publish time;
- live website update: 4 hours;
- destructive action: 1 hour;
- purchase/financial action: 30 minutes;
- sensitive export: 30 minutes;
- reusable project/task permission: up to 90 days;
- sensitive client-edit permission: up to 30 days;
- capped advertising grant: up to 7 days.

Changed content, recipient, target, amount, provider, scope, artifact, environment,
or risk invalidates approval.

Proposed approvers:

- Low: any member already authorized for the resource.
- Medium: project/operations manager or a holder of the scoped permission.
- High: project/operations manager or workspace owner/admin, approving the exact
  effect.
- Critical: workspace owner/admin or security admin; two authorized people where
  supported for deployment, bulk deletion, major spend, and privilege elevation.

MVP prohibitions are AI signing/accepting agreements, blind retry after an
unknown external outcome, and any Critical commitment without the configured
explicit approver. These are distinct from High actions, which remain allowed
only after their one-time approval.

#### Why this is recommended

- Separates planning consent from permission to cause an effect.
- Makes external and destructive actions fail closed.
- Supports routine internal work without constant prompts.
- Prevents duplicate sends and blind retries.
- Keeps evidence and accountability for every consequential action.

#### What happens if approved

The next architecture phase may formalize Policy rules, approval snapshots,
expiry, approver roles, idempotency, reconciliation, and audit evidence.

#### What happens if rejected

Risk levels, action classifications, approvers, expiry, and prohibited MVP
actions must be redesigned before any external Tool contract is implemented.

#### What remains replaceable

Policy and approval contracts remain independent of departments and providers.
Workspace policies may become stricter; weaker rules require explicit governance.

#### Owner decision

Use the following choice for each of the five items:

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation
```

```text
Risk levels:
Selected:
Notes:

Action classifications:
Selected:
Notes:

Approval expiry rules:
Selected:
Notes:

Authorized approvers:
Selected:
Notes:

MVP prohibited actions:
Selected:
Notes:
```

## Decision 4: Tenant isolation strategy

#### What this controls

Controls how every PostgreSQL row is tied to one agency workspace and how RLS,
repositories, background jobs, indexes, exports, and audits enforce isolation.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

- Every tenant-owned production table has non-null `workspace_id`.
- All child, join, high-volume, security-sensitive, event, audit, message-part,
  memory-source, artifact, approval, external-operation, and projection tables
  receive it.
- Composite foreign keys include `workspace_id` so a child cannot reference a
  parent in another workspace.
- Parent-join isolation is prohibited for tenant-owned production tables.
- Omission is allowed only for truly global immutable reference data.
- Offline migration staging may temporarily rely on a parent join but must
  populate and validate `workspace_id` before application access.

Enforcement:

- schema lint checks every tenant-owned table;
- table ownership is declared;
- RLS denies access without workspace context;
- CI verifies enabled/forced RLS and composite tenant relationships;
- two-workspace integration tests attempt forbidden reads and writes;
- background-job, cache-key, and object-key isolation tests run;
- security tests enumerate all tenant-owned tables.

#### Why this is recommended

- Direct RLS is safer than join-dependent isolation.
- Developers and jobs follow one rule.
- Auditing, export, deletion, and partitioning are simpler.
- Repeated UUID storage is cheaper than a cross-tenant incident.
- Adding tenant columns after large data growth is a difficult migration.

#### What happens if approved

An ADR may formalize this database invariant and architecture documents may be
updated before schema implementation.

#### What happens if rejected

A join-based or hybrid strategy needs a new security review, exact exception
rules, RLS designs, performance evidence, and migration analysis.

#### What remains replaceable

Repository interfaces preserve database access boundaries. The tenant key itself
is intentionally difficult to remove because it is a security invariant.

#### Owner decision

```text
A. Approve the recommendation
B. Approve with modifications
C. Reject and request another option
D. Need a simpler explanation

Selected:
Notes:
```

## Decision 5: Workflow authoring scope

#### What this controls

Controls who may create reusable workflow definitions. It does not remove dynamic
planning or the workflow engine.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Recommend **A. Built-in workflows only** for MVP.

- **Built-in workflows:** reviewed patterns shipped through the product release.
- **AI-generated plans:** typed proposals for a specific request.
- **Compiled workflow instances:** validated per-request executions produced by
  Workflow Compiler.
- **Administrator-authored definitions:** reusable internal authoring surface;
  deferred under the recommendation.
- **User-facing no-code builder:** workspace workflow-design product; deferred.

Normal users may still ask the Executive to build a website, create and approve a
campaign, prepare a weekly report, or update tasks after a meeting. Planner
selects approved Capabilities and Compiler creates the specific run; users cannot
inject arbitrary steps or code.

#### Why this is recommended

- Smallest safe product and security surface.
- Avoids building a no-code product inside the MVP.
- Dynamic requests remain flexible.
- Built-in patterns are versioned and testable.
- Authoring can be added over stable contracts later.

#### What happens if approved

The API may remove public/internal workflow-authoring scope for MVP while
retaining the engine, definition contract, Compiler, built-in patterns, and
per-request plans.

#### What happens if rejected

Internal or workspace authoring requires publishing permissions, schema UX,
version compatibility, debugging, support, abuse controls, and a new security
review.

#### What remains replaceable

Workflow definition and Compiler contracts allow internal or user authoring to be
added later without changing Department Capabilities.

#### Owner decision

```text
A. Built-in workflows only
B. Internal administrator authoring
C. Workspace user authoring
D. Deferred pending further review

Recommended: A
Selected:
Notes:
```

## Decision 6: Workload model

#### What this controls

Controls the planning and load-test assumptions used to judge whether designs are
credible for many agencies. These are assumptions, not claims of achieved
capacity, and must later be verified with telemetry and load testing.

#### Recommended choice

**PROPOSED — REQUIRES OWNER APPROVAL**

Use Expected Normal at 1,000 agencies as the mandatory review floor,
Conservative MVP for early cost planning, Stress for resilience tests, and
10,000 workspaces only as a long-term architecture projection.

| Measure | Normal: 1,000 agencies | Stress: 1,000 agencies | Target projection: 10,000 |
|---|---:|---:|---:|
| Registered users | 12,000 | 30,000 | 120,000 |
| Daily active users | 4,000 | 10,000 | 40,000 |
| Messages/day | 96,000 | 720,000 | 960,000 |
| Workflow runs/day | 5,000 | 20,000 | 50,000 |
| Average steps/workflow | 8 | 15 | 8 |
| Peak concurrent workflows | 500 | 2,000 | 5,000 planning target |
| Provider calls/day | 40,000 | 500,000 | 400,000 |
| External Tool calls/day | 15,000 | 200,000 | 150,000 |
| Peak WebSockets | 3,000 | 10,000 | 30,000 |
| Stored files | 2 million | 10 million | 20 million |
| Object storage | About 4 TB | About 50 TB | About 40 TB |
| Embeddings | 50 million | 250 million | 500 million |
| Audit events/day | 500,000 | 5 million | 5 million |
| Estimated AI tokens/month | 5–10 billion | 40–80 billion | 50–100 billion |
| Planning AI cost sensitivity | USD 10k–100k/month | USD 80k–800k/month | USD 100k–1m/month |
| Estimated DB growth/year | 2–6 TB | Not an accepted sustained mode; potentially >20 TB | 20–60 TB |

The cost figures are planning sensitivities, not vendor quotes.

One noisy tenant is assumed to generate 50 times normal workload for one hour,
hold 5% of files/embeddings, open 500 WebSockets, and hit a provider rate limit.
It must be throttled without delaying or exposing other workspaces.

#### Why this is recommended

- Gives “supports 1,000 agencies” measurable meaning.
- Includes storage, AI cost, concurrency, and noisy-neighbor behavior.
- Prevents speculative microservices or infrastructure.
- Creates concrete load and telemetry targets.
- Can be recalibrated from real usage.

#### What happens if approved

The model may be recorded as the initial architecture/load-test assumption.
Capacity is not considered achieved until measured tests and production telemetry
demonstrate it.

#### What happens if rejected

Specific agency size, retention, files, AI budget, concurrency, and traffic
assumptions must be supplied before capacity-dependent design can be approved.

#### What remains replaceable

The workload model is deliberately revisable. Provider-neutral contracts,
stateless processes, bounded workers, tenant quotas, Repository interfaces, and
measured infrastructure triggers protect later scaling choices.

#### Owner decision

```text
A. Approve the assumptions as the initial planning model
B. Modify specific assumptions
C. Request a lower-cost MVP model
D. Request a more aggressive scale model

Selected:
Notes:
```

## Recommended choices

1. Approve modular monolith, separate API/workers, PostgreSQL, and S3-compatible
   storage; approve proofs only for `pgvector`, Clerk, and Temporal; defer Redis.
2. Start Website, Marketing, and Operations, with Marketing as the single owner
   of MVP Creative capabilities.
3. Use Low/Medium/High/Critical risk levels, bounded reusable permissions, exact
   one-time external-action approvals, and prohibit AI agreement signing in MVP.
4. Put `workspace_id` on every tenant-owned table and enforce direct RLS.
5. Ship built-in workflows only while allowing typed AI-generated plans and
   compiled per-request instances.
6. Use the proposed 1,000-agency normal/stress model and the 10,000-workspace
   projection, subject to measurement.

## Final combined response template

```text
RIGHTJOB AI OS OWNER DECISIONS

Decision 1: Technology baseline

Modular monolith:
Selected:
Notes:

Separate API and workers:
Selected:
Notes:

PostgreSQL:
Selected:
Notes:

pgvector:
Selected:
Notes:

Redis:
Selected:
Notes:

Clerk:
Selected:
Notes:

S3-compatible storage:
Selected:
Notes:

Workflow engine:
Selected:
Notes:


Decision 2: Departments and Creative ownership

Selected:
Notes:


Decision 3: Risk and approval matrix

Risk levels:
Selected:
Notes:

Action classifications:
Selected:
Notes:

Approval expiry:
Selected:
Notes:

Authorized approvers:
Selected:
Notes:

MVP prohibited actions:
Selected:
Notes:


Decision 4: Tenant isolation

Selected:
Notes:


Decision 5: Workflow authoring

Selected:
Notes:


Decision 6: Workload model

Selected:
Notes:
```

**Implementation status: BLOCKED — WAITING FOR OWNER DECISIONS**

After the owner submits completed selections, the next architecture phase may:

1. verify that modifications do not introduce conflicts;
2. create ADRs for accepted choices;
3. reconcile the Constitution and existing architecture documents;
4. run the architecture review gate again.

No application implementation begins from this document alone.
