# Rightjob AI OS Blocker Resolution Package

**Status:** PROPOSED — NOT YET APPROVED  
**Source:** [Architecture Simulation Report](../validation/00-architecture-simulation-report.md)  
**Implementation:** BLOCKED

## 1. Executive blocker summary

| Measure | Extracted count/status |
|---|---:|
| Simulation scenarios | 20 |
| PASS | 6 |
| PASS WITH OWNER DECISION | 9 |
| FAIL | 3 |
| BLOCKED | 2 |
| Document inconsistencies/open states | 34 |
| Missing-contract register entries | 42 |
| Final simulation verdict | BLOCKED |

The counts above are taken directly from the simulation report’s Scenario Results,
Scenario 20 consistency table, and Missing Contracts register. They are not
estimates.

The blocking work separates into four classes:

1. Owner choices that change product scope, technology, cost, or risk appetite.
2. Architecture defects whose corrections follow existing constitutional intent.
3. Missing contracts that must be defined before their implementation phase.
4. Existing documents that must be reconciled after the owner decisions and
   corrections are recorded.

## 2. Owner decisions still required

No selection below is approved. Recommendations reproduce the existing Owner
Decision Review and Approval Session.

### Technology baseline

#### Modular monolith

```text
Recommendation:
Approve a modular monolith with strict module boundaries; reject premature
microservices and an unstructured monolith.

Why it matters:
It fixes the initial deployment and transaction boundary while preserving later
module extraction.

Blocked scenarios:
All implementation; no individual paper scenario requires microservices.

Owner selection:

Owner notes:
```

#### Separate API and worker processes

```text
Recommendation:
Approve separate API and worker processes within the modular codebase; do not
create one service per module.

Why it matters:
Long AI/provider work must not consume user-facing request capacity.

Blocked scenarios:
3, 4, 12, 14, 15 and all durable background execution.

Owner selection:

Owner notes:
```

#### PostgreSQL

```text
Recommendation:
Approve managed PostgreSQL as the primary database.

Why it matters:
Transactions, constraints, RLS, module-owned repositories and the outbox depend
on a primary persistence choice.

Blocked scenarios:
All persistence-dependent implementation; especially 1, 8, 12 and 18.

Owner selection:

Owner notes:
```

#### `pgvector`

```text
Recommendation:
Approve only a retrieval proof. Enable pgvector only if it measurably improves
context accuracy over structured links and PostgreSQL full-text search.

Why it matters:
It determines semantic-retrieval cost and primary-database load without changing
the Retrieval Service contract.

Blocked scenarios:
No safe paper route; implementation choice affects 2, 8, 10 and 18.

Owner selection:

Owner notes:
```

#### Redis

```text
Recommendation:
Defer Redis until multiple instances or measured cache/rate-limit pressure
requires it. Reject Redis as durable workflow or business state.

Why it matters:
It avoids an unnecessary service while keeping future shared rate limiting and
presence replaceable.

Blocked scenarios:
14 depends on a shared rate-limit design only when horizontally distributed.

Owner selection:

Owner notes:
```

#### Clerk

```text
Recommendation:
Approve only a Clerk proof and commercial/security review against Auth.js.
Reject custom authentication for MVP.

Why it matters:
Identity security, privacy, price, MFA, exportability and replacement must be
known before selecting an adapter.

Blocked scenarios:
All authenticated implementation; paper behavior in 1, 7, 8 and 19 remains
provider-neutral.

Owner selection:

Owner notes:
```

#### S3-compatible storage

```text
Recommendation:
Approve S3-compatible object storage; select the provider and data region later.

Why it matters:
Files and artifacts need durable shared storage outside application disks and
the primary database.

Blocked scenarios:
4, 5 and 15 require artifact durability and governed cleanup.

Owner selection:

Owner notes:
```

#### Workflow engine

```text
Recommendation:
Approve a focused managed-Temporal proof, not production adoption. If it passes,
prefer managed Temporal. If MVP is narrowed to short-lived work without durable
human waits, review PostgreSQL jobs and explicit state machines. Do not self-host
Temporal for MVP.

Why it matters:
Multi-day approvals, restarts, timers, cancellation, replay and uncertain
external outcomes are expensive to implement incorrectly.

Blocked scenarios:
3, 4, 12 and 15.

Owner selection:

Owner notes:
```

### Departments and Creative ownership

#### MVP plugin trust model

```text
Recommendation:
Allow only trusted first-party Department plugins released through the controlled
build pipeline. Prohibit uploaded third-party executable plugins until a separate
sandbox, signing, secret/network policy and revocation design is approved.

Why it matters:
The process-isolation and arbitrary-code threat model differs materially between
trusted product code and external executable plugins.

Blocked scenarios:
2–6, 10 and 15–16 depend on the Department runtime trust boundary.

Owner selection:

Owner notes:
```

#### Initial Departments and sole Creative owners

```text
Recommendation:
Start with Website, Marketing and Operations. Marketing is the sole MVP owner of
the listed Creative Capabilities. Website consumes approved artifacts only
through Orchestrator.

Why it matters:
One Capability must have one owner; duplicate design rules, prompts, tools and
quality standards are prohibited.

Blocked scenarios:
2, 3, 4 and 6; Scenario 4 is fully blocked.

Owner selection:

Owner notes:
```

| Creative Capability | Proposed sole owner | Consumers | Orchestrator handoff |
|---|---|---|---|
| Brand strategy | Marketing | Website, Operations | Required outside Marketing |
| Visual direction | Marketing | Website | Required |
| Graphic design brief | Marketing | Website | Required for website use |
| Social media graphics | Marketing | None | Not cross-department |
| Website visual assets | Marketing | Website | Required |
| Video concepts | Marketing | Website when embedded | Required when consumed |
| Image-generation prompts | Marketing | Website | Required for website assets |
| Campaign creative direction | Marketing | None | Not cross-department |

Website separately owns information architecture and UI composition. It must not
reimplement Creative artifact generation.

### Risk and approval policy

#### Risk levels

```text
Recommendation:
Use Low, Medium, High and Critical. Low is authorized internal/read/draft work;
Medium uses bounded permissions or manager approval; High requires exact
one-time effect approval; Critical requires owner/admin authority and two people
where supported.

Why it matters:
Every Capability and external effect needs a consistent default control level.

Blocked scenarios:
2–7, 13, 18 and 19.

Owner selection:

Owner notes:
```

#### Action classification

