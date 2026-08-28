# Phase 2.19 Stage A — Durable Result Quality Gate Design Report

**Date:** 2026-08-27
**Scope:** Published contracts, pure decisions, and durable PostgreSQL governance evidence
**Status:** `DURABLE QUALITY-GATE PERSISTENCE IMPLEMENTED — CHECKPOINT REVIEW READY`

## Stage B durable persistence

Owner-approved Stage B adds migration `20260827_0005_result_quality_gate`, Orchestration-owned
SQLAlchemy mappings/repositories, optimistic state updates, durable command idempotency, and one
application transaction spanning state, append-only decision evidence, Audit, and Outbox. Exact
command replay returns the recorded decision without another reservation or side effect; conflicting
reuse fails closed. Application-role grants expose no decision update/delete operation.

Revision reservations are consumed when `REVISION_REQUIRED` commits. The first consumes count 1,
the second count 2, and no later command can consume a third. Revision execution, human-review
workflow, API, Temporal, and worker integration remain deliberately unimplemented.

## Implemented source-only decision boundary

```text
passed ResultValidationEvidence
  + optional input ReviewAssessment (required by a configured quality gate)
  + exact enabled Capability Registry re-resolution
  + Capability-owned versioned quality policy
  + optional prior durable QualityGateState
  -> pure deterministic QualityGateDecision
  -> accepted | revision_required | needs_human_review
  -> STOP
```

No repository, Unit of Work, SQLAlchemy mapping, migration, database operation, Audit/Outbox write,
Capability invocation, revision scheduling, provider call, Temporal operation, worker, or API path
is implemented in Stage A.

## Trusted policy ownership

`CapabilityQualityGatePolicy` is part of the exact enabled `CapabilityDefinition`. It binds the
Capability ID/key/version, policy key/version, review criteria key/version, exact score key,
integer threshold, maximum automated revisions (`0..2`), and the closed
`STRICTLY_GREATER` improvement rule. The decision service re-resolves the exact Capability through
the published `CapabilityCatalog`; Planner, Reviewer, provider, user, result payload, and command
fields cannot supply or override policy.

The synthetic `fake.verify@1.0.0` definition owns `fake.verify.quality@1.0.0`, requires score
`fake.verify.quality >= 80`, permits at most two automated revisions, and requires strict score
improvement between comparable below-threshold attempts.

## Decision table

| Condition | Outcome | Revision count |
|---|---|---|
| Required score is at least threshold | `ACCEPTED` | unchanged |
| Below threshold, no prior score, budget remains | `REVISION_REQUIRED` | increment by one |
| Below threshold, strictly greater comparable score, budget remains | `REVISION_REQUIRED` | increment by one |
| Below threshold, revision count equals policy maximum | `NEEDS_HUMAN_REVIEW` | unchanged |
| Below threshold, comparable score is equal or lower | `NEEDS_HUMAN_REVIEW` | unchanged |
| Below threshold and Reviewer recommends human review | `NEEDS_HUMAN_REVIEW` | unchanged |
| Missing/mismatched/malformed evidence or state | integrity exception | no decision/state mutation |

Reviewer `ACCEPT` cannot make a below-threshold result acceptable. Reviewer
`NEEDS_HUMAN_REVIEW` is treated only as a conservative early-escalation signal for a result that is
already below the trusted threshold. It cannot override a threshold-met acceptance and grants no
approval, authorization, execution, or workflow-resume authority. Other recommendations do not
control the decision.

A configured quality gate requires a matching assessment because its trusted policy names an exact
score. The method accepts `None` only to fail closed without mutation. Capabilities without a
quality policy are outside this service rather than being implicitly accepted.

## Revision-count and comparison semantics

- Count `0` means no automated revision has ever been durably reserved.
- A `REVISION_REQUIRED` decision reserves the next cycle and increments the count atomically with
  that decision; first reservation produces `1`, second produces `2`.
- Count `2` prohibits a third reservation. Restart cannot reset it.
- Duplicate delivery of an identical command returns the existing decision and does not increment.
  The same command ID with different fields is an integrity conflict.
