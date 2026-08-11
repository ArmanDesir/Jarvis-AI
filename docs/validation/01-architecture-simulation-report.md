# Architecture Simulation Report — Revalidation

**Date:** 2026-07-28  
**Scope:** Paper simulation only; no runtime security, scale, or replaceability
claim  
**Implementation status:** BLOCKED

## Basis and conventions

This rerun uses the Constitution, ADR-001 through ADR-008, the reconciled PRD,
architecture, folder, schema, API, roadmap and sprint documents, and the P0/P1
contract baseline. Every sequence implicitly begins with authentication,
TenantContext, correlation, and applicable audit. “Adapter” means an eligible
provider-neutral adapter selected through the appropriate routing/Tool contract.

## Scenario 1 — Read-only project status

1. **Request/classification/context:** “Show me…” is a deterministic query.
   Context Resolver confirms workspace, Discover Zamboanga client/project, and
   evidence; ambiguity fails safely.
2. **Exact order:** API classification → TenantContext → Context Resolver →
   Work published query/Repository → forced RLS → Policy/read audit → Executive.
   Planner, Registry, Compiler, and Orchestrator are bypassed.
3. **Selection/tools/providers:** Work status-query Capability; no Department
   execution, Tool, or AI Provider required.
4. **Policy/risk/approval:** authorized tenant read; Low; no human approval.
5. **Data/events/evidence:** Work reads; no write except access audit where
   sensitivity policy requires. Emit `work.project_status_queried.v1`; retain
   actor, tenant, query scope, result IDs, correlation.
6. **Failure/cancel/reconcile:** not-found/denied disclose no foreign data; query
   retry is safe; cancellation ends response; no compensation.
7. **Response owner/conflict/result:** Executive presents. No missing P0/P1
   contract. **PASS**.

## Scenario 2 — Draft social post

1. **Request/classification/context:** reasoning required; Executive clarifies
   channel/audience only if missing. Resolver retrieves authorized project,
   canonical Marketing brand guidance, sources, and confidence.
2. **Exact order:** Executive → Context/Memory → Registry → Planner → Plan
   Validator → Policy → Compiler → Orchestrator → Marketing/content-draft
   Capability → AI Router → AI Adapter → Validator → Reviewer → Orchestrator
   artifact/evidence → Memory/Audit → Executive.
3. **Tools/providers:** no publishing Tool; AI adapter requires structured output,
   privacy, quality, latency, cost, region/retention compatibility.
4. **Policy/risk/approval:** Low unpublished draft; no human approval.
5. **Data/events/evidence:** Marketing owns draft/brand semantics; Content may
   store generic artifact bytes; Orchestration owns run/artifact handoff; Memory
   stores indexed source-backed copy. Events cover plan, step, artifact,
   validation/review. Evidence includes sources, prompt/template version,
   provider-neutral route, output hash, scores, usage/cost.
6. **Failure/cancel/reconcile:** bounded provider retry/fallback only if all
   requirements remain satisfied; cancel stops future work; no external
   compensation.
7. **Response owner/conflict/result:** Executive presents draft and never implies
   publication. **PASS**.

## Scenario 3 — Schedule approved Facebook post

1. **Request/classification/context:** exact workspace, Facebook page connection,
   timezone, scheduled time, and immutable approved post version/hash resolve.
2. **Exact order:** Executive/command classification → Context Resolver →
   Registry → Planner/Validator when a new schedule plan is needed → Policy →
   Compiler → Orchestrator approval pause → authorized decision → scheduled
   commit-time Policy → Marketing/social-publish Capability → Social Tool →
   Facebook Adapter → reconciliation/evidence → Validator → Audit/Memory →
   Executive.
3. **Policy/risk/approval:** High; exact one-time effect approval. Plan acceptance
   is insufficient. Expiry and commit-time re-evaluation apply.
4. **Data/events/evidence:** Marketing owns content/publish operation semantics;
   Integrations owns connection/external operation; Orchestration owns schedule
   and run state; Policy owns approval. Snapshot hash, approver authority,
   destination, schedule, provider reference, idempotency key, outcome retained.
5. **Failure/cancel/reconcile:** retry only on normalized safe failures; unknown
   outcome triggers provider lookup/reconciliation, never blind repost. Cancel
   before commit removes schedule; after commit reports too late and may propose
   a separately governed deletion.
