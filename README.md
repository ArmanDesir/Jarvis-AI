# Rightjob AI OS

Rightjob AI OS is a multi-tenant agency operating system governed by the
[Architecture Constitution](docs/constitution/README.md). Phase 1 provides only
a runnable engineering foundation: a FastAPI health process, idle worker,
Next.js status shell, module boundaries, PostgreSQL migration scaffolding, tests,
and CI.

No business Capability, AI call, workflow execution, authentication flow,
Memory retrieval, provider integration, or external effect is implemented.

## Requirements

- Python 3.11 or newer
- [UV](https://docs.astral.sh/uv/) 0.12 or compatible
- Node.js 20.20.2 or newer with npm 10+
- Docker only when running optional local PostgreSQL

## Quick start

```bash
cp .env.example .env
make install
make dev-api
```

In separate terminals:

```bash
make dev-worker
make dev-web
```

System endpoints:

- API: `GET http://127.0.0.1:8000/health`
- Readiness: `GET http://127.0.0.1:8000/ready`
- Version: `GET http://127.0.0.1:8000/version`
- Web: `http://127.0.0.1:3000`

Run the full local validation with:

```bash
make ci
```

## Documentation

- [Local setup](docs/implementation/local-setup.md)
- [Phase 1 architecture review](docs/implementation/00-phase1-architecture-review.md)
- [Repository structure](docs/implementation/repository-structure.md)
- [Command reference](docs/implementation/commands.md)
- [Environment variables](docs/implementation/environment.md)
- [Contribution rules](docs/implementation/contributing.md)
- [Architecture boundaries](docs/implementation/architecture-boundaries.md)
- [Phase status](docs/implementation/phase-status.md)
- [Phase 1 report](docs/implementation/01-repository-bootstrap-report.md)

Managed Temporal is the approved Durable Workflow Engine after the completed
Phase 2.5 proof. Clerk/Auth.js and `pgvector` remain proof-gated. Redis is
deferred.
