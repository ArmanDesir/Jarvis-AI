# Environment variables

All variables use the `RIGHTJOB_` namespace except browser-safe Next.js values.
See `.env.example` for defaults.

| Namespace | Variables | Phase 1 default |
|---|---|---|
| Runtime | `RIGHTJOB_ENVIRONMENT`, `RIGHTJOB_LOG_LEVEL`, `RIGHTJOB_BUILD_VERSION` | Local/info/dev |
| API | `RIGHTJOB_API_HOST`, `RIGHTJOB_API_PORT`, `RIGHTJOB_API_DATABASE_REQUIRED` | Database not required |
| Worker | `RIGHTJOB_WORKER_ID`, `RIGHTJOB_WORKER_POLL_SECONDS` | Idle local worker |
| Database | `RIGHTJOB_DATABASE_ENABLED`, `RIGHTJOB_DATABASE_URL` | Disabled |
| Storage | `RIGHTJOB_STORAGE_ENABLED`, `RIGHTJOB_STORAGE_ENDPOINT`, `RIGHTJOB_STORAGE_REGION` | Disabled |
| Identity | `RIGHTJOB_IDENTITY_ENABLED`, `RIGHTJOB_IDENTITY_ADAPTER` | Disabled |
| AI | `RIGHTJOB_AI_ENABLED`, `RIGHTJOB_AI_ADAPTER` | Disabled |
| Workflow | `RIGHTJOB_WORKFLOW_ENABLED`, `RIGHTJOB_WORKFLOW_ADAPTER` | Disabled |
| Frontend | `NEXT_PUBLIC_API_BASE_URL` | Local API URL |

Startup rejects invalid booleans, integer ranges, enabled database without a URL,
and enabled proof-gate namespace without an adapter name.

Never commit `.env`, provider credentials, tokens, private keys, or production
connection strings.

