# P0/P1 Architecture Contracts

**Status:** Normative design baseline; implementation not authorized  
**Date:** 2026-07-28

These contracts define the minimum safety and ownership boundaries required
before implementation. Concrete API/schema encodings remain implementation work.

## Common envelope

Every command, query, event, workflow, step, Capability invocation, Tool call,
provider request, approval, and effect carries:

- contract name/version, request ID, correlation ID, causation ID;
- workspace ID and authenticated actor/principal;
- sensitivity, deadline, and idempotency scope where applicable;
- typed payload and typed success/error result.

Missing tenant, actor, contract version, or correlation fails closed.

## P0 contracts

### TenantContext

**Owner:** Identity/Tenancy.  
**Input:** verified external identity, requested workspace, request metadata.  
**Output:** internal principal, membership, roles, workspace, authentication
evidence.  
**Errors:** unauthenticated, non-member, suspended, ambiguous workspace.

All tenant repositories require this context. Every tenant table has non-null
`workspace_id`, forced RLS, and tenant-aware foreign keys. Jobs establish a
service principal and workspace before access. Retrieval, cache, object, and
projection keys include workspace. CI proves cross-tenant read/write denial.

### PolicyDecision

**Owner:** Policy.  
**Input:** actor, workspace, typed operation, resource/effect snapshot, risk,
permissions, sensitivity, budget/quota, policy version.  
**Output:** allow, deny, or approval-required; approver rule, expiry, restrictions,
and decision evidence.  
**Errors:** missing policy, stale context, unclassifiable effect, budget exceeded.

Policy runs before execution and immediately before consequential commitment.
Workspace rules may tighten but cannot weaken platform minimums.

### ApprovalSnapshot

**Owner:** Policy/Approval.  
**Input:** exact effect including recipient/target, destination/environment,
content/artifact hash, amount, provider/connection, operation, risk, policy
version, and expiry.  
**Output:** immutable request and append-only decisions bound to a canonical
snapshot hash.  
**Errors:** unauthorized approver, expired, changed snapshot, insufficient
approvers, conflicting decision.

Plan acceptance is not action approval. Any material change invalidates approval.
High risk requires exact one-time approval unless a policy explicitly permits a
scoped reusable permission. Critical actions follow ADR-003, including dual
approval where supported. Commit-time re-evaluation is mandatory.

### ExternalEffect

**Owner:** Orchestrator for commitment; Tool Interface/Adapter for execution.  
**Input:** valid Policy decision, valid approval when required, immutable effect
snapshot, stable idempotency key, credential reference, timeout.  
**Output:** committed, rejected, failed, or `outcome_unknown`, with provider
reference and evidence.  
**Errors:** policy/approval stale, timeout, provider rejection, ambiguous outcome.

No blind retry follows `outcome_unknown`. Orchestrator reconciles by idempotency
key/provider status before retry, compensation, or human escalation. Audit
evidence must be durably available before commitment.

### TenantRepository

**Owner:** owning domain.  
**Input:** TenantContext plus typed aggregate/query identifier.  
**Output:** owning aggregate or published query DTO.  
**Errors:** denied, not found without cross-tenant disclosure, concurrency,
constraint, unavailable.

Repositories cannot decide business outcomes or access another module’s tables.
Cross-module reads use published queries or owned projections.

### UntrustedContent

**Owner:** ingestion/security boundary.  
**Input:** uploaded/retrieved content, provenance, sensitivity, scan state.  
**Output:** content explicitly labelled as data, safe excerpts, access decision.  
**Errors:** malware, unsupported type, unauthorized source, unsafe content.

Retrieved text never becomes authority, Tool instructions, Policy, secrets, or
code. AI-generated SQL or code cannot execute outside separately approved policy
and sandbox contracts.

## P1 contracts

### CommandClassification and ContextResolution

**Owners:** Executive for communication/classification presentation; Context
Resolver for references.  
**Input:** authenticated user input and eligible source/query results.  
**Output:** deterministic-command or reasoning-required classification; ranked,
workspace/permission-filtered references with evidence and confidence.  
**Errors:** ambiguous, missing, denied, stale.

Simple commands may bypass AI and Planner, but never tenancy, Policy, validation,
or audit.

### PlanProposal and PlanValidation

**Owners:** Planner; deterministic Plan Validator.  
**Input:** approved goal/context and enabled Registry Capability contracts.  
**Output:** versioned typed DAG with Capability IDs/versions, inputs, dependencies,
risks, constraints, and requested artifacts; then valid/invalid evidence.  
**Errors:** unsupported Capability, cycle, schema mismatch, missing dependency,
unbounded work.

