# ADR-005: MVP Workflow Authoring

**Status:** Accepted  
**Decision date:** 2026-07-28

## Decision

MVP ships reviewed built-in workflow definitions, AI-generated typed plans for
individual requests, compiled per-request workflow instances, approval,
cancellation and versioned execution.

MVP does not expose arbitrary workspace-authored definitions, user executable
code, a public no-code builder or third-party workflow plugins.

Internal administrator authoring is deferred until workflow contracts, versioning,
Policy, debugging and support procedures are stable.

## Consequences

Natural-language requests remain flexible because Planner proposes valid
Capability graphs and Workflow Compiler creates a run-specific definition.
Public workflow-definition authoring API endpoints are removed from MVP scope.
