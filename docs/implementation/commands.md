# Command reference

| Purpose | Command |
|---|---|
| Install locked dependencies | `make install` |
| Start API | `make dev-api` |
| Start idle worker | `make dev-worker` |
| Start frontend | `make dev-web` |
| Python and frontend lint | `make lint` |
| Apply formatting | `make format` |
| Check formatting | `make format-check` |
| Type check | `make typecheck` |
| Unit tests | `make test-unit` |
| Integration tests | `make test-integration` |
| Architecture checks | `make test-architecture` |
| All tests | `make test` |
| Build all packages/apps | `make build` |
| Apply migrations | `make migrate` |
| Validate migration safety | `make migration-check` |
| Secret hygiene | `make secret-check` |
| Full CI validation | `make ci` |
| Remove known generated artifacts | `make clean` |

`make install` requires committed `uv.lock` and `package-lock.json`. The current
execution environment could not download UV or npm dependencies, so lockfile
generation remains a Phase 1 condition documented in the bootstrap report.

