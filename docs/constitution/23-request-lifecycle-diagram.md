# Request Lifecycle Diagram

## Authoritative ordered lifecycle

User Input → Command Classification → Executive AI when reasoning is required →
Context Resolver and Memory Retrieval → Department Registry Discovery → Planner →
Plan Validator → Policy Engine → Workflow Compiler → Orchestrator → Department
Capability → Tool Interface when required → Provider Adapter when required →
Execution Result and Evidence → Deterministic Validator → Reviewer when qualitative
review is required → Policy and Approval Gate before consequential commitment →
Orchestrator commits, retries, compensates, or fails → Memory and Audit updates →
Executive AI presents the final result → User.

```text
User Input
   |
   v
Command Classification
   |
   +-- deterministic command -------------------------------+
   |                                                        |
   +-- reasoning required --> Executive AI                  |
                              |                             |
                              v                             |
                    Context Resolver <--> Memory Retrieval  |
                              |                             |
                              v                             |
                    Department Registry Discovery           |
                              |                             |
                              v                             |
                           Planner                          |
                              |                             |
                              v                             |
                       Plan Validator <----------------------+
                              |
                              v
                        Policy Engine
                              |
                              v
                     Workflow Compiler
                              |
                              v
                        Orchestrator
                              |
                              v
                    Department Capability
                              |
                      [when required]
                              v
                       Tool Interface
                              |
                      [when required]
                              v
                      Provider Adapter
                              |
                              v
                 Execution Result + Evidence
                              |
                              v
                 Deterministic Validator
                              |
                     [when required]
                              v
                          Reviewer
                              |
                              v
          Policy + Approval Gate before commitment
                              |
                              v
        Orchestrator commits / retries / compensates / fails
                              |
                              v
                    Memory + Audit updates
                              |
                              v
               Executive AI presents final result
                              |
                              v
                            User
```

## Fast-path clarification

Opening a dashboard, listing tasks, retrieving a known project, changing a
supported setting, cancelling an eligible workflow, or approving a pending
request may bypass Executive reasoning and Planner. The fast path rejoins at
deterministic validation/policy or the appropriate application command.

No fast path bypasses authentication, tenant resolution, authorization, policy,
validation, persistence ownership, audit, or correlation.

## Control clarification

Registry discovery constrains the Planner to enabled capabilities. Provider
selection occurs only after a capability declares AI/tool requirements. Every
result returns to Orchestrator; providers and departments never communicate
directly with the user.
