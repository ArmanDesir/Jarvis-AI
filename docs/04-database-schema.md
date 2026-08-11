# Database Schema

**Status:** Architecture-reconciled logical schema; implementation authorized by phase gate  
**Database:** PostgreSQL; `pgvector` remains proof-gated

## 1. Conventions

- Primary keys are UUIDv7.
- Mutable tables have `created_at`, `updated_at`, and optimistic `version`.
- Every tenant-owned production table, including children and joins, has
  non-null `workspace_id`, tenant-aware foreign keys, and enabled/forced RLS.
- Timestamps are UTC `timestamptz`.
- User-facing deletion is soft where audit/legal retention requires it; eligible
  personal content is hard-deleted by retention workflows.
- Flexible metadata may use `jsonb`; primary relationships and queryable state do
  not.
- Database enums are avoided for frequently evolving workflow states; constrained
  text values are migrated safely.

## 2. Identity and tenancy

| Table | Important columns |
|---|---|
| `workspaces` | `id`, `name`, `slug`, `status`, `timezone`, `locale`, `settings`, `created_at`, `updated_at`, `version` |
| `users` | `id`, `external_identity_provider`, `external_subject`, `email`, `display_name`, `status`, `created_at`, `updated_at`, `version` |
| `memberships` | `id`, `workspace_id`, `user_id`, `role`, `status`, `created_at`, `updated_at`, `version` |
| `roles` | `id`, `workspace_id?`, `name`, `permissions_json` |
| `service_principals` | `id`, `workspace_id`, `name`, `status` |
| `member_communication_preferences` | `id`, `workspace_id`, `user_id`, `notification_channels_json`, `language`, `timezone`, `contact_preferences_json`, `version` |

Unique constraints cover workspace slug, external identity, and membership pair.
Identity/Tenancy owns member communication preferences. Memory may store only
source-linked retrieval representations.

Workspace is both the tenant boundary and agency account for MVP and therefore has
no `workspace_id`. User is a platform identity that may join multiple Workspaces and
also has no `workspace_id`. Membership is tenant-owned and uses direct forced RLS.
Tenant and Organization are not separate MVP models (ADR-009).

## 3. Agency work graph

| Table | Important columns |
|---|---|
| `clients` | `id`, `workspace_id`, `name`, `status`, `owner_user_id`, `metadata_json` |
| `contacts` | `id`, `workspace_id`, `client_id?`, `name`, `email`, `phone` |
| `projects` | `id`, `workspace_id`, `client_id?`, `name`, `status`, `start_at`, `due_at` |
| `tasks` | `id`, `workspace_id`, `project_id?`, `parent_id?`, `title`, `status`, `priority`, `assignee_id?`, `due_at` |
| `meetings` | `id`, `workspace_id`, `project_id?`, `external_ref?`, `starts_at`, `ends_at`, `summary` |
| `decisions` | `id`, `workspace_id`, `project_id?`, `title`, `decision`, `rationale`, `decided_at`, `supersedes_id?` |
| `leads` | `id`, `workspace_id`, `client_id?`, `stage`, `source`, `owner_user_id?`, `next_action_at?` |
| `client_engagement_requirements` | `id`, `workspace_id`, `client_id`, `project_id?`, `kind`, `value_json`, `source_ref`, `effective_at`, `version` |
| `project_delivery_preferences` | `id`, `workspace_id`, `project_id`, `kind`, `value_json`, `effective_at`, `version` |

Clients, projects, tasks, contacts, and leads expose normalized custom fields
later through definitions/values tables if real customer requirements justify
them; arbitrary JSON is sufficient for MVP non-critical metadata.

Work owns the two preference/requirement tables above. Operations and Departments
consume them through Work contracts and cannot write them directly.

## 4. Conversations

| Table | Important columns |
|---|---|
| `conversations` | `id`, `workspace_id`, `title`, `channel`, `created_by`, `active_project_id?` |
| `messages` | `id`, `workspace_id`, `conversation_id`, `role`, `content`, `status`, `provider_message_id?`, `sequence` |
| `message_parts` | `id`, `workspace_id`, `message_id`, `kind`, `content_json`, `file_id?` |
| `conversation_summaries` | `id`, `workspace_id`, `conversation_id`, `from_sequence`, `to_sequence`, `summary`, `source_hash` |
| `context_resolutions` | `id`, `workspace_id`, `conversation_id`, `message_id`, `reference_type`, `reference_id`, `confidence`, `evidence_json` |

Messages are append-only apart from moderation/redaction state. Sequence is
unique within a conversation.

## 5. Plans and durable execution

| Table | Important columns |
|---|---|
| `plans` | `id`, `workspace_id`, `conversation_id?`, `goal`, `status`, `schema_version`, `created_by`, `approved_at?` |
| `plan_steps` | `id`, `workspace_id`, `plan_id`, `step_key`, `capability_id`, `capability_version`, `input_json`, `risk`, `status` |
| `plan_step_dependencies` | `workspace_id`, `plan_id`, `step_id`, `depends_on_step_id` |
| `workflow_runs` | `id`, `workspace_id`, `plan_id`, `engine_execution_ref?`, `status`, `started_at?`, `completed_at?` |
| `step_runs` | `id`, `workspace_id`, `workflow_run_id`, `plan_step_id`, `attempt`, `status`, `idempotency_key`, `output_json?`, `error_json?` |
| `artifacts` | `id`, `workspace_id`, `workflow_run_id?`, `step_run_id?`, `kind`, `uri`, `content_hash`, `metadata_json` |
| `schedules` | `id`, `workspace_id`, `workflow_definition_id`, `cron`, `timezone`, `status`, `next_run_at?` |