```text
Recommendation:
Classify reads/drafts as Low; internal project/task mutations as Medium;
email/social/live-site/file deletion/provider connection as High; deployment,
record deletion, spend, sensitive export, permissions and agreements as Critical.

Why it matters:
Misclassification can either stop routine work or permit unsafe effects.

Blocked scenarios:
2–7, 13, 18 and 19.

Owner selection:

Owner notes:
```

#### Approval expiry

```text
Recommendation:
Email/social: 24 hours or scheduled publish time; live website: 4 hours;
destructive: 1 hour; purchase/financial and sensitive export: 30 minutes;
project/task grant: up to 90 days; sensitive client edit: 30 days; capped ad
grant: 7 days. Material changes invalidate approval.

Why it matters:
Long-lived approval can outlive content, target, permission, cost or context.

Blocked scenarios:
3, 5, 6 and 13.

Owner selection:

Owner notes:
```

#### Authorized approvers

```text
Recommendation:
Low: authorized member. Medium: project/operations manager or scoped grant.
High: manager or workspace owner/admin approving the exact effect. Critical:
owner/admin or security admin, with two people where supported.

Why it matters:
Approval is ineffective if an unauthorized role can resume a workflow.

Blocked scenarios:
3–7, 13 and 19.

Owner selection:

Owner notes:
```

#### MVP prohibited actions

```text
Recommendation:
Prohibit AI signing/accepting agreements, blind retry after unknown external
outcomes, and Critical commitment without the configured explicit approver.

Why it matters:
These actions create contractual, duplicate-effect or severe authorization risk.

Blocked scenarios:
7, 12 and 19; safe denial remains available.

Owner selection:

Owner notes:
```

### Tenant isolation

#### `workspace_id` and direct RLS

```text
Recommendation:
Every tenant-owned production table, including child, join, high-volume,
security-sensitive, event, audit, artifact, approval and projection tables, has
non-null workspace_id. Composite foreign keys include workspace_id. Direct RLS
is required; parent-join isolation is prohibited except offline staging and
truly global immutable reference data.

Why it matters:
One direct rule reduces cross-tenant mistakes and simplifies jobs, audit, export,
deletion, indexing and future partitioning.

Blocked scenarios:
8 directly; 1–9, 12–14 and 18–19 depend on the final rule.

Owner selection:

Owner notes:
```

### Workflow authoring

#### MVP authoring scope

```text
Recommendation:
Choose built-in workflows only. Retain typed AI-generated per-request plans and
compiled workflow instances. Defer administrator-authored definitions and the
workspace no-code builder.

Why it matters:
User authoring creates a separate validation, permissions, versioning, security,
debugging and support product.

Blocked scenarios:
4 and document-consistency findings DC-21/DC-30.

Owner selection:
A. Built-in workflows only
B. Internal administrator authoring
C. Workspace user authoring
D. Deferred pending further review

Owner notes:
```

### Workload assumptions

#### Planning floor and long-term target

```text
Recommendation:
Use Expected Normal at 1,000 agencies as the mandatory architecture/load-test
floor, Conservative MVP for early cost, Stress for resilience, and 10,000
workspaces only as a long-term projection. Recalibrate from telemetry.

Why it matters:
Quotas, fairness, concurrency, provider cost, storage and future infrastructure
cannot be evaluated from a workspace count alone.

Blocked scenarios:
14 and every unverified scale claim.

Owner selection:
A. Approve initial planning model
B. Modify specific assumptions
C. Request lower-cost MVP model
D. Request more aggressive model

Owner notes:
```

## 3. Architecture defects requiring correction

These findings are not implementation tasks. Corrections must first be documented
and reviewed. “Owner approval: No” means the correction follows existing
constitutional intent; it does not authorize editing yet.

### AD-01 — Reviewer revision governance

```text
Finding:
Reviewer quality failure has no maximum automated revision count, non-improvement
rule, escalation owner or terminal state.

Severity:
High

Affected components:
Reviewer, Validator, Capability, Orchestrator, Policy, Executive

Affected documents:
Constitution 07, 14, 15; Simulation Scenario 16

Constitution rule:
Reviewer assesses only; Orchestrator owns state; work is bounded.

Proposed correction:
Adopt the minimal rule in Section 4 and add it to Capability/workflow contracts.

Owner approval required: Yes

Reason:
The default revision count and human-escalation behavior affect cost and product
experience, although the ownership correction itself is mandatory.
```

### AD-02 — Canonical preference ownership

```text
Finding:
“Client preference” can mean Work data, brand guidance, Website requirements,
workspace/user settings or derived Memory; no exact canonical taxonomy exists.

Severity:
High

Affected components:
Work, Content, Marketing, Website, Identity/Workspace, Memory/Retrieval

Affected documents:
Constitution 10/12; Original Schema §3/§8; Simulation Scenario 18

Constitution rule:
One canonical owner; Memory cannot duplicate another module’s source of truth.

Proposed correction:
Approve the taxonomy in Section 5, then reconcile data ownership and correction
events.

Owner approval required: Yes

Reason:
Allocating business data among domains changes ownership and future APIs.
```

### AD-03 — Engine-specific schema leakage

```text
Finding:
The logical schema exposes temporal_workflow_id and temporal_run_id before the
workflow engine is approved.

Severity:
High

Affected components:
Orchestration, Repository, Database, workflow-engine adapter

Affected documents:
Original Database Schema §5

Constitution rule:
Infrastructure remains behind published ports; technologies are Proposed.

Proposed correction:
Use engine-neutral execution references in the domain schema and keep vendor
identifiers in adapter-owned mapping/evidence after the engine decision.

Owner approval required: No

Reason:
The correction preserves whichever workflow engine the owner selects.
```

### AD-04 — Event actor misattribution

```text
Finding:
The Technical Architecture event example hardcodes the system actor as executive
for a workflow event even though Executive does not execute workflows.

Severity:
High

Affected components:
Executive, Orchestrator, Audit, event contracts

Affected documents:
Original Technical Architecture §7

Constitution rule:
One owner per responsibility; audit records the real actor and causation chain.

Proposed correction:
Define actor, initiator, service principal and delegation separately; attribute
workflow execution to Orchestrator while retaining the initiating user.

Owner approval required: No

Reason:
This corrects audit truth without changing product scope.
```

### AD-05 — Provider-specific leakage

