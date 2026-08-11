# External-Action Approval Lifecycle

```text
Capability prepares proposed external effect
                 |
                 v
       Deterministic validation
                 |
                 v
  Policy evaluates actor · tenant · action
  target · content · cost · risk · current context
                 |
        +--------+---------+
        |                  |
      DENY             ALLOW WITHOUT
        |              HUMAN APPROVAL
        v                  |
  Orchestrator fails       |
  safely + audits          |
                           |
                     REQUIRE APPROVAL
                           |
                           v
                 Freeze effect snapshot/hash
                 + evidence + expiry + policy
                           |
                           v
                   Authorized human decision
                    /        |          \
                 reject    expire     approve
                    |        |          |
                    +---- no commit ----+
                                      |
                                      v
                       Revalidate unchanged snapshot
                       and re-run commit-time policy
                                      |
                              +-------+-------+
                              |               |
                           invalid          valid
                              |               |
                       request new approval   v
                                      Reserve idempotency key
                                      + durable audit intent
                                              |
                                              v
                                      Provider Adapter call
                                              |
                           +------------------+------------------+
                           |                  |                  |
                        success          known failure     unknown outcome
                           |                  |                  |
                    record external ID   normalized fail    reconcile; do not
                    + evidence           / safe retry       blindly retry
                           \                  |                  /
                            +-----------------+-----------------+
                                              |
                                              v
                               Orchestrator commit / retry /
                                  compensate / fail + audit
```

## Mandatory rules

- Approval is bound to the exact effect; changed content, target, cost, risk,
  credentials, or expiry invalidates it.
- Plan acceptance is not action approval.
- Reviewer recommendations cannot approve.
- Idempotency is scoped to the external operation and survives retries/restarts.
- If durable audit intent cannot be recorded, consequential commitment stops.
- Compensation is not assumed. Where the provider cannot undo an effect, the
  contract must state irreversibility and require the appropriate approval.
