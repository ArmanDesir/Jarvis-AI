# Memory and Context Standard

Memory responsibilities are logical boundaries and need not be separate services.

## Working Memory

Holds bounded current-conversation and active-work context. It may reference
durable workflow state but cannot be the authoritative workflow store. Loss of a
cache or socket must not lose acknowledged work.

## Episodic Memory

Represents historical conversations, meetings, completed work, and decisions with
source references, effective dates, sensitivity, and retention. Canonical Work
records remain owned by Work.

## Semantic Knowledge

Represents source-backed facts about clients, projects, brands, SOPs, preferences,
and agency knowledge. It does not duplicate or override canonical records.
Corrections supersede derived facts and trigger re-indexing where required.

## Retrieval Service

Retrieval must:

1. establish workspace and principal;
2. enforce permission and sensitivity filters before ranking;
3. filter validity, retention, subject, and document state;
4. use keyword/vector/hybrid ranking as configured;
5. return provenance, confidence, and effective dates;
6. suppress or flag ambiguous and stale results.

Cross-workspace search is forbidden, including caches, embedding indexes, logs,
evaluation datasets, and support tooling.

## Context Resolver

The resolver uses Retrieval Service outputs and deterministic context signals to
rank references. It returns typed IDs, evidence, confidence, and ambiguity—not a
business plan. Low confidence requires clarification or safe failure.

## AI and persistence

AI may propose summaries, facts, or links. Deterministic code validates scope,
schema, provenance, sensitivity, retention, and permissions before the owning
Memory repository persists anything. Prompts never receive database schema.

## Storage choice

PostgreSQL full-text and entity retrieval is the default baseline. `pgvector` is
authorized only for a limited proof and requires measured accuracy improvement,
acceptable latency, verified tenant isolation/deletion, and acceptable cost
before adoption. A separate vector database requires measured corpus/latency
evidence, tenancy/deletion analysis, operating cost, migration/dual-write plan,
and owner-approved ADR.

## Preference ownership

- Work owns client identity/contact details, contractual and engagement
  requirements, and project delivery preferences.
- Identity/Tenancy owns workspace-member communication preferences, including
  notification channels, language, timezone, and contact preferences.
- Marketing owns brand voice/messaging and visual identity/asset rules.
- Website owns website structure and functional preferences.
- Working Memory owns expiring active-task instructions.
- The domain making a historical decision owns the canonical decision; Episodic
  Memory keeps immutable provenance.
- Derived AI inference is non-canonical and carries sources, timestamp,
  confidence, and model metadata.

Departments consume these records only through owner-controlled queries,
projections, or contracts. Corrections update the canonical owner first.
Memory representations retain workspace scope, provenance, source record
ID/version, and last-updated metadata, then refresh or supersede after the
canonical update.