6. **Response owner/conflict/result:** Executive reports scheduled/committed,
   reconciliating, or failed. **PASS**.

## Scenario 4 — Build a five-page restaurant website

1. **Request/classification/context:** incomplete client, scope, brand, content,
   budget, domain, hosting, and deadline require Executive clarification and
   source-backed Context resolution.
2. **Exact order:** Executive → Context/Memory → Registry → Planner →
   Plan Validator → Policy → Compiler → Orchestrator → Marketing Creative
   Capabilities and Website Capabilities as separate steps → versioned artifact
   handoffs through Orchestrator → Validators/Reviewers → approval pause before
   live effect → Website deployment Capability/Tool/Adapter → evidence →
   Memory/Audit → Executive.
3. **Ownership:** Marketing solely owns brand/visual/creative artifacts; Website
   owns information architecture, UI composition, implementation and QA.
   Departments never call each other.
4. **Policy/risk/approval:** drafts/plan Low; internal tasks Medium; live update
   High; production application-code deployment Critical. Exact applicable
   approval is required before commitment.
5. **Data/events/evidence:** Work owns client/project; domains own their
   artifacts/rules; Orchestration owns workflow state. Versioned plan, workflow,
   Capability, artifact, validation/review and deployment evidence are emitted.
6. **Failure/cancel/reconcile:** engine-neutral durable state supports waits,
   retries, restart, bounded review, cancellation, retained completed drafts,
   and compensation/rollback where deployment supports it.
7. **Response owner/conflict/result:** Executive consolidates. Creative ownership
   is resolved by ADR-002. Engine implementation remains proof-gated but the
   contract is sufficient for architecture. **PASS**.

## Scenario 5 — Change live homepage headline

1. **Request/classification/context:** resolve exact client/site/environment,
   current revision and proposed headline; ambiguity blocks.
2. **Order/selection:** Executive → Context → Registry → Planner/Validator when
   drafting is needed → Policy → Compiler/Orchestrator → Website content-change
   Capability → Validator/optional Reviewer → exact approval → commit-time
   Policy → Website Tool → deployment/CMS Adapter → evidence → Executive.
3. **Policy:** live modification High; exact one-time approval. Any text, target,
   environment, artifact, or provider change invalidates it.
4. **Owners/evidence:** Website owns site change rules; Integrations owns
   connection/operation; Orchestrator state; Policy approval. Audit before/after
   hashes, revision, approver, idempotency, provider result and rollback ref.
5. **Failure/cancel/compensation:** optimistic version check; safe retry only with
   idempotency; unknown outcome reconciled; rollback is a governed compensating
   action. Pre-commit cancellation prevents change.
6. **Response/result:** Executive presents. **PASS**.

## Scenario 6 — Email the client

1. **Request/classification/context:** resolve exact client/recipient and campaign;
   generate a draft, then freeze recipients, subject, body, attachments and
   sender connection.
2. **Order/selection:** Executive → Context → Registry → Planner/Validator →
   Policy → Orchestrator → Operations email-draft Capability → AI Router/Adapter
   if needed → Validator/Reviewer → snapshot approval → commit Policy →
   Email Tool → Email Adapter → reconcile/audit → Executive.
3. **Policy:** sending is High and requires exact one-time approval; draft is Low.
4. **Owners/evidence:** Work owns contact; Operations owns communication business
   operation; Integrations external record; Policy approval; Orchestration state.
   Retain snapshot hash, recipient source, approver, idempotency, provider ID,
   delivery status and safe content reference.
5. **Failure/cancel/reconcile:** no duplicate send; timeout after submission is
   `outcome_unknown` and reconciled before retry. Cancel before commit stops send;
   sent mail cannot be compensated.
6. **Response/result:** Executive presents. **PASS**.

## Scenario 7 — Delete every client and project

1. **Classification/context:** Critical bulk destructive command; exact scope,
   authority, dependencies and recovery state must resolve without AI database
   access.
2. **Order:** classification → TenantContext → Policy → deny, or exceptional
   recovery-capable workflow/dual approval when a separately enabled exact policy
   exists → Orchestrator → owner-domain Capabilities/Repositories → Audit.
3. **Tools/providers:** no AI/provider required; no direct SQL or cross-module
   repository access.