```text
Finding:
Original API, schema, roadmap and folder examples assume Clerk, Temporal,
pgvector and generic provider fields before selections; action manifests also
name service-like llm/social-provider dependencies.

Severity:
High

Affected components:
Identity, Orchestration, Memory, Capabilities, Tools, Adapters

Affected documents:
Original Technical Architecture §§2/5/10/12; Schema §§5/8/10; API §2;
Roadmap/Sprints

Constitution rule:
Provider-specific code exists only in adapters; unapproved technology is not an
architectural fact.

Proposed correction:
Keep public/domain contracts capability-based and move vendor IDs/configuration
to adapter/telemetry mappings after owner decisions.

Owner approval required: No

Reason:
The boundary correction applies regardless of which provider is chosen.
```

### AD-06 — Cross-module read violations

```text
Finding:
Original documents prohibit only writes or allow ambiguous “queries/projections,”
which can be read as permission to query another module’s tables.

Severity:
Critical

Affected components:
All modules, Repositories, Database, reporting projections

Affected documents:
Original Technical Architecture §3; Folder Structure Ownership Boundary

Constitution rule:
Direct cross-module database reads and writes are prohibited.

Proposed correction:
Require owner public Query interfaces or consumer-owned projections built from
versioned events; prohibit direct table access.

Owner approval required: No

Reason:
This is already a mandatory constitutional invariant.
```

### AD-07 — Missing approval invalidation in originals

```text
Finding:
Original lifecycle/schema/API do not clearly bind action approval to immutable
content/target/cost or require commit-time invalidation.

Severity:
Critical

Affected components:
Policy, Approval, Orchestrator, Capabilities, Tools, Audit

Affected documents:
PRD §6; Technical §6; Schema §7; API §§5/6

Constitution rule:
Material change invalidates approval; Policy runs again before commitment.

Proposed correction:
Separate plan acceptance from action approval and persist an immutable effect
snapshot/hash, expiry, policy version and invalidation reason.

Owner approval required: No

Reason:
The owner chooses defaults, but stale approval must always fail closed.
```

### AD-08 — Ambiguous audit ownership

```text
Finding:
Original Audit appears to own tool evidence while modules also emit events; the
producer/semantic owner versus audit-storage owner is not explicit.

Severity:
High

Affected components:
All event producers, Audit/Observability, outbox, Repositories

Affected documents:
Original Technical §3/§7; Schema §10; Constitution 12/13

Constitution rule:
Each module owns its events; Audit observes without owning business workflows.

Proposed correction:
The source module owns event semantics and evidence generation; Audit owns
append-only recording, correlation, retention and access—not the business fact.

Owner approval required: No

Reason:
This removes duplicate ownership without changing policy.
```

### AD-09 — Duplicated Creative Capability ownership

```text
Finding:
PRD assigns Creative actions to Website and Marketing, allowing two owners.

Severity:
Critical

Affected components:
Website, Marketing, Registry, Planner, Orchestrator

Affected documents:
PRD §5; Conflict C-22; Decisions 00/01

Constitution rule:
One Capability has one Department owner; Departments cannot call each other.

Proposed correction:
Adopt one owner per Creative Capability and typed Orchestrator artifact handoffs.

Owner approval required: Yes

Reason:
The no-duplication rule is fixed, but choosing the Department changes product
scope and team ownership.
```

### AD-10 — Workflow-state ownership conflicts

```text
Finding:
PRD gives Executive coordination, Technical Memory owns procedural workflows,
and Reviewer authority is underspecified.

Severity:
Critical

Affected components:
Executive, Planner, Memory, Reviewer, Workflow Compiler, Orchestrator

Affected documents:
PRD §§1/6/FR-02; Technical §§3/8; original lifecycle

Constitution rule:
Planner proposes; Orchestrator alone owns workflow state; Memory stores knowledge;
Reviewer only assesses.

Proposed correction:
Remove workflow ownership from Executive, Memory and Reviewer and route all state
changes through Orchestration interfaces.

Owner approval required: No

Reason:
This is the adopted constitutional ownership model.
```

## 4. Reviewer governance proposal

**PROPOSED — REQUIRES OWNER APPROVAL**

### Minimal MVP rule

1. Reviewer evaluates qualitative quality only against the Capability’s versioned,
   explicit criteria.
2. Reviewer cannot grant permission, satisfy approval, bypass Policy, call a Tool,
   persist business data, or directly mutate workflow state.
3. Reviewer returns a structured assessment: artifact/version, criteria version,
   score by criterion, threshold, reasons, evidence references, confidence and
   recommended revisions.
4. Orchestrator owns the decision to accept, schedule a revision, pause, fail, or
   enter human review.
5. A workflow receives at most **two automated revision cycles** for a given
   artifact/quality gate. Provider transport retries do not count as content
   revision cycles but have their own bounded retry budget.
6. After two failed cycles, Orchestrator sets `needs_human_review`. No additional
   revision occurs without a person or a separately approved, versioned workflow
   rule.
7. The user is asked to review when the result is user-owned content, the user can
   supply missing judgment, or deadline/budget makes more automation unsafe.
8. A Department owner/manager is notified when criteria conflict, a repeated
   systematic failure affects multiple runs, regulated/sensitive quality is at
   issue, or the workflow cannot proceed without domain judgment.
9. Reviewer assessments, artifact hashes, criteria versions, scores, structured
   reasons, evidence, attempts, model/adapter version, cost, and Orchestrator
   decisions are retained as execution evidence according to retention policy.
10. Infinite loops are prevented by the two-cycle counter, immutable attempt
    history, maximum workflow budget/deadline, non-improvement detection, and a
    terminal `needs_human_review` state.

### Approval

```text
A. Approve
B. Approve with modifications
C. Reject and request another rule
D. Need a simpler explanation

Selected:
Notes:
```

## 5. Canonical preference ownership proposal

**PROPOSED — REQUIRES OWNER APPROVAL**

The taxonomy below assigns one canonical owner. Memory may index or summarize a
source owned elsewhere, but it never becomes that source of truth.

