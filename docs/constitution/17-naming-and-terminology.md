# Naming and Terminology

Use these terms consistently in contracts, documentation, code, and reviews.

| Term | Definition |
|---|---|
| Executive AI | Sole user-facing AI communication component |
| Context Resolver | Ranks referenced entities using evidence and confidence |
| Planner | Produces an untrusted typed plan proposal |
| Plan Validator | Deterministic validation applied before policy/compilation |
| Policy Engine | Decides authorization, risk, budgets, quotas, and approvals |
| Department Registry | Catalog and workspace activation of Department plugins/capabilities |
| Workflow Compiler | Orchestration-owned compiler from valid plan to deterministic workflow definition |
| Orchestrator | Owner of workflow lifecycle and coordination |
| Department | Cohesive business-domain plugin |
| Capability | One typed business operation published by a Department |
| Tool Interface | Vendor-neutral external/technical port |
| Provider Adapter | Vendor-specific implementation of a Tool or AI port |
| AI Router | Selects an eligible AI adapter from declared requirements |
| Validator | Deterministic correctness checker |
| Reviewer | Qualitative assessor with no authority to approve or mutate |
| Memory | Working, episodic, semantic, and retrieval responsibilities |
| Repository | Owner-scoped persistence interface |
| Workspace | Canonical MVP tenant boundary and agency account |
| Tenant | Security/architecture description of Workspace isolation; not an MVP entity |
| Organization | Informal agency synonym only; not an MVP entity or persistence model |
| Agency | Customer business represented by a Workspace; not a separate MVP entity |
| Event | Immutable, versioned fact that occurred |
| Command | Request for one owner to attempt a state change |
| Query | Side-effect-free request to an owner’s public read interface |
| External effect | State change outside Rightjob AI OS |
| Consequential commitment | Point at which a high-risk/irreversible effect becomes externally observable |
| Plan acceptance | User/policy acceptance of proposed work; not action approval |
| Action approval | Authorization bound to a specific consequential effect |

## Deprecated or restricted terms

- **Action** is not a synonym for Capability. Use it only for a policy/audit verb
  or a legacy storage name awaiting migration.
- **Agent** does not define a module boundary. Specialist reasoning, if used,
  remains an internal implementation behind a capability and cannot communicate
  freely with another agent.
- **Provider** means a vendor adapter, not a domain owner.
- **Workflow Builder** is the Workflow Compiler unless referring to the deferred
  no-code product.
- **Procedural Memory** is not an owner of workflows or policies.
- **Executive planning** means conversational goal clarification, not task
  decomposition.