4. **Policy/approval:** fail closed. MVP prohibits permanent bulk destruction
   without recovery safeguards and explicit Critical approval; dual approval
   applies when supported.
5. **Evidence/failure:** scope manifest/count/hash, dependencies, backup/restore
   verification, approvers, policy version, deletion/tombstone evidence.
   Partial completion reconciles per owning aggregate; retry is idempotent.
6. **Response/result:** Executive safely refuses or explains gated recovery-safe
   procedure without confirming inaccessible data. **PASS**.

## Scenario 8 — Cross-tenant request

1. **Classification/context:** authentication resolves Workspace A membership;
   requested Workspace B lacks authorization.
2. **Order:** API → TenantContext denial → security audit/alert → Executive.
   Resolver, repository, cache, retrieval and object store receive no Workspace B
   access context.
3. **Policy/risk/approval:** denied; approval cannot override membership/RLS.
4. **Data/evidence:** no Workspace B read/write. Forced RLS, composite FKs,
   tenant-prefixed cache/object/vector keys are defense in depth. Audit records
   requesting actor, attempted scope, denial and correlation without target data.
5. **Failure/retry/cancel:** repeated attempts may rate-limit/alert; no
   compensation.
6. **Response/result:** Executive says the request cannot be fulfilled and does
   not confirm whether Workspace B or its clients exist. **PASS**.

## Scenario 9 — Prompt injection in an upload

1. **Classification/context:** uploaded text is untrusted content, not an
   instruction; scan/provenance/sensitivity and tenant permissions apply.
2. **Order:** ingestion boundary → scan/UntrustedContent contract → Content owner
   → Retrieval filtering → AI context as quoted data only → deterministic
   validation/Policy → Audit → Executive.
3. **Tools/providers:** retrieved content cannot invoke a Tool or select a
   provider; secrets/credentials are never prompt data.
4. **Policy/risk/approval:** exfiltration/send request is denied before any
   effect; no approval can be inferred from document text.
5. **Evidence/failure:** content hash/source, detection, blocked instruction,
   route/policy decision and security event. Unsafe ingestion fails closed.
6. **Response/result:** Executive explains the document was treated as content.
   **PASS**.

## Scenario 10 — Provider replacement

1. **Execution:** the same Marketing content-draft Capability invokes AI Router
   three times with identical AI requirements through Provider A, fake adapter,
   and Provider B.
2. **Unchanged contracts:** Executive, Planner, Orchestrator, Department,
   Capability, Repository/database, artifact and user result schemas remain
   unchanged.
3. **Adapter-only data:** vendor request/response types, auth, error mapping and
   raw model fields remain inside adapters. Normalized provider identity,
   capability, usage and cost may appear in audit evidence.
4. **Validation/failure:** each output passes the same schema/Validator/Reviewer.
   Ineligible provider is rejected rather than weakening requirements.
5. **Result:** paper replaceability is consistent; technical demonstration still
   requires contract tests/fakes during implementation. **PASS**.

## Scenario 11 — Provider outage

1. **Order:** failing Tool/AI Adapter → normalized failure → Orchestrator retry
   policy or AI Router/Tool routing fallback evaluation → eligible fallback or
   typed unavailable → Audit/status → Executive.
2. **Policy:** fallback must satisfy privacy, region, retention, modality,
   structured-output/tool, quality, cost and workspace restrictions; no silent
   weaker fallback.
3. **Evidence:** attempts, timeouts, candidate/rejection reasons, selected route,
   cost/usage and workflow status.
4. **Cancellation/recovery:** bounded retry/backoff; cancellation stops new
   attempts; durable workflow resumes after recovery. Unknown external effects
   reconcile before retry.
5. **Result:** **PASS**.

## Scenario 12 — Worker crash after external call

1. **Order:** Orchestrator records intended effect/idempotency → Tool/Adapter call
   → crash before result persistence → durable restart → mark/retain
   `outcome_unknown` → reconcile by provider reference/idempotency → persist
   committed or retry-safe result → Audit/Executive.
2. **Ownership:** Orchestrator solely owns workflow state; Integrations owns the
   external-operation record; adapter mapping owns engine/provider IDs.
3. **Policy/evidence:** original approval and commit-time policy must remain
   valid; evidence links attempt and reconciliation.
