# Core module boundaries

These packages are logical modules in one modular codebase. An empty package is a
registration point, not an implemented feature.

| Package | Published responsibility |
|---|---|
| `executive` | User conversation and presentation |
| `context` | Context Resolver |
| `planner` | Typed plan proposals |
| `orchestration` | Workflow Compiler and Orchestrator state |
| `policy` | Authorization, risk, quota, approval boundary |
| `work` | Canonical client/project records |
| `identity` | Identity/Tenancy |
| `memory` | Derived knowledge representations |
| `ai_router` | Eligible AI adapter routing |
| `validation` | Deterministic Validator |
| `reviewer` | Qualitative Reviewer |
| `tool_interfaces` | Vendor-neutral Tool contracts |
| `provider_adapters` | Vendor implementations only |
| `repositories` | Shared repository conventions; repositories remain module-owned |
| `contracts` | Published shared contracts |
| `registry` | Department manifest and Capability registry |
| `audit` | Audit/Observability |
| `content` | Generic files and source content |
| `usage` | Usage/cost measurement |

The architecture check rejects forbidden cross-module imports. A module needing
another owner's behavior imports only that owner's future published contract.

