# ADR-008: Canonical Preference Ownership

**Status:** Accepted  
**Decision date:** 2026-07-28  
**Final ownership approval:** 2026-07-29

## Accepted rules

- Marketing canonically owns brand voice/messaging and visual identity/asset
  rules.
- Website canonically owns website structure and functional preferences.
- Working Memory owns only expiring active-task instructions.
- The domain that made a historical decision owns its canonical decision;
  Episodic Memory stores source-linked history.
- Derived AI inference has no canonical business owner. Memory stores it only as
  a derived, source-linked, timestamped, confidence-bearing, explicitly
  non-canonical record.
- Corrections update the canonical owner first; Memory then refreshes or
  supersedes derived representations and never overwrites another owner.

## Final canonical ownership

- **Client identity and contact details:** Work.
- **Contractual and engagement requirements:** Work.
- **Project delivery preferences:** Work.
- **Workspace-member communication preferences:** Identity/Tenancy.

Work exposes owner-controlled commands and queries for its records.
Identity/Tenancy exposes owner-controlled commands and queries for member
communication preferences. Operations and Departments may consume these through
published queries, projections, or contracts but may not mutate them directly.

## Memory representation and correction

Memory may index, summarize, or derive records only with workspace scope,
provenance, canonical source ID/version, and last-updated metadata. Corrections
write to Work, Identity/Tenancy, Marketing, Website, or the other applicable
canonical owner first. The owner emits a versioned event; Memory refreshes or
supersedes its representation. Memory never becomes the source of truth for
another module's records.

## Consequences

This resolves the P1 ownership blocker found in validation Scenarios 18 and 20.
It does not by itself authorize implementation.
