# Dependency Direction Diagram

```text
                         USER
                           |
                    Public API / UI
                           |
              +------------v-------------+
              | Application Interfaces   |
              | commands · queries       |
              +------------+-------------+
                           |
        +------------------+------------------+
        |                  |                  |
  Executive/Context     Planning         Policy/Registry
        |                  |                  |
        +------------------+------------------+
                           |
                 Orchestration Interfaces
                           |
                  Workflow Compiler/Run
                           |
                   Capability Contract
                           |
                  Department Capability
                           |
                     Tool Interface
                           |
                    Provider Adapter
                           |
                    External Provider

Within every module:

Domain <- Application <- Infrastructure <- Composition Root
   ^           |
   +---- owned public contracts

Cross-cutting observation:
All boundaries --versioned evidence/events--> Audit & Observability
```

## Direction rules

- Dependencies point toward stable domain/public contracts, never toward vendor,
  framework, ORM, or another module’s internals.
- Orchestration depends on capability contracts, not plugin implementations.
- Departments depend on Tool/AI ports, not adapters.
- Infrastructure implements owned ports and is wired only at composition roots.
- Events may notify consumers but do not grant direct ownership or callback
  authority.
- The Database and external vendors are replaceable infrastructure leaves, not
  upstream business dependencies.
