# Policy, Approval, and Security

## Policy authority

Policy Engine owns authorization, permissions, risk, budgets, quotas, approval
requirements, and restrictions. Policy decisions are typed, attributable,
time-bounded, workspace-scoped, and auditable. Deny wins over allow unless an
explicitly authorized exception policy says otherwise.

## Evaluation points

- At command acceptance.
- After plan validation and before execution.
- Before a capability accesses sensitive data or Tool Interface.
- Immediately before consequential commitment when permissions, content, cost,
  target, credentials, or context may have changed.

Earlier plan acceptance never substitutes for current action approval.

## Approval

Approval requests contain the exact proposed effect, target, content/hash,
estimated cost, risk, policy reason, evidence, expiry, and workflow/step version.
Only authorized principals may decide. Decisions are append-only, concurrency
controlled, and bound to the reviewed content. Any material change invalidates
the approval.

Publishing, sending, deleting, purchasing, deployment, financial actions, and
other high-risk/irreversible effects always pass applicable policy.

## Accepted default matrix

- **Low:** authorized reads/search, drafts, plans, validation, and unpublished
  creative artifacts; no human approval by default.
- **Medium:** projects/tasks, ordinary task state, reversible internal edits, and
  explicitly scoped reusable permissions; the adopted role/scoped permission
  rule applies.
- **High:** email, social publish/schedule, live-site changes, file deletion,
  provider connection, ordinary export, and client/public external effects;
  exact one-time approval by an authorized project/operations manager,
  workspace admin, or owner.
- **Critical:** production deployment, bulk/permanent destruction, role changes,
  sensitive export, material spend, security configuration, and legal agreement;
  only owner/security admin/designated senior administrator, with dual approval
  for the designated categories when supported.

Approval expiry follows the accepted defaults in ADR-003. The exact snapshot is
hashed; changes to recipient, target, content, amount, provider, environment,
artifact, or operation invalidate it. Policy re-evaluates at commit.

MVP prohibits AI contract acceptance, self-permission changes, unrestricted
reusable approval, secret disclosure, repository bypass, blind retry after an
unknown outcome, third-party executable Department plugins, autonomous uncapped
spend, and permanent bulk destruction without recovery safeguards and explicit
Critical approval.

## Security boundaries

- Authenticate the principal and resolve local membership on every request.
- Authorize workspace, resource, action, and current context.
- Apply least privilege to processes, plugins, databases, tools, and credentials.
- Keep secrets in an approved secret store and pass only opaque references.
- Treat prompts, uploads, provider output, websites, and webhook payloads as
  untrusted.
- Verify webhook signatures, time windows, and replay/idempotency identifiers.
- Malware/content scan files before model or plugin access.
- Redact secrets and sensitive payloads from prompts, logs, traces, and audit
  diffs.
- Time-bound, reason, approve, and audit support access.

## AI/code safety

AI cannot directly access a database, unrestricted network, shell, filesystem,
credential, or arbitrary code executor. AI-generated SQL is never executed
directly. AI-generated code requires a separately approved sandbox, policy,
resource limits, network/secret isolation, artifact review, and audit trail.

## Failure behavior

Missing tenant, uncertain authorization, stale approval, unavailable compliant
provider, unknown effect outcome, or failed audit recording fails closed.
Emergency break-glass behavior requires a dedicated owner-approved policy and
immutable audit; it cannot be invented during an incident.