- A later failed revision execution does not refund the reservation. Provider transport retries are
  separate and cannot reset the content-revision count.
- Stage A does not execute the reservation. A future authorized Orchestration command may move
  `REVISION_REQUIRED` to `AWAITING_REVIEW` only after a new validated artifact exists.
- Comparable attempts require the same gate, Workspace/run/step, Capability, policy key/version,
  criteria key/version, score key, and artifact ID. Artifact version must strictly increase and its
  SHA-256 must change.
- Below threshold, the required integer score must be strictly greater than the prior score. Equal
  or lower escalates. The first assessment has no comparison requirement.
- Threshold satisfaction wins before improvement comparison.
- A policy or criteria version change is not comparable and fails closed; it requires an explicitly
  reviewed new lifecycle design rather than silently resetting the budget.

## Safe evidence projection

`QualityGateDecisionEvidence` contains only closed or trusted typed data: decision/command/gate,
Workspace/run/step/correlation/causation, Capability and policy identities/versions, criteria and score keys, bounded
integer scores/threshold, artifact ID/version/SHA-256, validation/assessment IDs, revision counts,
and timestamp. State adds only closed status, optimistic version, and the same safe identities.

Reviewer reasons, arbitrary Reviewer evidence-reference strings, prompts, user/provider content,
credentials, executable text, raw result payloads, provider models, and SDK/runtime objects never
enter decision evidence or state. The same safe projection is the maximum proposed Audit/Outbox
payload. Unrestricted Reviewer diagnostic persistence is not authorized by Stage A.

## Idempotency and concurrency design

- `command_id` is the globally unique idempotency identity and deterministic decision identity.
- The command binds the exact validated Workspace/run/step/correlation/causation and artifact
  identity/version/SHA-256; any mismatch is an integrity rejection.
- Exact duplicate command: return the already persisted decision.
- Same command ID with differing command fields: reject as conflict.
- New gate creation requires `expected_state_version = NULL`; an existing gate requires exact
  positive `expected_state_version`.
- Every successful decision increments the optimistic state version once, even when revision count
  is unchanged.
- Terminal `ACCEPTED` and `NEEDS_HUMAN_REVIEW`, and unresolved `REVISION_REQUIRED`, reject another
  assessment decision.
- The future repository update must use `WHERE workspace_id = :workspace AND id = :gate AND
  version = :expected`; zero updated rows is a concurrency conflict.
- State update, append-only decision, Audit evidence, and Outbox event must share one transaction.
  Two concurrent second-cycle commands cannot both update the expected version; one rolls back.

## Proposed migration `20260827_0005_result_quality_gate`

Implemented owner: `orchestration`; down revision: `20260812_0004`.

### Existing-table refinement

Add `UNIQUE(workspace_id, id, run_id)` to `execution_steps` so both proposed tables can bind the
exact Workspace/step/run triple instead of relying on application-only run provenance.

### `quality_gate_states`

| Column | SQL type | Purpose |
|---|---|---|
| `id` | UUID PK | Quality-gate identity |
| `workspace_id` | UUID NOT NULL | tenant/RLS scope |
| `run_id`, `step_id` | UUID NOT NULL | exact canonical execution owner |
| `correlation_id`, `causation_id` | UUID NOT NULL / UUID NULL | validated trace provenance |
| `capability_definition_id` | UUID NOT NULL | exact Registry identity snapshot |
| `capability_key` | VARCHAR(255) NOT NULL | bounded Registry key snapshot |
| `capability_version` | VARCHAR(50) NOT NULL | exact Capability version |
| `policy_key`, `policy_version` | VARCHAR(255/50) NOT NULL | trusted policy identity |
| `criteria_key`, `criteria_version` | VARCHAR(255/50) NOT NULL | comparable review criteria |
| `score_key` | VARCHAR(255) NOT NULL | exact score used for decisions |
| `status` | VARCHAR(40) NOT NULL | closed quality-gate lifecycle |
| `automated_revision_count` | SMALLINT NOT NULL | durable reservations, `0..2` |
| `last_artifact_id` | UUID NOT NULL | comparable artifact identity |
| `last_artifact_version` | INTEGER NOT NULL | strictly positive artifact version |
| `last_artifact_sha256` | CHAR(64) NOT NULL | immutable content binding |
| `last_validation_id`, `last_assessment_id`, `last_decision_id` | UUID NOT NULL | exact evidence lineage |
| `last_score` | SMALLINT NOT NULL | comparable required score, `0..100` |
| `version` | INTEGER NOT NULL | optimistic concurrency, positive |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL | application-owned aware timestamps |

