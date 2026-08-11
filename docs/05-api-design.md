# API Design

**Status:** Architecture-reconciled draft; implementation not authorized  
**Style:** REST commands/resources, WebSockets for streams, signed webhooks

## 1. Principles

- The API is workspace-scoped, versioned under `/v1`, and described by OpenAPI.
- Clients call Executive and operating-system resources, never department agents.
- Mutations accept `Idempotency-Key`; asynchronous work returns `202 Accepted`.
- All IDs are opaque UUIDs. Times are ISO 8601 UTC.
- List endpoints use cursor pagination.
- Generated TypeScript clients consume the published OpenAPI contract.

## 2. Authentication and tenancy

`Authorization: Bearer <identity-provider token>` is verified through an
identity adapter. Workspace is explicit
in `/v1/workspaces/{workspace_id}/...`; membership and policy are checked for
every request. The server never trusts a workspace claim without local membership
validation.

## 3. Error format

```json
{
  "type": "https://rightjob.ai/problems/approval-required",
  "title": "Approval required",
  "status": 409,
  "code": "APPROVAL_REQUIRED",
  "detail": "Publishing content requires approval.",
  "instance": "/v1/workspaces/.../runs/...",
  "correlation_id": "uuid",
  "errors": []
}
```

Use RFC 9457 problem details. Validation errors include safe field pointers.

## 4. Executive and conversations

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/workspaces/{w}/conversations` | Start conversation |
| `GET` | `/v1/workspaces/{w}/conversations` | List conversations |
| `GET` | `/v1/workspaces/{w}/conversations/{id}` | Conversation metadata |
| `GET` | `/v1/workspaces/{w}/conversations/{id}/messages` | Message history |
| `POST` | `/v1/workspaces/{w}/conversations/{id}/messages` | Send user command |
| `POST` | `/v1/workspaces/{w}/briefs/daily` | Generate or retrieve daily brief |
| `POST` | `/v1/workspaces/{w}/context/resolve` | Preview reference resolution |

Message command:

```json
{
  "client_message_id": "uuid",
  "content": [{"type": "text", "text": "Continue yesterday's project"}],
  "response_mode": "stream",
  "timezone": "Asia/Manila"
}
```

Response:

```json
{
  "message_id": "uuid",
  "status": "accepted",
  "run_id": "uuid",
  "stream_cursor": "opaque"
}
```

## 5. Plans and runs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/workspaces/{w}/plans/{id}` | Inspect typed plan |
| `POST` | `/v1/workspaces/{w}/plans/{id}/accept` | Accept a plan; does not authorize an external effect |
| `POST` | `/v1/workspaces/{w}/plans/{id}/reject` | Reject with reason |
| `GET` | `/v1/workspaces/{w}/runs` | Filter run history |
| `GET` | `/v1/workspaces/{w}/runs/{id}` | Status and summary |
| `GET` | `/v1/workspaces/{w}/runs/{id}/timeline` | Steps, evidence, approvals |
| `POST` | `/v1/workspaces/{w}/runs/{id}/cancel` | Request cancellation |
| `POST` | `/v1/workspaces/{w}/runs/{id}/retry` | Retry eligible failure |

Run status is one of `queued`, `planning`, `awaiting_approval`, `running`,
`completed`, `failed`, `cancelling`, or `cancelled`.

## 6. Approval inbox

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/workspaces/{w}/approvals` | List pending/history |
| `GET` | `/v1/workspaces/{w}/approvals/{id}` | Risk, preview, evidence |
| `POST` | `/v1/workspaces/{w}/approvals/{id}/decisions` | Approve/reject the exact hashed effect snapshot |

```json
{
  "decision": "approve",
  "reason": "Copy and audience verified",
  "expected_version": 3,
  "effect_snapshot_hash": "sha256:..."
}
```

Concurrent or expired decisions return `409`.

## 7. Agency resources

Standard create/list/get/update endpoints exist for:

- `/clients`, `/contacts`, `/projects`, `/tasks`, `/meetings`, `/leads`
- `/decisions`, `/files`, `/sops`, `/brand-profiles`

Updates use `If-Match` with the resource version. Deletion behavior is explicit
per resource; there is no generic irreversible bulk-delete endpoint.

Work-owned client engagement requirements and project delivery preferences are
read and corrected through Work resource commands. Workspace-member
communication preferences are read and corrected through Identity/Tenancy
member-settings commands. Memory correction endpoints cannot mutate either
canonical record; they route an authorized correction to the owner and refresh
the derived representation after the owner's versioned event.

## 8. Departments, workflows, and policies

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/workspaces/{w}/departments` | Enabled and available departments |
| `GET` | `/v1/workspaces/{w}/departments/{key}` | Manifest/Capability summary |
| `PUT` | `/v1/workspaces/{w}/departments/{key}/activation` | Enable or pin version |
| `GET` | `/v1/workspaces/{w}/workflow-definitions` | List definitions |
| `GET/POST` | `/v1/workspaces/{w}/policies` | Read/create policy |
| `PATCH` | `/v1/workspaces/{w}/policies/{id}` | Update policy |

Workflow definitions are reviewed built-ins and read-only to workspace users.
No public endpoint authors definitions or uploads executable plugin code in MVP.
Packages are deployed
through the trusted release pipeline; workspaces only activate approved versions.

## 9. Memory and knowledge

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/workspaces/{w}/memory` | Search eligible memories |
| `POST` | `/v1/workspaces/{w}/memory` | Add explicit memory |
| `POST` | `/v1/workspaces/{w}/memory/{id}/corrections` | Supersede inaccurate memory |
| `DELETE` | `/v1/workspaces/{w}/memory/{id}` | Request eligible deletion |
| `POST` | `/v1/workspaces/{w}/knowledge-documents` | Initiate upload |
| `GET` | `/v1/workspaces/{w}/knowledge-documents/{id}` | Ingestion state |

Search responses include source references, confidence, and effective dates.

## 10. Files and voice

File upload uses a create-upload/finalize flow with short-lived signed URLs and
scan status. Voice session endpoints issue short-lived tokens for configured STT
and TTS transports; finalized transcripts are submitted through the message API.

Raw provider credentials are never returned.

## 11. Realtime protocol

Connect to:

```text
GET /v1/workspaces/{w}/realtime?cursor=<opaque>
Upgrade: websocket
```

Server events:

- `conversation.message.delta`
- `conversation.message.completed`
- `run.status.changed`
- `run.step.changed`
- `approval.requested`
- `artifact.created`
- `notification.created`
- `error`

Every event includes `event_id`, `sequence`, `occurred_at`, `correlation_id`, and
payload. Clients acknowledge the latest sequence; reconnect replays retained
events or directs the client to refresh projections.

## 12. Webhooks

Inbound integrations use `/v1/webhooks/{provider}` with signature verification
and replay protection. Outbound workspace webhooks are post-MVP; internal domain
events are not exposed as an accidental public contract.

## 13. Versioning and compatibility

- Additive response fields are non-breaking.
- Removing/renaming fields or changing semantics requires a new API version.
- Events and Capability schemas carry independent versions.
- Deprecations publish a sunset date and telemetry verifies remaining consumers.
- OpenAPI diff and plugin contract tests run in CI.