4. **Engine finding:** the contract can be implemented by managed Temporal or a
   carefully transactional PostgreSQL job/state machine. The authorized proof
   must establish which meets the chosen MVP workflow breadth; no production
   engine is selected yet.
5. **Result:** architecture is engine-neutral and safe on paper. **PASS**.

## Scenario 13 — Approval becomes stale

1. **Order:** content/destination mutation creates a new artifact/effect hash →
   commit-time Policy compares snapshot → invalidates approval → Orchestrator
   stays/returns to `awaiting_approval` → new authorized decision → commitment.
2. **Policy:** High; no reuse of the old one-time approval.
3. **Evidence:** old/new hashes, changed fields, invalidation reason, policy
   versions, approver and timestamps.
4. **Failure/cancel:** no provider call occurs while stale; cancellation ends the
   pending run.
5. **Result:** **PASS**.

## Scenario 14 — Noisy tenant

1. **Order:** request admission → TenantContext/Policy quota → per-workspace
   Orchestrator queue/concurrency → AI Router/Tool provider rate limits →
   WebSocket backpressure/projection → metrics/alerts.
2. **Controls:** bounded fan-out/payload/tokens, reservations, fair queues,
   per-tenant connection/cost limits, global safety ceilings and provider
   backoff. Redis is not required for correctness; it may be introduced only
   after measured multi-instance need.
3. **Evidence/failure:** throttling decisions, queue age, saturation, costs,
   dropped/coalesced non-authoritative realtime updates, noisy-neighbor alerts.
4. **Scale:** ADR-006 supplies planning assumptions only; telemetry and load tests
   must set thresholds and prove behavior.
5. **Result:** **PASS** as architecture; capacity remains unproven.

## Scenario 15 — Cancel active website workflow

1. **Classification/order:** eligible deterministic cancel → TenantContext →
   Policy/authorization → Orchestrator cancellation signal → stop unscheduled
   steps → provider cancellation if supported → persist terminal/partial state →
   Audit → Executive.
2. **State/artifacts:** completed drafts remain with retention/provenance; running
   image request is cancelled or its late result quarantined; no deployment step
   can start.
3. **Failure/compensation:** cancellation is idempotent; unsupported provider
   cancellation is monitored to terminal state. No live effect means no
   compensation.
4. **Result:** **PASS**.

## Scenario 16 — Reviewer disagrees

1. **Order:** Validator pass → Reviewer structured low-quality assessment →
   Orchestrator evaluates declared revision policy → Capability revision →
   repeat no more than twice → `needs_human_review` → Executive/user or
   authorized Department owner.
2. **Authority:** Reviewer cannot authorize, call Tools, select approvers, bypass
   Policy, or mutate state.
3. **Evidence:** artifact/criteria/reviewer versions, scores, reasons, evidence,
   attempt count, cost and state decision are durable.
4. **Failure/cancel:** non-improvement and cost/deadline boundaries can escalate
   earlier; cancellation stops revision. No third automatic cycle.
5. **Result:** ADR-007 resolves the former defect. **PASS**.

## Scenario 17 — Unsupported Capability

1. **Order:** Executive/Context → Registry discovery → Planner receives no
   eligible Capability → Plan Validator rejects unsupported step → Executive.
2. **Policy/tools/providers:** no arbitrary Tool, provider, code, plugin, or
   invented Capability call occurs.
3. **Evidence:** requested operation, enabled Registry versions, rejection reason,
   correlation and optional future-Capability proposal.
4. **Result:** **PASS**.

## Scenario 18 — Correct an outdated client preference

1. **Order:** Executive → Context Resolver/Retrieval → Policy → canonical owner
   correction command/Repository → domain event → Memory supersede/re-index →
   Audit → Executive.
2. **Known ownership:** Marketing owns brand/visual preferences; Website owns
   site preferences; Working Memory owns expiring task instructions; originating
   domain owns historical decisions; derived inference is non-canonical.
3. **Blocker:** exact owners remain ambiguous for client identity/contact,
   contractual requirements, project delivery preferences, and workspace-member
   communication preferences. The phrase “A or B” violates one-owner rules.
4. **Safety behavior:** if the correction category is ambiguous, no write occurs;
   Memory cannot silently become canonical. Provenance and supersession are
   retained after a valid domain correction.
5. **Result:** **BLOCKED — exact owner selection required in ADR-008**.

## Scenario 19 — Unauthorized Critical approval

