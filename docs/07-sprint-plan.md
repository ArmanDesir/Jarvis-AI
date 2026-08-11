# Sprint Plan

**Status:** Reconciled plan; implementation gate remains closed  
**Cadence:** Two-week sprints  
**Scope:** First 12 sprints through production beta

No sprint begins implementation until the architecture approval gate closes.

## Sprint 0 — Approval and proof

**Goal:** Retire the highest architectural risks.

- Review PRD, architecture, schema, API, and threat model.
- Record accepted ADRs, proof gates, and ADR-008 canonical owners.
- Prove durable approval pause/resume and worker restart.
- Prove RLS isolation and structured planner validation.
- Define golden evaluation cases and engineering quality gates.

**Review:** Demonstrate proofs, rerun paper validation, and issue or deny explicit
implementation authorization.

## Sprint 1 — Repository and delivery foundation

- Establish monorepo tooling and dependency boundaries.
- Add local Docker environment and initial PostgreSQL migrations.
- Add CI for formatting, types, tests, migrations, and container scanning.
- Add structured logging, correlation IDs, health/readiness endpoints.

**Review:** Clean checkout reaches a healthy stack and CI blocks a broken change.

## Sprint 2 — Identity and tenancy

- Integrate the identity adapter selected after the Clerk/Auth.js proof and local user mapping.
- Implement workspaces, memberships, roles, and scoped request context.
- Enable RLS and isolation integration tests.
- Add audit entries for identity and membership mutations.

**Review:** Two workspaces cannot read or mutate each other by API or repository.

## Sprint 3 — Agency work core

- Implement clients, projects, tasks, decisions, and meetings.
- Add optimistic concurrency and cursor pagination.
- Create minimal accessible web views for daily work.
- Publish generated TypeScript API types.

**Review:** Agency owner can manage work records with complete audit history.

## Sprint 4 — Conversations and realtime

- Implement conversations, messages, and streaming response envelope.
- Add WebSocket cursor/reconnect and outbox-backed progress events.
- Build the single Executive chat surface.
- Add deterministic fake Executive provider for tests.

**Review:** A conversation survives reconnect without missing or duplicating state.

## Sprint 5 — Registry and plugin SDK

- Validate signed-in-build department manifests and JSON Schemas.
- Implement activation/version pinning and capability lookup.
- Provide typed Capability context, results, cancellation, and idempotency helpers.
- Add a fake reference department and contract test kit.

**Review:** A plugin is registered and replaced without changing Executive code.

## Sprint 6 — Durable orchestration

- Implement typed plans, DAG validation, and the selected Workflow Engine adapter.
- Add retries, timeouts, heartbeats, cancellation, and run timeline.
- Record artifacts, errors, external operations, usage, and evidence.
- Add workflow replay and worker-failure tests.

**Review:** A multi-step run survives restart and never duplicates side effects.

## Sprint 7 — Policy and approvals

- Implement RBAC-backed policy evaluation and budget reservation.
- Build approval inbox, decision history, expiry, and resume signals.
- Define conservative default policies for external communication/publishing.
- Add concurrent-decision and tamper tests.

**Review:** High-risk work cannot execute without an authorized valid approval.

## Sprint 8 — Executive planning

- Add first production AI adapter behind the provider port.
- Implement intent extraction, capability-constrained planning, and validation.
- Add review/result synthesis with evidence references.
- Gate changes with routing and safety evaluations.

**Review:** Supported prompts choose only valid Departments/Capabilities; unsupported or
ambiguous requests fail safely.

## Sprint 9 — Memory and knowledge

- Implement memory items, provenance, sensitivity, and corrections.
- Add full-text/entity retrieval; enable vectors only after the approved proof gate.
- Ingest SOPs, brand profiles, and scanned files.
- Add retention and cross-tenant retrieval tests.

**Review:** Prior-project continuation meets the approved evaluation threshold.

## Sprint 10 — Website and Marketing departments

- Deliver Website planning/implementation/QA Capabilities.
- Deliver Marketing strategy/copy/SEO/Creative Capabilities.
- Add one governed social publishing adapter.
- Test cross-department plan and Executive consolidation.

**Review:** Representative website and campaign requests complete end to end.

## Sprint 11 — Operations department and daily brief

- Deliver CRM lead prioritization and follow-up actions.
- Add email/calendar adapters with approval and idempotency.
- Build daily brief projections and Executive presentation.
- Add provider failure and partial-success scenarios.

**Review:** Daily brief is source-backed; approved lead follow-up is traceable.

## Sprint 12 — Voice and beta hardening

- Add STT/TTS adapters and browser voice flow.
- Run load, accessibility, security, backup/restore, and failure drills.
- Finish SLO dashboards, alerts, quotas, runbooks, and beta onboarding.
- Complete release review against PRD acceptance criteria.

**Review:** Production-beta go/no-go review.

## Sprint controls

Each sprint has a product demo, architecture/security review for changed
boundaries, evaluation report for AI behavior, and retrospective. Work not
meeting the shared definition of done returns to the backlog; it is not counted
as complete.

## Suggested initial team

- 1 product manager/domain owner
- 1 technical lead
- 2 backend/platform engineers
- 2 frontend/full-stack engineers
- 1 AI/evaluation engineer
- Shared product design, QA automation, DevOps/SRE, and security support

With fewer people, keep the sprint order and reduce parallel scope rather than
removing isolation, approval, audit, or recovery controls.
