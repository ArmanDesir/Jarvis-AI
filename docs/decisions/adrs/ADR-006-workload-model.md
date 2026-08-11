# ADR-006: Initial Workload Model

**Status:** Accepted as planning assumptions, not achieved capacity  
**Decision date:** 2026-07-28

## Decision

Use the 1,000-agency Expected Normal model as the mandatory architecture-review
floor, Conservative MVP for initial cost/deployment planning, Stress for
resilience/noisy-neighbor/quota/recovery tests, and 10,000 workspaces only as a
long-term architecture projection.

The detailed assumptions in the Owner Decision Review govern until replaced by
measured telemetry and load testing.

## Consequences

No document may claim achieved capacity. Infrastructure additions require
measured thresholds and an ADR; this decision does not authorize microservices,
Kafka, a dedicated vector database or other speculative infrastructure.
