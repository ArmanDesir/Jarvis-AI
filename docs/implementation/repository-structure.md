# Repository structure

```text
apps/
├── api/                 FastAPI composition root
└── web/                 Next.js status shell
services/
└── worker/              Separate idle worker process
packages/
├── core/                Vendor-free module boundaries and shared primitives
├── contracts/           Future versioned public schemas
├── plugin_sdk/          Future first-party plugin SDK
├── provider_ports/      Future vendor-neutral ports
└── provider_adapters/   Future vendor implementations
departments/
├── marketing/           Trusted first-party placeholder
├── website/             Trusted first-party placeholder
└── operations/          Trusted first-party placeholder
db/
└── migrations/          Module-owned Alembic migration stream
tests/
├── unit/
├── integration/
└── architecture/
scripts/                 CI-safe architecture, migration, secret, clean checks
docs/                    Authoritative architecture and implementation guides
.github/workflows/       Validation only; no deployment
```

API and worker share `rightjob-core` but remain independently runnable.
Logical modules are packages in `packages/core/src/rightjob`; they are not
microservices.

