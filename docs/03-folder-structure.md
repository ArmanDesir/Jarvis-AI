# Folder Structure

**Status:** Architecture-reconciled draft; implementation not authorized

The repository is a monorepo so contracts, migrations, and end-to-end changes can
be reviewed atomically. Boundaries are enforced by imports and tests rather than
by creating many repositories.

```text
rightjob-ai-os/
├── apps/
│   ├── web/                         # Next.js UI and browser voice client
│   │   ├── src/app/
│   │   ├── src/features/
│   │   ├── src/components/
│   │   └── src/lib/
│   └── api/                         # FastAPI composition root
│       ├── src/main.py
│       ├── src/http/
│       ├── src/realtime/
│       └── src/bootstrap/
├── services/
│   ├── worker/                      # Workflow-engine-neutral worker composition root
│   │   ├── src/workflows/
│   │   ├── src/activities/
│   │   └── src/main.py
│   └── outbox/                      # Transactional outbox relay
├── packages/
│   ├── core/                        # Pure Python domain and application modules
│   │   ├── identity/
│   │   ├── executive/
│   │   ├── context/
│   │   ├── planning/
│   │   ├── orchestration/
│   │   ├── departments/
│   │   ├── policy/
│   │   ├── memory/
│   │   ├── work/
│   │   ├── content/
│   │   ├── integrations/
│   │   ├── audit/
│   │   ├── validation/
│   │   ├── ai_routing/
│   │   └── usage/
│   ├── plugin_sdk/                  # Manifest and Capability contracts
│   ├── provider_ports/              # Vendor-neutral interfaces and value types
│   ├── provider_adapters/           # Vendor SDK implementations
│   ├── contracts/                   # OpenAPI, events, JSON Schemas
│   └── ui/                          # Shared accessible UI primitives
├── departments/
│   ├── website/
│   │   ├── department.yaml
│   │   ├── schemas/
│   │   ├── activities/
│   │   └── tests/
│   ├── marketing/
│   └── operations/
├── db/
│   ├── migrations/                 # Namespaced and owned by module
│   ├── policies/                    # PostgreSQL RLS policies
│   └── seeds/                       # Development-only reference data
├── evals/
│   ├── datasets/
│   ├── graders/
│   └── scenarios/
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── workflow/
│   └── e2e/
├── deploy/
│   ├── docker/
│   └── environments/
├── docs/
│   ├── decisions/                   # Architecture Decision Records
│   ├── runbooks/
│   └── ...
├── scripts/                         # Small repeatable developer/CI commands
├── .github/workflows/
├── pyproject.toml                   # Python workspace and tooling
├── package.json                     # JavaScript workspace scripts
└── README.md
```

## Module internals

Each core module may contain:

```text
module/
├── domain/          # Entities, value objects, domain events, invariants
├── application/     # Commands, queries, use cases, ports
├── infrastructure/  # Repositories and adapters for that module
└── contracts/       # Public DTOs/events; the only cross-module imports
```

Not every module must have every directory. Create a directory only when it has
content.

## Dependency rules

```text
domain <- application <- infrastructure <- composition roots
                     ^
               public contracts
```

- Domain code is framework- and vendor-free.
- HTTP and workflow-engine entry points call application use cases.
- Infrastructure implements ports; it does not define business policy.
- Plugins depend on `plugin_sdk` and public contracts, never API internals.
- Frontend feature code consumes generated API types.
- Database migrations are the only mechanism for schema changes.

## Configuration

Configuration is typed and loaded at process startup. Environment variables hold
deployment-specific values and secret references, not workflow definitions.
Workspace policies, plugin activation, and provider routing are stored as
versioned data.

## Ownership boundary

A package owns its tables, events, and write operations. Cross-module reads use
queries or projections; cross-module work uses commands/events. This enables
later extraction without pretending the initial deployment is distributed.
