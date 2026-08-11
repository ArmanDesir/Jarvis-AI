# Implementation phase status

## Phase 1 — Repository Bootstrap

Implemented with environment conditions. See
`01-repository-bootstrap-report.md`.

## Explicitly unavailable

- Business Capabilities and business persistence
- Executive AI, prompts, model calls, and AI routing behavior
- Workflow compilation/execution
- Authentication flows
- Memory retrieval
- Provider Adapters and external effects
- Third-party plugins
- Production deployment automation

## Proof gates

| Technology | Status |
|---|---|
| Temporal | Phase 2.5 passed; Managed Temporal adopted by owner on 2026-08-11 |
| Clerk/Auth.js comparison | Not started |
| `pgvector` | Not started |
| Redis | Deferred |

Phases 2.1 through 2.5 are accepted. Managed Temporal is the approved Durable
Workflow Engine; production implementation remains behind the provider-neutral
orchestration contract.

## Phase 2.6 — Audit Evidence & Transactional Outbox Foundation

The owner designated Audit Evidence & Transactional Outbox Foundation as the
canonical Phase 2.6 objective on 2026-08-11. Source-only implementation is
complete. The required migration and PostgreSQL verification remain approval-gated.