AI output is untrusted. Planner cannot invent Capabilities, execute, authorize,
or persist.

### WorkflowCompilation and WorkflowState

**Owner:** Orchestration.  
**Input:** validated plan, pinned built-in definition/contract versions, Policy
decisions.  
**Output:** engine-neutral immutable workflow definition and durable workflow
instance.  
**Errors:** incompatible version, invalid dependency, unsupported engine feature.

Orchestrator solely owns run/step state, scheduling, retry, timeout, cancellation,
compensation, approval pauses, evidence, and reconciliation. Engine IDs stay in
adapter mappings, not domain/public contracts. MVP definitions are built-in only.

### CapabilityInvocation and ArtifactHandoff

**Owners:** owning Department/Capability; Orchestrator coordinates handoff.  
**Input:** pinned Capability contract, typed input, workspace/actor, Policy
reference, deadline/cancellation, approved Tool/AI requirements.  
**Output:** typed result, immutable artifact/version/hash, evidence, validation
requirements, normalized errors/events.  
**Errors:** invalid input, denied, unavailable dependency, timeout, cancelled,
partial result.

One Capability has one Department owner. Departments never call each other.
Marketing owns Creative artifacts consumed by Website through Orchestrator.

### ToolInvocation and ProviderInvocation

**Owners:** vendor-neutral Tool Interface; Provider Adapter for vendor behavior.  
**Input:** typed operation, credential reference, idempotency key, deadline,
tenant/policy context.  
**Output:** normalized result/status/evidence/usage/cost.  
**Errors:** unavailable, rate-limited, rejected, timeout, unknown outcome.

Provider SDK types and vendor-specific fields stay inside adapters. Normalized
provider identity may appear in audit/usage evidence. Fakes must satisfy the same
contract.

### AICapabilityRoute

**Owner:** AI Router.  
**Input:** structured-output/tool/context/modality requirements, privacy,
workspace configuration, cost, latency, quality, availability, geography,
retention, fallback eligibility.  
**Output:** eligible adapter route or typed unavailable result, with rejection
reasons.  
**Errors:** no eligible provider, restriction conflict, exhausted budget.

Fallback cannot silently weaken a declared requirement.

### Validation and Review

**Owners:** Validator for deterministic checks; Reviewer for qualitative
assessment; Orchestrator for state.  
**Input:** immutable artifact hash/version and versioned criteria.  
**Output:** Validator pass/fail evidence; Reviewer structured scores, reasons,
evidence, and recommendation.  
**Errors:** invalid criteria, low confidence, non-improvement, unavailable.

Reviewer cannot approve, call Tools, bypass Policy, or mutate state. Orchestrator
allows at most two automated revision cycles, then sets `needs_human_review`.

### MemoryRetrieval and Correction

**Owners:** Retrieval Service and canonical domain owner.  
**Input:** TenantContext, permission/sensitivity filters, query, source scope.  
**Output:** ranked source-backed items with confidence and canonical/derived
status.  
**Errors:** denied, deleted/superseded, low confidence, ambiguous owner.

Corrections update the canonical module first; derived memory is refreshed or
superseded. Work owns client/contact, contractual/engagement, and project-delivery
preferences. Identity/Tenancy owns workspace-member communication preferences.
Marketing and Website retain their accepted preference categories in ADR-008.

### AuditEvidence

**Owner:** Audit/Observability policy and retention; each producer supplies
evidence for its action.  
**Input:** actual actor/executor, workspace, operation, resource/effect hash,
policy/approval refs, outcome, correlation/causation, safe before/after/evidence.  
**Output:** append-only durable audit reference.  
**Errors:** unavailable, invalid actor, secret/sensitive payload violation.

An audit outage blocks consequential commitment unless an owner-approved durable
buffer contract preserves the record.

### QuotaAndFairness

**Owner:** Policy for limits; Orchestrator/AI Router/Tool adapters enforce their
bounded concurrency.  
**Input:** workspace, workload/cost class, current reservations/usage, provider
limits.  
**Output:** allow, throttle, queue, or deny with retry time and evidence.  
**Errors:** quota exceeded, noisy tenant, provider saturation.

Per-workspace concurrency, queue fairness, token/cost ceilings, payload/fan-out
limits, and backpressure protect other tenants. Thresholds begin from ADR-006
planning assumptions and must be recalibrated from telemetry.

## Implementation gate

All P0 contracts and applicable P1 contracts need versioned schemas, fake/contract
tests, ownership, failure semantics, and audit fields before their feature may
enter implementation. No unresolved P0/P1 ownership blocker remains in this
contract baseline.
