# Module Boundaries

## Modules

The initial logical modules are Identity/Tenancy, Executive, Context/Memory,
Planning, Orchestration, Department Registry, Policy/Approval, Work, Content,
Integrations, Audit/Observability, and Usage.

Logical modules do not imply separate services. Deployment boundaries remain a
modular monolith plus independently scalable API and worker processes unless an
ADR approves extraction.

## Allowed communication

- Synchronous command/query through the owner’s published application interface.
- Versioned domain/integration event through the outbox.
- Orchestrator invocation of a published capability.
- Tool invocation through a vendor-neutral interface.

## Forbidden communication

- Importing another module’s `domain`, `application`, `infrastructure`, repository,
  ORM model, or private DTO.
- Querying or mutating another module’s tables.
- Sharing writable domain entities between modules.
- Calling another department or plugin directly.
- Using a WebSocket, cache, prompt, or event bus as the only durable state.

## Dependency direction

Domain rules depend only on domain values. Application use cases depend on domain
and owned ports. Infrastructure implements those ports. Composition roots wire
implementations. Public contracts contain no framework, ORM, or vendor types.

## Cross-module reads

Use the owning module’s query interface. For high-volume read composition, build
a consumer-owned projection from versioned events. A projection is disposable
and cannot be written back as the source of truth.

## Boundary enforcement

CI must verify import rules, owned migration paths, prohibited SDK imports,
contract compatibility, and plugin dependencies. Database roles and RLS provide
runtime defense. Architectural review is required for new module edges.
