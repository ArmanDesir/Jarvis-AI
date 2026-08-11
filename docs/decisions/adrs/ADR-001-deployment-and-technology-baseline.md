# ADR-001: Deployment and Technology Baseline

**Status:** Accepted, with proof gates  
**Decision date:** 2026-07-28  
**Owner authority:** Explicit owner response

## Durable Workflow Engine adoption

**Approved:** 2026-08-11  
**Owner decision:** Adopt Managed Temporal as the Durable Workflow Engine for
Rightjob AI OS based on the completed Phase 2.5 proof.

Temporal remains infrastructure behind the provider-neutral
`DurableWorkflowEngine` contract. It does not own business rules, Policy,
authorization, Departments, canonical business data, Memory, Capability
definitions, or user communication. Production deployments use Managed
Temporal; self-hosted production Temporal remains prohibited.

## Phase 2.5 development exception

**Approved:** 2026-08-07  
**Scope:** Phase 2.5 development verification only

A localhost Temporal server is permitted exclusively for Phase 2.5 development
verification. Production deployments MUST continue using Managed Temporal. No
production code may depend on localhost-specific behavior.

This exception expired when the Phase 2.5 proof ended. It does not authorize
self-hosted Temporal for production. Temporal adoption is recorded separately
above and is based on the completed proof, not on localhost-specific behavior.

## Decision

- Use one strictly modular codebase.
- Deploy the API and durable workers as separate scalable processes.
- Use managed PostgreSQL as the primary durable database.
- Use provider-neutral S3-compatible object storage; provider, region and
  lifecycle settings remain a later operating decision.
- Defer Redis until distributed rate limiting, presence or measured cache pressure
  requires it. Redis can never be authoritative state.
- Run a limited `pgvector` retrieval proof. Production use requires measured
  accuracy improvement, acceptable latency/cost, tenant isolation and deletion.
- Run a Clerk proof/security/commercial comparison with Auth.js. Use internal
  user IDs; custom authentication is excluded from MVP.
- Use Managed Temporal as the durable workflow engine behind the approved
  provider-neutral orchestration port. The Phase 2.5 proof covered durable
  approval waits, recovery, retry, cancellation, idempotent effects, versioning,
  uncertain outcomes, and independent workers. Do not self-host Temporal in
  production.

## Consequences

Proof authorization is not production adoption. Domain and public contracts
remain engine-, identity-, storage-provider- and model-neutral. Active workflow
history is acknowledged as expensive to migrate.

## Rejected

Premature microservices, service-per-module, custom authentication, Redis as
durable state, self-hosted Temporal for MVP and a dedicated vector database
without measurements.