| Preference type | Proposed canonical owner | Who may update | Source of truth | Memory representation | Provenance | Correction and supersession |
|---|---|---|---|---|---|---|
| Client identity and contact details | Work/Client domain | Authorized Work command by assigned staff/manager | Versioned client/contact aggregate | Retrieval copy/reference only | Exact entity/version/field source | Correct canonical record; invalidate derived copy; new version supersedes old |
| Contractual requirements | Work domain | Authorized manager/owner; Operations only through Work interface | Versioned client/project requirement or decision record | Referenced summary only | Agreement/decision ID, version, effective date | Amend through governed Work command; never edit Memory as substitute |
| Brand voice and messaging | Marketing Department | Authorized Marketing Capability/manager | Versioned Marketing-owned brand guidance | Indexed Semantic Knowledge | Brand record/version, author, evidence | New approved guidance supersedes prior version; re-index derived entries |
| Visual identity and asset rules | Marketing Department | Authorized Marketing Capability/manager | Versioned visual-guideline/asset-rule record | Indexed Semantic Knowledge | Guideline and asset IDs/hashes/version | Supersede rule/version; preserve history; propagate re-index |
| Website structure and functional preferences | Website Department | Authorized Website Capability/manager | Versioned website requirements/specification | Indexed Semantic Knowledge | Project/site/spec version and decision refs | Amend specification; invalidate affected derived summaries/plans |
| Project delivery preferences | Work domain | Project/operations manager through Work interface | Versioned project settings/requirements | Indexed Semantic Knowledge | Project/version, actor, effective date | Update canonical project setting; supersede derived memory |
| User communication preferences | Identity/Workspace settings | The user for self; authorized admin for workspace defaults | Versioned user/workspace preference record | Retrieval copy only | User/workspace setting ID/version | Update setting; invalidate caches/derived copy; preserve required audit |
| Temporary task instructions | Working Memory | Authorized current user/Orchestrator within active context | Bounded active conversation/run context | Working Memory only | Message/run/step source and expiry | Replace within active context; expires automatically; not promoted without validation |
| Historical decisions | Work domain for canonical decision; Episodic Memory for representation | Authorized decision owner through Work command | Append-only/versioned decision record | Source-linked episodic history | Decision ID/version, actor, rationale, effective date | Correction is a new superseding decision; history is not rewritten |
| Derived AI inference | Memory | Deterministic Memory application service after validation | Provenance-bearing inference record, explicitly non-canonical | Semantic item with confidence/validity | All source IDs, model/schema version, confidence | Correct by superseding/invalidation; never overwrite source facts or treat inference as fact |

### Ownership clarification requiring reconciliation

The original Constitution lists Content as owner of brand profiles, while the
owner package proposes Marketing as the Creative owner. If this taxonomy is
approved, architecture reconciliation must decide whether:

- Marketing owns the canonical brand-guidance aggregate and Repository; or
- Content remains the canonical data module while Marketing alone owns the
  Capabilities that govern it through Content’s public commands.

Those alternatives cannot both be treated as ownership. The selected model must
name one write owner and one Repository owner.

### Approval

```text
A. Approve
B. Approve with modifications
C. Reject and request another taxonomy
D. Need a simpler explanation

Selected:
Notes:
```

## 6. Missing contract register

The simulation contains **42** missing-contract entries. “Needed phase” is the
earliest architecture/implementation phase that cannot begin safely without the
contract; it does not authorize that phase.

### Executive and Context

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-01 Command Classification | Executive application boundary | API, Executive, Policy, application commands | Route deterministic, reasoning, unsupported and ambiguous requests | Actor, workspace hint, request type/content metadata, correlation | Typed classification, confidence/reason, next route | Invalid input, ambiguous, unsupported | Classification request ID; no duplicate command dispatch | Classification, route, actor/workspace, correlation | Executive foundation | 1, 7, 8, 15, 17, 19 |
| MC-02 Context Resolution | Context Resolver | Executive, Planner, application commands | Resolve allowed entity references with evidence | Principal, workspace, utterance/explicit IDs, requested entity types | Ranked typed references, confidence, evidence, ambiguity | Unauthorized, not found, ambiguous, stale | Read request/correlation only | Filters, candidate IDs, chosen result, confidence; redact content | Context/Memory | 1–6, 8, 18 |

### Planner and Compiler

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-03 Typed Plan/Step DAG | Planner public contract | Plan Validator, Policy, Compiler, UI | Represent proposed Capabilities/dependencies without executable code | Approved goal, resolved refs, enabled Capability metadata, constraints | Versioned steps, schemas, dependencies, risks, artifacts, uncertainty | Unsupported Capability, unbounded plan, missing input | Stable proposal ID/version; duplicate submission deduped | Planner/schema/model versions, sources, correlation | Planning kernel | 2–6, 10, 17 |
| MC-04 Plan Validator | Planning application service | Planner, Policy, Compiler | Deterministically accept/reject plan structure and references | Typed plan, Registry snapshot, tenant context, limits | Validated plan or structured violations | Cycle, version mismatch, unavailable Capability, tenant mismatch, size limit | Same plan/version yields same validation result | Violations, Registry/schema versions, correlation | Planning kernel | 2–6, 17 |
| MC-05 Compiled Workflow Definition/Instance | Workflow Compiler inside Orchestration | Orchestrator, workers, audit/UI | Convert validated plan to deterministic, versioned execution | Validated plan, policy checkpoints, Capability versions, failure rules | Engine-neutral definition/instance version and compatibility metadata | Incompatible version, invalid dependency/policy checkpoint | Stable compile key by plan/version | Compiler/definition versions and compatibility result | Orchestration kernel | 2–6, 12, 15 |
| MC-06 Engine-neutral Workflow Identity Mapping | Orchestration infrastructure | Orchestrator Repository, selected engine adapter, operations | Keep vendor run IDs out of domain schema | Internal run ID, engine adapter, engine identifiers | Mapping/status reference without vendor domain leakage | Missing mapping, engine mismatch, stale run | Unique internal run + engine mapping | Mapping creation/change and correlation | Before engine integration | 3, 4, 12, 15 |

