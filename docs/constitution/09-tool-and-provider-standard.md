# Tool and Provider Standard

## Tool Interface

A Tool Interface is a vendor-neutral contract for an external system or technical
function such as email, calendar, CRM, social publishing, storage, browser
automation, deployment, or analytics. It owns operation semantics and normalized
types, not business policy or workflow coordination.

Tool operations declare authentication needs, permissions, data sensitivity,
idempotency, timeout, retry safety, cancellation, reconciliation, evidence, and
failure categories.

## Provider Adapter

An adapter contains all vendor-specific authentication, SDK imports, request and
response mapping, error normalization, capability metadata, usage, and cost.
Adapters cannot implement business rules, communicate with users, select
departments, or relax policy.

The same adapter pattern covers LLMs, embeddings, STT, TTS, email, calendar, CRM,
social, storage, and other vendors. A provider name cannot appear in domain or
capability contracts except in approved configuration/telemetry values.

## AI Router

A Department Capability requests required AI characteristics. Policy provides
eligibility constraints. AI Router selects among eligible adapters using:

- structured-output and tool support;
- context size and modality;
- privacy and retention requirements;
- workspace provider settings;
- cost limits and latency targets;
- quality thresholds and evaluation evidence;
- availability and geographic restrictions;
- fallback eligibility.

No static “model X for coding/model Y for writing” business rule is allowed.
Routing is capability-based and measurable.

## Fallback

Fallback candidates must satisfy every mandatory capability and policy
constraint. The Router cannot silently use a weaker, non-compliant, differently
retained, or geographically prohibited provider. If none qualifies, return a
typed unavailable result and let Orchestrator wait, retry, or fail.

## Replaceability

Every Tool Interface and AI port has a fake adapter and contract suite. At least
one provider can be replaced in test configuration without changes to domain,
department, workflow, or Executive code. Vendor-only features require an
approved exception with degradation and exit plans.
