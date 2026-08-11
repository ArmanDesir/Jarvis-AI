# ADR-002: Departments, Creative Ownership, and Plugin Trust

**Status:** Accepted  
**Decision date:** 2026-07-28

## Decision

Initial Departments are Website, Marketing and Operations.

Marketing solely owns brand strategy, brand voice/messaging, visual direction,
graphic-design briefs, social graphics, website visual assets, campaign creative
direction, video concepts and image-generation prompts.

Website solely owns website information architecture, UI composition and
implementation. It consumes Marketing artifacts through versioned Orchestrator
handoffs and cannot duplicate Creative Capabilities.

Operations owns operational delivery business rules and Capabilities. This does
not transfer workflow lifecycle, scheduling, retries or workflow state from
Orchestrator.

MVP permits trusted first-party Department plugins released through the controlled
build pipeline. Third-party executable plugins are prohibited. Configuration-only
integrations and Provider Adapters remain subject to Tool, Policy, credential and
audit boundaries and are not automatically Department plugins.

## Consequences

Every Capability has one owner. Departments never call each other. A future
third-party plugin system requires a separately approved security architecture
covering signing, provenance, sandboxing, permissions, tenant credentials,
network/resource limits, dependency scanning, audit, revocation, compatibility,
emergency disabling and marketplace governance.