### Policy and Approval

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-07 Risk/Action/Approver Matrix | Policy | All commands, Capabilities, approvals | Supply adopted default risk and thresholds | Action/Capability, resource, value/bulk/sensitivity context | Risk, approver rule, expiry, prohibitions | Unclassified action, missing threshold | Versioned policy lookup | Policy version and classification evidence | Before external/internal mutations | 2–7, 13, 18, 19 |
| MC-08 Policy Request/Decision | Policy | API, Planner, Orchestrator, Capabilities, Tools | Make authorization/risk/budget decisions with deny precedence | Principal, workspace, action, resource/effect, context, policy versions | Allow/deny/approval-required, constraints, reason, expiry | Missing tenant/principal, indeterminate, quota, stale context | Stable decision request ID; re-evaluation creates linked decision | Full decision metadata without secrets | Security foundation | Nearly all |
| MC-09 External-effect Snapshot/Invalidation | Policy/Approval | Orchestrator, Capability, Tool, UI | Bind approval to exact immutable effect | Target, content/artifact hash, cost, provider/connection, risk, expiry | Snapshot ID/hash, material fields, validity/invalidation result | Changed effect, expired, missing evidence | Snapshot content hash; duplicate snapshot dedupe | Old/new hashes, invalidation reason, correlation | Before external effects | 3, 5, 6, 13 |
| MC-10 Approval Eligibility/Resume | Policy/Approval | Identity, Orchestrator, approval API | Authorize approver and authenticate workflow resume | Actor/role, approval/effect/run IDs, expected version, decision, reason | Append-only decision, valid resume signal or denial | Unauthorized, expired, conflict, stale snapshot, second approver missing | Decision key and optimistic version | Actor/role, policy, decision, effect hash, denial/resume | Approval foundation | 3–7, 13, 19 |
| MC-11 Untrusted-content Security Boundary | Policy/Security with Content input | Retrieval, Executive, Planner, Capabilities, AI ports | Treat retrieved/uploaded text as data, never authority | Trust label, source, sensitivity, content excerpt, requested use | Allowed/sanitized context, blocked instruction category, security signal | Malware, injection, secret exposure, prohibited content | Content hash/detection version | Safe source hash, classification, blocked reason; never secrets | File/retrieval foundation | 9 |
| MC-12 Support/Break-glass Access | Policy/Security | Support tooling, Identity, Audit, Repositories | Govern exceptional time-bound support access | Support actor, reason, workspace, scope, duration, approvals | Limited session/grant, expiry/revocation | Unauthorized, missing reason/approval, expired | Unique grant/session; non-replayable | Complete immutable access trail and sensitive reads | Before support access | 8 |

### Orchestration

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-13 Durable State/Lease/Replay | Orchestration | Workers, engine adapter, operations | Define recoverable transitions and ownership of work | Run/step/version, lease/heartbeat, definition version, signal | Durable state, next work, replay/compatibility status | Lost lease, incompatible history, duplicate worker, crash | Transition command/event IDs; compare-and-set version | Every transition/attempt/worker recovery | Orchestration kernel | 3, 4, 12, 15 |
| MC-14 Cancellation/Late Result/Retention | Orchestration | Capabilities, Tools, Providers, Content, Policy | Stop work without deploying or losing evidence | Actor, run/version, active steps, cancellation deadline, retention policy | Cancelling/final state, provider outcomes, retained artifacts, released budget | Unauthorized, too late, provider cannot cancel, uncertain effect | Cancellation command ID; repeated request safe | Actor, states, signals, late results, cleanup | Orchestration kernel | 4, 15 |
| MC-15 Failure/Retry/Deadline | Orchestration | Compiler, Capabilities, Tools, adapters, UI | Normalize failures and bound retry/backoff | Error category, attempts, retry safety, deadline, budget, provider hints | Retry/wait/fail/reconcile decision and schedule | Permanent failure, deadline/budget exhausted, unknown outcome | Attempt IDs; stable effect idempotency preserved | Error category, attempts, backoff, terminal reason | Orchestration kernel | 2–6, 11–12, 16 |
| MC-16 External-operation Ledger/Reconciliation | Integrations with Orchestration contract | Tools, adapters, Orchestrator, Audit | Prevent duplicate effects and recover unknown outcomes | Effect hash, operation key, provider/connection, approval/policy refs, attempt | Intent/status/external ID/certainty, reconcile/compensate result | Duplicate key conflict, unsupported lookup, uncertain outcome | Mandatory stable operation-scoped key | Durable pre-call intent, each provider attempt/status/result | Before any external effect | 3, 5, 6, 11–13 |

### Department and Capability

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-17 Department Manifest/Ownership Map | Department Registry; each Department authors manifest | Planner, Policy, Compiler, operators | Publish enabled/versioned single owners and metadata | Department/version, Capabilities, schemas, risks, permissions, tools/AI | Validated immutable manifest and activation/version | Duplicate owner, invalid schema, incompatible/disabled version | Package checksum/version and activation command key | Publication/activation/owner changes | Before Department implementation | 2–6, 10, 15–16 |
| MC-18 MVP Capability Set | Each owning Department | Registry, Planner, Compiler, Policy | Define social, email, website, image and correction operations | Per-operation business inputs and context refs | Typed result/artifacts/evidence | Domain validation, unsupported state, dependency failure | Per Capability/effect policy | Capability/version, inputs hash, result/evidence | Department phase | 2–6, 18 |
| MC-19 Capability Standard Envelope | Each Department under Plugin SDK standard | Orchestrator, Policy, Tools, Audit | Carry all constitutional metadata consistently | IDs/version, typed input, permissions, risk, dependencies, timeout/retry/cancel/review | Typed output, evidence, events, usage/cost, normalized failure | Schema, policy, timeout, cancellation, domain invariant | Invocation/effect key declared per contract | Invocation/result and correlation | Plugin SDK/Registry | 2–6, 10–17 |
| MC-20 Cross-Department Artifact Handoff | Orchestration contract; artifact producer owns schema | Producing/consuming Departments, Validator, Audit | Pass immutable artifacts without Department calls | Artifact ID/version/hash/type, producer, permissions, acceptance criteria | Accepted/rejected typed reference and evidence | Incompatible version, unauthorized, invalid artifact | Artifact/version + consumer step key | Producer/consumer, hash, validation, lineage | Before cross-department workflow | 4 |
| MC-21 Unsupported Capability Result/Proposal | Registry/Planning application | Executive, Planner, product governance | Fail safely and optionally record non-executable demand | Requested semantics, workspace-safe context, Registry snapshot | Unsupported reason, alternatives, proposal reference | Sensitive request, duplicate proposal | Proposal fingerprint; never executable | Registry version, request category, outcome | Planning kernel | 17 |

### Tool Interface

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-22 External Tool Interfaces | Integrations/tool-contract owners | Department Capabilities, Orchestrator, adapters | Define Social, Email, Website/CMS/Deployment, Storage, Browser/QA and Image operations without vendors | Typed operation, tenant/connection ref, deadline, effect key, safe payload/artifact refs | Normalized result, evidence, external ref, capability/status | Auth, validation, rate limit, timeout, permanent, uncertain, unsupported | Mandatory for effects; explicit for reads/generation | Tool call/result, connection ref, usage/cost, correlation | Before each integration | 3–6, 9, 11–12, 15 |

