# ADR-003: Risk and Approval Policy

**Status:** Accepted with configured thresholds pending contract definition  
**Decision date:** 2026-07-28

## Decision

Use Low, Medium, High and Critical risk levels. Workspace policy may be stricter
but cannot weaken platform minimums.

- Low: authorized reads, Memory search, plans/drafts, non-destructive validation
  and unpublished artifacts.
- Medium: projects/tasks, ordinary internal state changes, reversible internal
  edits and scoped reusable permissions.
- High: email, social publishing/scheduling, live-site updates, file deletion,
  provider connection, ordinary export and client/public external effects.
- Critical: code deployment, permanent/bulk deletion, role/permission changes,
  sensitive export, material spend, security configuration and agreements.

Plan acceptance never authorizes an external effect. Material changes to
recipient, target, content, amount, provider, environment, artifact or operation
invalidate one-time approval. Policy re-evaluates before commitment.

Approvers:

- Low: already authorized member.
- Medium: project/operations manager, workspace admin or applicable grant holder.
- High: project/operations manager, admin or owner approving the exact effect.
- Critical: owner, security admin or designated senior admin. Dual approval is
  required for bulk destruction, privilege elevation, production deployment,
  sensitive bulk export and material spend when dual approval is supported.

Adopt the expiry defaults in the Owner Decision Review.

## MVP prohibitions

AI cannot sign agreements, change its permissions, create unrestricted reusable
approvals, expose secrets, bypass Repositories, blindly retry unknown outcomes,
load third-party executable Departments, spend without caps or permanently
bulk-destroy without recovery safeguards and exact Critical approval.
