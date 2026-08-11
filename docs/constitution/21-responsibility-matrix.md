# Responsibility Matrix

**Legend:** A = accountable owner, R = performs, C = consulted/constraint source,
I = receives outcome, — = no authority.

| Responsibility | Executive | Context / Memory | Planner | Policy | Registry | Orchestrator / Compiler | Department / Capability | Tool / Adapter | Validator / Reviewer | Repository / DB | Audit / Obs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| User conversation | A/R | C | C | — | — | I | — | — | — | — | I |
| Reference resolution | I | A/R | C | C | — | — | — | — | C | R | I |
| Task decomposition | I | C | A/R | C | C | — | — | — | C | — | I |
| Capability catalog | — | — | C | C | A/R | C | I | — | — | R | I |
| Authorization/risk | I | C | — | A/R | C | C | C | — | — | R | I |
| Workflow compilation | — | — | C | C | C | A/R | C | — | C | R | I |
| Workflow lifecycle | I | I | — | C | C | A/R | R for step | R for call | C | R | I |
| Domain business operation | — | C | — | C | I | C | A/R | R for integration | C | R | I |
| External integration contract | — | — | — | C | — | C | C | A Tool | — | — | I |
| Vendor implementation | — | — | — | C | — | C | C | A/R Adapter | C | — | I |
| AI provider selection | — | — | C | C | — | I | R requester | A/R AI Router | — | — | I |
| Deterministic validation | — | — | C | C | C | C | C | C | A/R Validator | — | I |
| Qualitative assessment | I | C | — | — | — | C | C | C | A/R Reviewer | — | I |
| Human approval state | I | — | — | A Policy | — | R pause/resume | I | — | — | R | I |
| Canonical persistence | — | — | — | — | — | — | — | — | — | A/R owning Repository; DB provides | I |
| Audit/telemetry | I | I | I | I | I | R emits | R emits | R emits | R emits | R stores own evidence | A |
| Final presentation | A/R | C | — | I | — | I | I | — | C | — | I |

## Matrix rules

- A row has one accountable logical owner.
- “R” does not grant authority outside the owner’s published contract.
- Repository/Database participation never transfers business ownership.
- Audit observes and stores evidence; it does not become the workflow owner.
- AI Router is part of the provider/tool platform boundary, not Department or
  Planning.