### Provider Adapter

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-23 Normalized AI Provider Contract | AI provider port; adapters implement | AI Router, Executive/Planner/Capabilities through port, Validator | Normalize inference, embedding, streaming, usage and cancellation | Capability requirements, messages/data, schema, deadline, privacy/cost context | Typed output/stream, usage/cost, adapter metadata, finish/cancel status | Invalid output, unavailable, rate limit, timeout, policy-ineligible | Request ID; generation duplicate policy explicit | Adapter/model/schema, safe hashes, usage/cost, errors | AI foundation | 2, 4, 6, 9–11, 16, 18 |
| MC-24 Fake-adapter Contract Suite | Provider/tool platform test owner | All adapter implementations, CI | Demonstrate interchangeable behavior without live providers | Canonical contract cases and failure/cancel/status fixtures | Pass/fail compatibility report | Contract deviation, leaked vendor type/field | Deterministic fixture IDs | Test version/results; no production data | Before provider integration | 10 |
| MC-25 Provider Status/Connection Contract | Each adapter behind standard provider metadata | Tools, Orchestrator, AI Router, Policy | Expose status lookup, idempotency support, OAuth scopes and health | Connection ref, external/idempotency ID, requested scopes/capability | Normalized status/certainty, scopes, capability/health metadata | Unsupported lookup, revoked auth, unknown, rate limit | Status reads safe; connection attempts keyed | Scope grants, connection changes, status lookups | Before external effects/fallback | 3, 5, 6, 11–12 |

### AI Router

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-26 AI Capability Routing | AI Router | Executive, Planner, Reviewer, Department Capabilities, Policy | Select only eligible providers and explain rejection/fallback | Structured output/tool/context/modality/privacy/region/cost/latency/quality/fallback requirements | Selected adapter/capabilities or typed unavailable; ranked rejection reasons | No eligible provider, stale availability, budget/region/privacy conflict | Route request ID; same snapshot should be explainable | Requirements, candidates, rejections, selection, fallback, cost | AI foundation | 2, 4, 6, 10–11, 16, 18 |

### Validator and Reviewer

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-27 Reviewer/Revision Governance | Capability owns criteria; Reviewer assesses; Orchestrator governs attempts | Validator, Orchestrator, Executive, managers | Bound qualitative revisions and escalate without authority leakage | Artifact/version, criteria/version, scores, prior attempts, budget/deadline | Structured reasons/evidence, recommendation; Orchestrator state decision | Invalid criteria, low confidence, non-improvement, attempts exhausted | Assessment keyed by artifact/criteria/reviewer version | Scores/reasons/evidence/attempt/cost/state decision | Before qualitative review | 2, 4–6, 16 |

### Repository and tenancy

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-28 Work Query/Canonical Entity Contract | Work | Executive fast path, Context Resolver, Planner through public query | Read project/client/task state without table access | Principal/workspace, typed filters/IDs, field projection | Versioned typed entity/status DTO with visibility metadata | Unauthorized, not found, ambiguous, stale | Read/correlation ID | Sensitive-read policy, query/resource IDs | Work foundation | 1–6, 18 |
| MC-29 Table/Module Ownership and Migration Manifest | Each module; architecture/DB governance validates | Migration runner, CI, repositories, reviewers | Declare one owner for every schema object/migration/event | Object/migration ID, module, tenant/global class, dependencies | Validated ownership map/order | Duplicate/unowned/cross-module mutation | Migration/version checksums | Owner/change/review/migration outcome | Before first migration | All persistence |
| MC-30 Tenant Column/Composite FK/RLS Rule | Identity/Tenancy security with each data owner | Repositories, migrations, DB roles, CI | Enforce direct tenant isolation on all tenant-owned rows | Table ownership/class, workspace field, parent relations, app roles | RLS/FK/index policy and verification result | Missing context/policy, mismatched tenant, privileged bypass | Transaction workspace context; writes versioned/keyed | Denied cross-tenant attempts and policy checks | Before tenant schema | 1–9, 12–14, 18–19 |
| MC-31 Tenant Context Propagation | Identity/Tenancy | API, workers, repositories, caches, objects, retrieval, audit | Carry authenticated workspace/actor without implicit globals | Verified principal/membership, workspace, service delegation, correlation | Scoped context/reference with expiry | Missing/invalid membership, context loss, delegation invalid | Context token/request correlation; non-replayable where signed | Creation/delegation/loss/denial | Platform foundation | Nearly all |
| MC-32 Tenant Key Isolation Verification | Security/tenancy test contract | Cache, object storage, embedding/retrieval, projections, CI | Prevent collisions/enumeration outside SQL RLS | Workspace, key type, generated key/index namespace, adversarial inputs | Scoped key and isolation test result | Collision, missing tenant prefix/filter, cross-tenant hit | Stable key derivation; no shared mutable tenant data | Security test evidence/alerts | Before cache/object/vector use | 4, 8, 9, 14 |
| MC-33 Data Lifecycle/Recovery | Each data owner with security/compliance | Repositories, Memory, Storage, Audit, backup operations | Define retention, legal hold, export, deletion, backup and restore | Data class, workspace, source/derivatives, policy/legal basis | Retain/archive/delete/export/restore decision and evidence | Hold conflict, partial derivative deletion, restore failure | Operation-scoped key; deletion/export resumable | Complete lifecycle evidence without secret payload | Before production data | 4, 7–9, 18 |

### Memory and Retrieval

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-34 Retrieval Query/Result | Retrieval Service | Context Resolver, Executive, Planner, Capabilities | Permission-filter and rank keyword/vector/source knowledge | Principal/workspace, query, entity/sensitivity filters, top/threshold, purpose | Source-backed ranked items, confidence, validity, provenance | Unauthorized, no result, ambiguous, stale/index unavailable | Read/correlation ID; cache tenant-keyed | Filters, source IDs, method/version, confidence | Memory foundation | 1–4, 6, 8–10, 18 |
| MC-35 Canonical Preference Taxonomy | Domain owners defined by approved taxonomy | Memory, Context Resolver, Work/Content/Identity/Departments | Prevent duplicate sources of truth for preferences | Preference category, entity, source/owner, actor, effective date | Canonical reference plus allowed Memory representation | Unknown category/owner, unauthorized update, conflicting source | Versioned canonical update | Actor/source/version/correction/supersession | Before preference memory | 18 |
| MC-36 Memory Supersession/Re-index/Deletion | Memory | Canonical data owners, embedding adapter, Retrieval, Audit | Propagate corrections and deletion to derived knowledge | Source event/version, old/new content hash, provenance, retention | Superseded item, replacement/invalidity, index/delete status | Missing source, stale event, provider failure, legal hold | Source event/content hash dedupe | Source, old/new item, model/index, outcome | Memory foundation | 18 |

### Audit and Observability