1. **Order:** approval command → TenantContext/role resolution → Policy denies →
   approval remains pending and workflow does not resume → security audit →
   Executive.
2. **Policy:** ordinary member cannot approve Critical deployment; required
   owner/security admin/designated senior admin and applicable dual approval.
3. **Evidence:** actor, roles, requested approval/snapshot hash, denial rule,
   workflow unchanged, correlation.
4. **Response:** safe denial without sensitive operational details. **PASS**.

## Scenario 20 — Document consistency

The reconciled PRD, technical architecture, folder structure, logical schema,
API, roadmap, sprint plan, Constitution, ADRs, and P0/P1 contracts now agree on
module boundaries, Capability terminology, direct RLS, Creative ownership,
workflow state ownership, provider neutrality, Reviewer governance, approval
hashing, event actors, plugin trust, and proof/defer status.

| ID | Document/section | Remaining conflict | Governing rule | Severity | Required correction | Owner approval |
|---|---|---|---|---|---|---|
| R-01 | ADR-008; Memory/Data Ownership | Four preference categories name alternative canonical owners | One record/rule has exactly one owner | P1 High | Owner chooses one module for each; then reconcile schema/API/domain language | Yes |
| R-02 | Historical conflict/review/session reports | Pre-decision reports retain “proposed/open” statements | Historical reports must not be silently rewritten | Informational | Keep immutable; ADRs and decision log supersede them | No |

Because R-01 is unresolved P1 ownership, document consistency does not pass the
implementation gate. **FAIL**.

## Scenario results

| Scenario | Result | Blocking issue | Owner decision required |
|---|---|---|---|
| 1 Read project | PASS | — | No |
| 2 Draft social | PASS | — | No |
| 3 Publish social | PASS | — | No |
| 4 Build website | PASS | — | No |
| 5 Live headline | PASS | — | No |
| 6 Send email | PASS | — | No |
| 7 Bulk deletion | PASS | Fails closed unless exact Critical policy exists | No new decision |
| 8 Cross-tenant attack | PASS | — | No |
| 9 Prompt injection | PASS | — | No |
| 10 Provider replacement | PASS | Runtime contract proof remains future work | No |
| 11 Provider outage | PASS | — | No |
| 12 Worker crash | PASS | Engine proof must select implementation | No; proof result |
| 13 Stale approval | PASS | — | No |
| 14 Noisy tenant | PASS | Capacity unproven | No; measurement |
| 15 Cancel workflow | PASS | — | No |
| 16 Reviewer disagrees | PASS | — | No |
| 17 Unsupported Capability | PASS | — | No |
| 18 Memory correction | BLOCKED | Four canonical preference owners ambiguous | Yes |
| 19 Unauthorized approval | PASS | — | No |
| 20 Document consistency | FAIL | R-01 P1 ownership conflict | Yes |

**Counts:** PASS 18; PASS WITH OWNER DECISION 0; FAIL 1; BLOCKED 1.

## Component coverage

| Component | Scenarios |
|---|---|
| Executive AI | 1–9, 11–19 |
| Context Resolver / Memory | 1–9, 17–18 |
| Planner / Plan Validator | 2–6, 10–11, 17 |
| Policy / Approval | 1–9, 11–15, 18–19 |
| Registry / Compiler / Orchestrator | 2–7, 10–17 |
| Departments / Capabilities | 2–7, 10–13, 15–18 |
| Tool Interfaces / Provider Adapters / AI Router | 2–6, 9–13, 15 |
| Validator / Reviewer | 2–6, 10, 16 |
| Repositories / Database/RLS | 1, 3–9, 12–14, 18–19 |
| Audit / Observability | All scenarios |

## Contract status

The previous 42-item register is sequenced by
`docs/contracts/00-p0-p1-architecture-contracts.md`. P0 and P1 semantics now have
an authoritative baseline. Concrete versioned schemas and contract tests remain
required before implementing each boundary. The only unresolved ownership
contract is canonical preference routing for the four ADR-008 categories.

## Final architecture verdict

**BLOCKED**

The architecture is materially safer and consistent for 18 scenarios, but it
cannot receive `VALIDATED` or `VALIDATED WITH CONDITIONS` while the P1 canonical
preference ownership conflict remains. The technology proofs also must not be
misrepresented as production adoption or capacity proof.

Implementation is not authorized.
