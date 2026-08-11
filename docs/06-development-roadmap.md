# Development Roadmap

**Status:** Reconciled plan; implementation gate remains closed  
**Planning assumption:** Two cross-functional squads after foundation; dates are
set only after staffing and integration access are confirmed.

## Phase 0 — Decisions and validation

**Outcome:** Approved product boundary and executable architectural proof.

- Approve this architecture pack and create decision records.
- Threat model tenant isolation, AI/tool boundaries, and external side effects.
- Run the authorized managed-Temporal, Clerk/Auth.js, and `pgvector` proofs.
- Prototype PostgreSQL RLS, structured AI output, and WebSocket replay.
- Establish measurable AI routing/context evaluation dataset.

**Exit gate:** ADRs and P0/P1 contracts are complete, all paper scenarios rerun,
and implementation is explicitly authorized. Proof code is disposable.

## Phase 1 — Platform foundation

**Outcome:** Secure multi-tenant shell deploys continuously.

- Monorepo, CI, Docker, environments, migrations, observability.
- Identity adapter selected after Clerk/Auth.js proof; local principals,
  workspaces, membership, RBAC, and forced RLS.
- FastAPI/Next.js shells, WebSocket event stream, transactional outbox.
- Clients/projects/tasks and append-only audit.

**Exit gate:** Tenant isolation, authorization, migration, restore, and deployment
tests pass.

## Phase 2 — Executive and orchestration kernel

**Outcome:** A typed request becomes a durable, observable plan.

- Conversation and message model with streaming.
- Provider-neutral AI port and first adapter.
- Intent/context schema, plan DAG, department registry, plugin SDK.
- Selected Workflow Engine adapter with retry, timeout, cancel, evidence, and
  worker restart.
- Policy evaluation, approval inbox, usage/cost ledger.

**Exit gate:** A fake department completes, pauses, resumes, retries, and cancels
through the UI with a full audit timeline.

## Phase 3 — Memory and agency context

**Outcome:** The Executive can reliably continue prior work.

- Memory extraction with provenance and sensitivity.
- PostgreSQL full-text/entity retrieval; adopt `pgvector` only if its proof gate passes.
- Conversation compaction, project/client context, corrections, and retention.
- SOP, brand profile, file ingestion, and untrusted-content controls.
- Daily brief projection and generation.

**Exit gate:** Context-resolution evaluation meets agreed accuracy and isolation
thresholds; “continue yesterday’s project” works with ambiguity handling.

## Phase 4 — Initial departments

**Outcome:** Three real agency workflows deliver governed results.

- Website Capabilities: brief, plan, information architecture, implementation, QA.
- Marketing Capabilities: strategy, copy, SEO, all approved Creative ownership,
  approval-ready publishing.
- Operations Capabilities: lead prioritization, follow-up draft/send, calendar/email.
- Provider adapters and integration credential lifecycle.
- Cross-department plans and consolidated Executive reporting.

**Exit gate:** One representative workflow per department passes contract,
failure-injection, approval, and end-to-end acceptance tests.

## Phase 5 — Voice and operational hardening

**Outcome:** Production beta supports voice and recoverable operations.

- Streaming STT/TTS adapters and browser session flow.
- SLO dashboards, alerts, runbooks, backup/restore drills.
- Rate limits, quotas, model routing, cost controls.
- Security testing, accessibility audit, load testing, disaster recovery.

**Exit gate:** Beta SLOs, security controls, WCAG 2.2 AA core flows, and recovery
objectives are demonstrated.

## Phase 6 — Beta and general availability

**Outcome:** Agencies onboard safely with measurable product value.

- Design-partner onboarding and workspace configuration.
- Evaluation feedback loop and prompt/model release gates.
- Support tooling with audited access.
- Billing entitlements, data export/deletion, compliance preparation.

**Exit gate:** Product metrics, reliability, support load, and security review meet
the launch checklist.

## Deferred until evidence

- Kafka or another streaming platform.
- A separate vector database.
- Department microservices.
- Third-party executable plugin marketplace.
- Visual workflow builder.
- Multi-region active-active deployment.
- Proprietary model training.

## Cross-cutting definition of done

A feature is complete only when:

- Acceptance criteria and failure behavior are documented.
- Authorization, tenant isolation, audit, and idempotency are reviewed.
- Unit/contract/integration tests match its risk.
- Telemetry, usage, and operational errors are visible.
- Accessibility and privacy requirements are met.
- Documentation and runbooks are updated.
- Product review accepts the user outcome.