| ID / Contract name | Owner | Consumers | Purpose | Required inputs | Required outputs | Errors | Idempotency requirement | Audit requirement | Needed phase | Blocked scenarios |
|---|---|---|---|---|---|---|---|---|---|---|
| MC-37 Versioned Event Catalog/Envelope | Each producer owns semantics; Audit/Event platform owns envelope rules | All event consumers, projections, Orchestrator, Audit | Standardize immutable facts and compatibility | Event ID/type/version, workspace, actor, correlation/causation, sensitivity, typed payload | Valid event/outbox record and schema compatibility result | Invalid schema, missing tenant/correlation, incompatible version | Event ID; consumers dedupe | Event publication/delivery failures | Platform foundation | All |
| MC-38 Audit/Sensitive Read/Pre-effect Intent | Audit owns record standard; source owns evidence semantics | Policy, Orchestrator, Tools, security/support | Record mutations, sensitive reads and durable intent before effects | Actor/workspace/action/resource, policy/approval, safe diff/hash, outcome, correlation | Append-only audit ID/evidence ref | Audit unavailable, redaction failure, missing intent | Audit/event/effect key dedupe | This is the audit contract; failures block effects | Security foundation | 1, 3–9, 12–13, 19 |
| MC-39 Correlation/Actor/Delegation | Audit/Observability standard with Identity input | Every module/interface/event/tool/provider | Trace actual initiator, executor and causation | Request/workflow/step/tool/effect IDs, principal/service actor, delegation | Correlation/causation chain and actor attribution | Missing/broken chain, invalid delegation | Stable IDs propagated; no regeneration across retry | Completeness metric and defect alert | Platform foundation | All |
| MC-40 User-facing Workflow Status/Error | Orchestration projection; Executive presents | UI/API/WebSocket, Executive, support | Explain queued/running/waiting/uncertain/cancelled/failed safely | Run/step projection, normalized failure, approval/recovery state | Versioned safe status, next action, replay cursor | Projection lag, unauthorized, unknown state | Event sequence/cursor dedupe | Status access and projection lag/errors | Orchestration/UI foundation | 3–6, 11–16 |
| MC-41 Workload/Quota/Fair Scheduling | Policy owns enforcement; Usage/Orchestration measure/execute | API, Planner, Orchestrator, workers, providers, operations | Bound noisy tenants, fan-out, cost and queue starvation | Workspace/tier, workload units, current/reserved usage, provider/platform capacity | Allow/throttle/reject/reserve decision, fair scheduling metadata | Quota, budget, saturation, unavailable capacity | Reservation/command key; release idempotent | Decisions, queue delay, usage/cost, noisy-tenant alerts | Before scale acceptance | 14 |
| MC-42 WebSocket Admission/Fan-out/Replay/SLO | Realtime application/Observability | UI, Orchestration projections, operations | Keep realtime non-authoritative and bounded | Principal/workspace, topics, cursor, connection quota, retention | Authorized stream/replay or refresh directive, metrics | Unauthorized, quota, cursor expired, backpressure | Event sequence/cursor dedupe | Connections, drops, lag, replay, tenant pressure | Realtime foundation | 1–6, 14–15 |

## 7. Document reconciliation queue

This queue reproduces every inconsistency/open state DC-01 through DC-34 from
Simulation Scenario 20. No correction is applied by this document.

