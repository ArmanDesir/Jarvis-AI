# Executive and Planning Rules

## Command classification

Every input is first classified as deterministic command, reasoning request,
unsupported request, or ambiguous request. Classification is typed and audited.

Simple deterministic commands may bypass Executive reasoning and Planner:

- open a dashboard;
- list tasks;
- retrieve a known project;
- change a supported setting;
- cancel an eligible workflow;
- approve a pending request.

They still require authentication, workspace resolution, authorization, policy,
validation, audit, and correlation.

## Executive AI

The Executive owns the human conversation. It may clarify intent, explain a
proposed plan, summarize progress, and present evidence-backed results. It does
not decompose work, choose arbitrary tools, modify workflow state, approve
permissions, or persist data.

Prompts may contain communication style, task context, retrieved evidence, and
typed available choices. They must not contain authoritative authorization,
pricing, retention, workflow, or domain rules; SQL; ORM models; table names;
internal endpoints; secrets; or infrastructure details.

## Context Resolver

The resolver requests permission-filtered retrieval, ranks candidate references,
and returns typed references with evidence and confidence. Below an approved
confidence threshold or with close competing candidates, the Executive asks one
clarifying question. A model cannot invent a missing identifier.

## Planner

The Planner receives an approved goal, resolved references, constraints, and
enabled capability metadata. It emits a typed plan proposal containing steps,
capability IDs and versions, inputs, outputs, dependencies, expected artifacts,
and uncertainty.

The Planner cannot name unavailable capabilities, call code, persist plans, grant
permission, or define new business rules. Deterministic application code validates
the proposal before persistence or policy evaluation.

## Plan validation

Validation checks schema, acyclic dependencies, required inputs, compatible
versions, capability availability, tenant references, bounded size, and declared
risk/tool/AI requirements. Invalid plans are rejected or returned for bounded
revision; they are never “best-effort” executed.
