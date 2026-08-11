# Local setup

## Required tools

Install Python 3.11+, UV 0.12, Node 20.20.2+, and npm 10+. Docker is optional.

```bash
cp .env.example .env
make install
make ci
```

`.env` is ignored. Local defaults contain no secrets and disable database,
storage, identity, AI, and workflow adapters.

## Optional PostgreSQL

```bash
docker compose up -d postgres
```

Then set:

```text
RIGHTJOB_DATABASE_ENABLED=true
RIGHTJOB_DATABASE_URL=postgresql+psycopg://rightjob:rightjob@localhost:5432/rightjob
```

PostgreSQL is not required for health-only bootstrap startup. No production table
exists in Phase 1.

## Processes

```bash
make dev-api
make dev-worker
make dev-web
```

The worker remains idle until stopped. The API exposes only health, readiness,
and version metadata. The frontend exposes only system status.