| ID | Document | Section | Conflict | Governing rule | Required correction | Owner decision dependency | Priority |
|---|---|---|---|---|---|---|---|
| DC-01 | PRD | §1, §6, FR-02 | Executive owns/emits plans and coordinates execution | Executive communicates; Planner decomposes; Orchestrator coordinates | Reassign lifecycle wording to the three owners | None | P1 |
| DC-02 | PRD; Technical Architecture | PRD §6; Technical §2/§3 | Context resolution lacks explicit Context Resolver owner | Resolver ranks; Retrieval filters/provides evidence | Add Resolver/Retrieval boundaries | None | P1 |
| DC-03 | PRD; Technical; Schema; API; Roadmap/Sprints | Multiple | Action and Capability are interchangeable | Capability is canonical public operation | Rename public concepts; plan uses Capability ID/version | None | P3 |
| DC-04 | Technical Architecture | §8 | Procedural Memory owns workflows/policies | Orchestration owns workflows; Policy owns policy | Remove procedural ownership; keep source-backed knowledge only | None | P1 |
| DC-05 | Technical; Folder | §3/§10; provider packages | Tools, AI providers and routing are conflated | Tool port, Adapter and AI Router have separate ownership | Split logical contracts without new services | None | P1 |
| DC-06 | Technical Architecture | §10 | Provider selection is configuration plus policy | Policy constrains; AI Router selects eligible provider | Add Router request/selection boundary | None | P1 |
| DC-07 | Technical Architecture | §3 | Billing/Usage owns quotas | Usage measures; Policy enforces budgets/quotas | Move enforcement ownership to Policy | None | P1 |
| DC-08 | Folder Structure | `db/migrations` | Central migrations obscure module ownership | Each module owns schema/migrations | Namespace/declare owner and enforce CI | None | P1 |
| DC-09 | Technical; Folder | §3; ownership boundary | Cross-module reads are not clearly prohibited | No direct cross-module DB reads/writes | Require owner Query interfaces/event projections | None | P0 |
| DC-10 | PRD; Technical; Schema | PRD §5; Technical §8; Schema §8 | Work/Content canonical data overlaps Memory facts | One canonical owner; Memory derived only | Annotate owners and source-linked derivatives | Preference taxonomy affects exact allocation | P1 |
| DC-11 | PRD | Success metric §9 | 95% consequential effects follow approval policy | 100% receive Policy evaluation | Replace metric; measure human-approval rate separately | None | P0 |
| DC-12 | PRD | FR-10 | Fallback may ignore eligibility requirements | No weaker/non-compliant fallback | Add privacy/geography/quality/cost eligibility | None | P0 |
| DC-13 | Technical Architecture | §5/§6 | “No hardcoded workflows” may prohibit deterministic engine logic | Definitions are versioned data; safety/engine invariants are code | Use constitutional definition | None | P2 |
| DC-14 | PRD; Technical | PRD §6; Technical §6 | AI critic authority is undefined | Validator first; Reviewer assesses; Orchestrator mutates | Add typed review/no-authority contract | Reviewer governance approval | P1 |
| DC-15 | Technical Architecture | Core workflow §6 | Commit-time Policy re-evaluation is absent | Re-evaluate before consequential commitment | Add snapshot and commit-time Policy step | None | P0 |
| DC-16 | PRD; Technical | Risk table; deployment | Process isolation claim conflicts with optional plugin workers | Trusted first-party may share; untrusted prohibited | Clarify trusted MVP plugin model | D-011 | P1 |
| DC-17 | Schema; API | `plans.approved_at`; plan approval | Plan acceptance may be mistaken for effect approval | Plan acceptance never authorizes effect | Separate names/models and exact action approval | None | P0 |
| DC-18 | Technical; Schema | Technical §9; child tables | Every row claim conflicts with child rows lacking workspace ID | Final tenant-column strategy must be uniform | Apply selected direct-RLS/tenant-key rule | D-016 | P0 |
| DC-19 | Technical; Schema; API; Roadmap/Sprint | Multiple | Temporal, Clerk, Redis, pgvector, S3 appear adopted | All remain Proposed | Reflect each separate owner selection | Decision 1 technologies | P2 |
| DC-20 | Schema | §5 | Temporal IDs leak into logical schema | Workflow engine stays behind Orchestration adapter | Use engine-neutral references/adapter mapping | D-006 chooses engine; correction itself neutral | P2 |
| DC-21 | API Design | §8 | Workspace workflow create/publish API exists before authoring scope | Authoring is owner-open and no-code is non-MVP | Remove/internalize/govern endpoints | D-017 | P2 |
| DC-22 | PRD | §5 | Creative used by both Website and Marketing | One Capability has one Department owner | Apply approved sole-owner map/handoffs | D-018 | P1 |
| DC-23 | Roadmap; Sprint Plan | Phases 1–4; Sprints 2/6/9/10 | Unapproved technologies/departments are scheduled as facts | Proposed decisions block dependent implementation | Replan after owner selections/ADRs | D-006–D-010, D-018 | P3 |
| DC-24 | Sprint Plan | Sprint 8 | “Executive planning” implies wrong owner | Planner decomposes; Executive clarifies/communicates | Rename and separate work | None | P3 |
| DC-25 | Technical Architecture | Event example §7 | Workflow event actor is `executive` | Audit identifies real actor/executor/causation | Define initiator/service actor/delegation | None | P1 |
| DC-26 | PRD; Owner model | NFR scale; Decision 6 | 100k users/1M workflows differ from 120k/~1.5M projection | Workload model must be approved/measurable | Reconcile targets after selection | D-020 | P3 |
| DC-27 | Technical; Roadmap | Memory §8; Phase 3 | pgvector is initial fact rather than proof | Retrieval implementation requires measured evidence | Reflect proof result and full-text baseline | D-007 | P3 |
| DC-28 | Technical; README baseline | Deployment §12 | Managed Redis is required despite defer recommendation | No unverified infrastructure; Redis never durable | Reflect selected defer/use scope | D-009 | P3 |
| DC-29 | API; Roadmap/Sprint | API §2; identity phases | Clerk is a concrete contract before proof | Identity provider remains behind adapter | Use provider-neutral identity contract; apply selection later | D-008 | P0 |
| DC-30 | Schema; API | Schema §6; API §8 | Workspace-owned workflow definitions conflict with built-in recommendation | Authoring scope requires owner decision | Reconcile schema/API after selection | D-017 | P2 |
| DC-31 | Constitution; Simulation | Reviewer/DoD; Scenario 16 | No max revision/escalation rule | Reviewer no authority; Orchestrator bounded execution | Adopt/revise Section 4 rule and contracts | Reviewer governance approval | P1 |
| DC-32 | Constitution; Simulation | Memory/Data Ownership; Scenario 18 | Preference categories lack canonical owners | Memory cannot duplicate canonical facts | Approve taxonomy and reconcile data ownership | Preference taxonomy approval | P1 |
| DC-33 | Decision Review; Decision Log | D-002/D-007 | Granular technology choices are grouped in Decision Log | Owner choices must be independent and recorded | Split ADR/decision records after response | Decision 1 | P3 |
| DC-34 | Owner Approval Session | All selection fields | No explicit owner selections exist | No implementation with unresolved blockers | Wait; never infer approval | All six decisions | P1 |

## 8. Resolution sequence

The exact recommended order is:

1. **Owner submits decisions.** Complete the eight technology selections and the
   five other decision areas. Recommendations are not consent.
2. **Validate proposed modifications for constitutional conflicts.** Reject or
   return any change that creates duplicate ownership, unsafe external effects,
   cross-tenant access, provider leakage or new workflow owners.
3. **Create ADRs.** Record only accepted choices, consequences, rejected
   alternatives and replacement boundaries.
4. **Approve Reviewer governance.** Resolve the revision limit, escalation and
   `needs_human_review` semantics.
5. **Approve preference ownership taxonomy.** Select one write/Repository owner
   for every category, including brand guidance.
6. **Define P0 and P1 missing contracts.** Complete security, tenant, ownership,
   workflow-state, policy, effect and reconciliation contracts before code that
   depends on them.
7. **Reconcile existing architecture documents.** Update PRD, architecture,
   folder, schema, API, roadmap and sprint plan only after decisions/contracts
   are authoritative.
8. **Rerun all 20 paper scenarios.** Test the reconciled documents with the same
   expected fail-closed outcomes.
9. **Require zero unresolved P0/P1 conflicts.** No safety, tenancy, ownership or
   execution-correctness issue may remain.
10. **Issue or deny implementation authorization.** Authorization must be explicit
    and scoped; it does not follow automatically from document edits.

P2 and P3 findings may remain only when explicitly documented as deferred, with
an owner and revisit trigger, and only when they do not affect security, tenant
isolation, ownership, data integrity, approval, workflow execution or failure
correctness. A terminology or roadmap label cannot be deferred if it would cause
developers to implement the wrong owner or unsafe path.

## 9. Owner response template

```text
RIGHTJOB AI OS BLOCKER RESOLUTION RESPONSE

Decision 1: Technology baseline

Modular monolith:
Selected:
Notes:

Separate API and worker processes:
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

MVP plugin trust model:
Selected:
Notes:

Initial Departments:
Selected:
Notes:

Creative Capability ownership map:
Selected:
Notes:


Decision 3: Risk and approval policy

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

workspace_id and direct-RLS rule:
Selected:
Notes:


Decision 5: Workflow authoring

Selected:
Notes:


Decision 6: Workload assumptions

Selected:
Notes:


Reviewer governance

Selected:
Notes:


Canonical preference ownership

Selected:
Notes:


Requested modifications:


Owner comments:
```

## Final status

`IMPLEMENTATION STATUS: BLOCKED`

This document does not approve technologies, modify the Constitution, create
ADRs, reconcile conflicting documents, define production contracts, or authorize
implementation.
