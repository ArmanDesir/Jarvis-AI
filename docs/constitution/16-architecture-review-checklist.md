# Architecture Review Checklist

Complete this before any feature or material architecture change.

## Questions

1. Is there duplication?
2. Does another module already own this responsibility?
3. Can this be an existing capability instead of a new component?
4. Does it require a new plugin, or can an existing department own it?
5. Does it violate SOLID or the dependency direction?
6. Is it scalable for at least 1,000 agencies under documented workload?
7. Can every provider be replaced?
8. Is tenant isolation preserved?
9. Is it secure?
10. Can it be tested without a live AI provider?
11. Is it observable and auditable?
12. Are failure, retry, cancellation, reconciliation, and compensation defined?
13. Does it introduce an unnecessary abstraction?
14. Is there a simpler acceptable solution?
15. Does it require owner approval?

## Required review response

```text
Status: approved | revise | blocked
Ownership:
Affected modules:
Duplication findings:
Security findings:
Tenancy findings:
Scale findings:
Required contracts:
Required tests:
Required observability:
Unresolved decisions:
Recommended architecture:
```

## Status rules

- **Approved:** no unresolved blocker; owner decisions and required contracts are
  recorded.
- **Revise:** direction is viable, but boundary, safety, test, scale, or
  observability work is incomplete. Implementation is prohibited.
- **Blocked:** ownership conflict, unsafe design, missing authority, constitutional
  violation, or material unknown prevents responsible progress.

Approval applies only to the reviewed scope and versions. Material changes
invalidate it.