Constraints: `UNIQUE(workspace_id,id)`, `UNIQUE(workspace_id,run_id,step_id)`, Workspace FK
`ON DELETE RESTRICT`, exact `(workspace_id,step_id,run_id)` FK to `execution_steps`, closed status,
revision/score/version/artifact-version bounds, lowercase SHA-256, canonical nonblank keys/versions,
and `updated_at >= created_at`. Index: `(workspace_id,status,updated_at)`.

### `quality_gate_decisions` (append-only application contract)

Columns: decision/command UUIDs, Workspace/gate/run/step/correlation/causation, actor type/ID, Capability/policy/criteria/
score identities and versions, score/threshold/prior score, artifact ID/version/SHA-256,
validation/assessment IDs, closed outcome, bounded JSON array of closed reason codes, revision count
before/after, resulting state version, and `decided_at TIMESTAMPTZ`.

Constraints: UUID PK; `decision_id = command_id`; `UNIQUE(workspace_id,id)`,
`UNIQUE(workspace_id,command_id)`, and `UNIQUE(workspace_id,assessment_id)`; Workspace FK, exact
gate FK, exact execution-step triple FK, `ON DELETE RESTRICT`; closed actor/outcome/reason vocabulary;
score/count/version/artifact bounds; count cannot decrease or increase by more than one; lowercase
SHA-256; bounded canonical keys/versions; JSON reasons must be a nonempty array no larger than the
contract bound. Index: `(workspace_id,quality_gate_id,decided_at)`.

The repository contract will expose insert/get only for decisions. No application update/delete is
allowed. State updates require exact optimistic version. PostgreSQL owner privileges remain a
trusted administrative boundary; no trigger or new role is proposed.

## RLS, transaction, and downgrade

Both tables have non-null `workspace_id`, tenant-leading keys/indexes, enabled and forced RLS, and
one table-specific `FOR ALL` policy using the established expression identically in `USING` and
`WITH CHECK`:

```sql
workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid
```

One future Orchestration Unit of Work must atomically perform optimistic state insert/update,
append-only decision insert, safe `AuditEvidence`, safe `IntegrationEvent`, and commit. Any
integrity, concurrency, Audit, or Outbox failure rolls the whole transaction back. No Reviewer
diagnostic strings enter either event.

Downgrade order: drop decision RLS policy/table; drop state RLS policy/table; remove only the new
execution-step composite UNIQUE. It must not alter prior execution data, Policy/Approval tables,
Audit/Outbox tables, roles, grants, extensions, or earlier RLS policies.

## Verification

The focused source and architecture selection passed 58 tests; five isolated PostgreSQL tests
passed. The ordinary offline suite passed 471 tests with 54 database/runtime/live-provider tests
gated and skipped. Ruff format/lint, strict mypy (128 source files), architecture, phase scope,
migration safety, secret hygiene, Python compilation, offline UV lock consistency, and diff
integrity passed. The isolated proof covered upgrade, constraints, forced RLS, tenant denial,
reservations, restart-safe idempotency, conflicting duplicates, optimistic concurrency,
append-only decisions, atomic Audit/Outbox rollback, safe evidence, downgrade, and re-upgrade.
Migration head is `20260827_0005`.

## Approval gate

The owner approved the two-table schema, exact Workspace/step/run binding, reservation-time count
consumption, and exclusion of unrestricted Reviewer diagnostics. Further owner authorization is
required before revision execution or any API/Temporal/worker integration.

`PHASE 2.19 DURABLE QUALITY-GATE PERSISTENCE IMPLEMENTED — CHECKPOINT REVIEW READY`