`idempotency_key` is unique per external operation scope. Inputs/outputs are
retained as schema-versioned execution evidence but secrets are redacted.

## 6. Departments and workflows

| Table | Important columns |
|---|---|
| `department_packages` | `id`, `department_key`, `version`, `manifest_json`, `checksum`, `status` |
| `workspace_departments` | `workspace_id`, `department_package_id`, `enabled`, `config_json` |
| `capability_definitions` | `id`, `department_package_id`, `capability_key`, `input_schema`, `output_schema`, `risk`, `permissions_json` |
| `workflow_definitions` | `id`, `workspace_id?`, `key`, `version`, `definition_json`, `status` |
| `workflow_definition_versions` | `id`, `workflow_definition_id`, `version`, `definition_json`, `checksum`, `published_at` |

Published manifests and workflow versions are immutable.

## 7. Policy and approval

| Table | Important columns |
|---|---|
| `policies` | `id`, `workspace_id`, `name`, `priority`, `condition_json`, `effect`, `status` |
| `approval_requests` | `id`, `workspace_id`, `workflow_run_id`, `step_run_id?`, `status`, `risk`, `summary`, `expires_at?` |
| `approval_decisions` | `id`, `workspace_id`, `approval_request_id`, `decided_by`, `decision`, `effect_snapshot_hash`, `reason`, `created_at` |
| `budget_reservations` | `id`, `workspace_id`, `workflow_run_id`, `amount`, `unit`, `status`, `expires_at` |

Approval decisions are append-only. A request’s current status is a projection of
its decisions and expiry.

## 8. Memory and knowledge

| Table | Important columns |
|---|---|
| `memory_items` | `id`, `workspace_id`, `kind`, `subject_type?`, `subject_id?`, `content`, `summary?`, `sensitivity`, `confidence`, `valid_from`, `valid_to?`, `supersedes_id?` |
| `memory_sources` | `workspace_id`, `memory_item_id`, `source_type`, `source_id`, `source_locator_json` |
| `memory_embeddings` | `workspace_id`, `memory_item_id`, `adapter_metadata_json`, `dimensions`, `embedding?`, `content_hash` |
| `knowledge_documents` | `id`, `workspace_id`, `kind`, `title`, `file_id?`, `status`, `version` |
| `knowledge_chunks` | `id`, `workspace_id`, `document_id`, `ordinal`, `content`, `embedding?`, `token_count` |
| `brand_profiles` | `id`, `workspace_id`, `client_id?`, `name`, `guidelines_json`, `version` |
| `sops` | `id`, `workspace_id`, `title`, `status`, `content`, `version` |

Embedding implementation metadata stays adapter-owned. Vector columns and
indexes are added only if the `pgvector` proof passes its adoption gates.

## 9. Files and integrations

| Table | Important columns |
|---|---|
| `files` | `id`, `workspace_id`, `storage_key`, `name`, `media_type`, `size`, `sha256`, `scan_status` |
| `integration_connections` | `id`, `workspace_id`, `provider`, `external_account_id`, `secret_ref`, `scopes_json`, `status` |
| `webhook_receipts` | `id`, `workspace_id`, `provider`, `external_event_id`, `received_at`, `payload_hash`, `status` |
| `external_operations` | `id`, `workspace_id`, `step_run_id`, `provider`, `operation`, `idempotency_key`, `external_id?`, `status` |

Files are unavailable to models and plugins until malware/content checks pass.

## 10. Audit, events, and usage

| Table | Important columns |
|---|---|
| `audit_entries` | `id`, `workspace_id`, `actor_type`, `actor_id`, `action`, `resource_type`, `resource_id`, `before_json?`, `after_json?`, `correlation_id`, `created_at` |
| `outbox_events` | `id`, `workspace_id`, `event_type`, `payload_json`, `correlation_id`, `published_at?`, `attempts` |
| `usage_records` | `id`, `workspace_id`, `workflow_run_id?`, `provider`, `model?`, `input_units`, `output_units`, `cost_micros`, `occurred_at` |
| `notifications` | `id`, `workspace_id`, `recipient_user_id`, `kind`, `payload_json`, `read_at?` |

Audit entries are append-only and partitioned by time at scale. Outbox consumers
deduplicate on event ID.

## 11. Key relationships

```text
workspace
├── clients ── projects ── tasks
├── conversations ── messages
├── departments ── capabilities
├── plans ── plan_steps ── step_dependencies
│              └── workflow_runs ── step_runs ── artifacts
├── approval_requests ── approval_decisions
├── memory_items ── memory_sources / embeddings
└── integration_connections / audit_entries / usage_records
```

## 12. Isolation and indexes

- RLS uses the transaction-local authenticated workspace ID.
- RLS is enabled and forced; parent-join-only isolation is prohibited for
  production tenant data.
- Composite tenant-aware foreign keys prevent cross-workspace references.
- Composite indexes begin with `workspace_id` for tenant queries.
- Primary operational indexes cover task due/status, project status, run status,
  pending approvals, unpublished outbox rows, and memory subject/validity.
- Full-text GIN indexes cover memory, SOP, document chunks, and message search.
- Every repository integration test verifies the RLS “no context means no rows”
  failure mode.
