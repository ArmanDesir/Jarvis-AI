# Phase 1.6 Python and Database Toolchain Verification Report

**Completed:** 2026-08-06  
**Scope:** Frozen Phase 1 bootstrap only  
**Verdict:** PHASE 1 CONDITIONS CLEARED

## Summary

Python, UV locking, FastAPI, the idle worker, Python quality gates, package
builds, the repository CI-equivalent command, and the complete isolated
PostgreSQL runtime lifecycle were verified successfully. PostgreSQL 17.7 was
inspected, copied project-locally, initialized, started, migrated through the
approved empty lifecycle, inventoried, exercised through read-only API/client
checks, and shut down cleanly.

No Constitution, ADR, ownership, contract, architecture, schema-design, API,
roadmap, sprint, or business-scope document was changed. Phase 2 was not
started.

## Versions and locations

| Tool | Version | Executable | Location result |
|---|---|---|---|
| UV | 0.12.0 (`b88d7c5c4`, x86_64 Apple Darwin) | `.tooling/uv/0.12.0/uv-x86_64-apple-darwin/uv` | Project-local |
| Managed Python | CPython 3.11.15, macOS x86_64 | `.tooling/uv-python/cpython-3.11-macos-x86_64-none/bin/python3.11` | Project-local |
| Project environment Python | CPython 3.11.15 | `.venv/bin/python` | Project-local |
| System Python | CPython 3.8.2 | `/usr/bin/python3` | Unchanged |
| FastAPI | 0.140.13 | Locked environment | Project-local |
| Uvicorn | 0.51.0 | Locked environment | Project-local |
| SQLAlchemy | 2.0.51 | Locked environment | Project-local |
| Alembic | 1.18.5 | Locked environment | Project-local |
| PostgreSQL | 17.7 (Postgres.app 2.9.2) | `.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/postgres` | Project-local; verified and stopped |

UV cache and managed Python storage are under `.tooling/uv-cache/` and
`.tooling/uv-python/`. No shell profile, global runtime, or system directory was
modified.

## Verified UV acquisition

- Pinned version: `0.12.0`, matching the existing CI version.
- Official artifact:
  `https://github.com/astral-sh/uv/releases/download/0.12.0/uv-x86_64-apple-darwin.tar.gz`
- Official checksum metadata:
  `https://github.com/astral-sh/uv/releases/download/0.12.0/uv-x86_64-apple-darwin.tar.gz.sha256`
- Expected and observed SHA-256:
  `d41593beaefc54bab7d062af0ef6ca093bfb81d001d58ebbef39e44423f9c496`
- Archive destination: `.tooling/uv/0.12.0/`

The archive was downloaded without execution, hashed with `shasum -a 256`,
compared to Astral's official release checksum, and extracted only after the
complete digest matched.

## Dependency locking and installation

`pyproject.toml` remains the canonical dependency definition.

| Evidence | Result |
|---|---|
| `uv lock --python <managed-python>` | PASS; resolved 46 packages |
| Real `uv.lock` | PASS |
| Lock SHA-256 | `88a20983d4248613f52767b5d05e46188674eb826fbe656301c1f614ee0f5847` |
| `uv lock --check` | PASS |
| Repeat lock | PASS; lock hash unchanged |
| `uv sync --all-packages --all-groups --locked` | PASS |
| `uv sync --all-packages --all-groups --frozen` | PASS; checked 43 installed packages |

The initial workspace sync without `--all-packages` omitted API/worker package
dependencies. The repository `make install` command was corrected to include all
existing workspace packages. This is a Phase 1 bootstrap defect correction, not
an architecture change.

## Commands executed

All commands ran from the repository root unless stated otherwise.

| Command or operation | Exit | Result |
|---|---:|---|
| Host tool discovery | 0 | Found only system Python 3.8.2; no pre-existing UV or PostgreSQL. |
| Retrieve official UV checksum metadata | 0 | Expected checksum obtained from Astral's GitHub release. |
| Download and hash UV archive | 0 | Exact checksum match. |
| Extract UV and run `uv --version` | 0 | UV 0.12.0 verified. |
| `uv python install 3.11` with project-local storage | 0 | Installed CPython 3.11.15. |
| Managed/system Python path and version checks | 0 | Managed runtime local; `/usr/bin/python3` unchanged at 3.8.2. |
| `uv lock --python ...` | 0 | Real lock generated. |
| `uv lock --check` and repeat lock hash | 0 | Lock current and stable. |
| Locked and frozen all-package syncs | 0 | Dependencies installed reproducibly. |
| First repository-wide Ruff run | 1 | Generated `.tooling` cache was scanned as source. Corrected generated-tooling exclusions without weakening source rules. |
| Ruff format of repository-owned Python | 0 | 33 bootstrap Python files normalized. |
| `uv run ruff format --check .` | 0 | 122 repository files formatted. |
| `uv run ruff check .` | 0 | All checks passed. |
| `uv run mypy` | 0 | Strict check passed for 40 source files. |
| `uv run pytest -m "not integration"` | 0 | 10 passed, 4 deselected. |
| `uv run pytest -m integration` | 0 | 3 passed, 1 future-schema test skipped, 10 deselected. |
| `uv run python scripts/check_architecture.py` | 0 | PASS. |
| `uv run python scripts/check_phase1_scope.py` | 0 | PASS. |
| `uv run python scripts/check_migrations.py` | 0 | PASS. |
| `uv run python scripts/check_secrets.py` | 0 | PASS. |
| Locked Python `compileall` | 0 | PASS. |
| First sandboxed `uv build --all-packages` in `make ci` | 2 | DNS denied access to the declared Hatchling build requirement. |
| Escalated `uv build --all-packages` | 0 | All three source distributions and wheels built. |
| Final `make ci` with local UV/Python/Node paths | 0 | Formatting, lint, typing, Python/Node tests, architecture/scope, builds, migration safety, and secrets all passed. |

The test suite reports a Starlette deprecation warning concerning its current
TestClient/httpx compatibility path. It is not a test failure and was not
addressed through a dependency-major change.

## FastAPI evidence

Startup command:

```text
.tooling/uv/0.12.0/uv-x86_64-apple-darwin/uv run uvicorn \
  rightjob_api.main:app --app-dir apps/api/src \
  --host 127.0.0.1 --port 8016
```

| Route | HTTP status | Sanitized response |
|---|---:|---|
| `/health` | 200 | `{"status":"running"}` |
| `/ready` | 200 | Ready; required dependencies ready; database, storage, identity, AI, and workflow proof-gate dependencies explicitly disabled/optional. |
| `/version` | 200 | `{"service":"rightjob-api","version":"0.1.0","build":"dev"}` |
| `/not-a-route` | 404 | `{"detail":"Not Found"}` |

Startup logged `api.started` with environment metadata. Ctrl-C initiated a clean
Uvicorn shutdown, logged `api.stopped`, completed application shutdown, and
exited normally. No business endpoint or external effect exists.

## Worker evidence

The worker was launched through the locked UV environment. It logged:

- identity `worker-local`;
- workflow engine `disabled`;
- workflow execution disabled.

It remained idle, received `SIGTERM`, logged `worker.stopped`, and exited 0. No
provider or external service was contacted.

## PostgreSQL status

PostgreSQL runtime verification is **complete**. The retained project-local
cluster is stopped, and no socket, listener, PID file, or PostgreSQL process
remains. No production or shared database was contacted.

The inspected trusted candidate is Postgres.app `2.9.2`. Its official
legacy-download page explicitly supports macOS 10.15, and inspection confirmed
that its universal/Intel bundle contains PostgreSQL 17.7:

| Item | Candidate detail |
|---|---|
| Provider | Postgres.app project (`PostgresApp/PostgresApp`), PostgreSQL-licensed |
| Artifact | `Postgres-2.9.2-13-14-15-16-17-18.dmg` |
| Official URL | `https://github.com/PostgresApp/PostgresApp/releases/download/v2.9.2/Postgres-2.9.2-13-14-15-16-17-18.dmg` |
| Artifact size | 583,520,231 bytes (GitHub release metadata; provider describes 584 MB) |
| SHA-256 | `816e5b59ead707dd2a9ca8f859aa7461d533bdfe347ab542d829eb4f26cb2e00` |
| Database version | PostgreSQL 17.7 |
| Platform | Universal/Intel; provider requires macOS 10.15 |
| Downloaded location | `.tooling/postgresql/artifacts/Postgres-2.9.2-13-14-15-16-17-18.dmg` |
| Verified runtime destination | `.tooling/postgresql/runtime/postgresapp-2.9.2/17/` |
| Verified port | `55416`, localhost only |
| Verified data directory | `.tooling/postgresql/data/phase16-pg17/` |
| Verified database | `rightjob_phase16` |
| Verified role | `rightjob_phase16_owner` |

### Read-only artifact evidence

The 583,520,231-byte artifact was hashed before mounting. Its observed SHA-256
exactly matched the official digest above. `hdiutil` also verified the disk
image's internal CRC32 checks before mounting it at:

```text
/Volumes/Postgres-2.9.2-13-14-15-16-17-18
```

The mount was `read-only`, `nodev`, `nosuid`, `noowners`, and `nobrowse`.
Postgres.app was never opened or launched.

| Measurement | Result |
|---|---:|
| Application bundle | 1,994,076 KiB (approximately 1.902 GiB) |
| PostgreSQL 17 directory | 392,536 KiB (approximately 383.3 MiB) |

`Contents/Info.plist` identifies Postgres.app 2.9.2 build 349, macOS as its
supported platform, and `LSMinimumSystemVersion` 10.15. Every inspected
PostgreSQL executable is a universal Mach-O containing both x86_64 and arm64
slices. The x86_64 Mach-O load commands declare minimum macOS 10.15 and SDK
14.4.

The following files were confirmed:

| Tool | Inspected path relative to `Postgres.app/Contents/Versions/17/` |
|---|---|
| Server | `bin/postgres` |
| Cluster initialization | `bin/initdb` |
| Server control | `bin/pg_ctl` |
| SQL client | `bin/psql` |
| Database creation | `bin/createdb` |
| Database deletion | `bin/dropdb` |
| Readiness | `bin/pg_isready` |

`lib/postgresql/pgxs/src/Makefile.global` declares `VERSION = 17.7` and
`VERSION_NUM = 170007`; the included documentation is also PostgreSQL 17.7.

Immediate bundled dependencies reported by `otool -L` include:

- `postgres`: `libzstd.1`, `liblz4.1`, `libxml2.2`, `libssl.3`,
  `libcrypto.3`, `libicui18n.75`, and `libicuuc.75`;
- `initdb`: `libpq.5` and `libicuuc.75`;
- `psql`, `createdb`, `dropdb`, and `pg_isready`: `libpq.5`;
- macOS system dependencies: `libSystem.B`, `libz`, and `libedit` where
  applicable.

All `@loader_path/../lib` dependencies were present. Versioned symlinks for
zstd, lz4, and ICU resolved inside the PostgreSQL 17 `lib` directory.

Code-signing evidence:

- bundle identifier `com.postgresapp.Postgres2`;
- Developer ID Application `Jakob Egger (ZF84SJ5A3G)`;
- Apple Developer ID certificate chain;
- hardened-runtime signature;
- timestamp 2025-11-16;
- deep/strict verification: valid on disk and satisfies its designated
  requirement;
- Gatekeeper: accepted, source `Notarized Developer ID`;
- `postgres` itself is signed by the same Developer ID and team.

The image was detached successfully after inspection. No Postgres.app,
PostgreSQL, login-helper, or database process was launched.

Artifact cleanup command, not executed:

```text
rm ".tooling/postgresql/artifacts/Postgres-2.9.2-13-14-15-16-17-18.dmg"
```

### Approved PostgreSQL 17 runtime copy evidence

The artifact digest was verified again before the runtime copy:

```text
816e5b59ead707dd2a9ca8f859aa7461d533bdfe347ab542d829eb4f26cb2e00
```

The destination did not exist before copying. The DMG was mounted read-only,
and only:

```text
Postgres.app/Contents/Versions/17
```

was copied to:

```text
.tooling/postgresql/runtime/postgresapp-2.9.2/17
```

`ditto --rsrc --extattr` preserved directory structure, permissions, extended
metadata, and symlinks. Verification results:

| Evidence | Source | Copied runtime |
|---|---:|---:|
| Allocated size (`du -sk`) | 392,536 KiB on mounted HFS | 388,924 KiB on local filesystem |
| Regular files | 5,104 | 5,104 |
| Symlinks | 903 | 903 |
| Copied logical regular-file bytes | — | 385,852,250 bytes |

The allocated-size difference is attributable to the source and destination
filesystems' allocation units. `diff -qr` reported no content differences.

The copied runtime still identifies PostgreSQL `17.7` / `170007`; its
`postgres` executable remains a universal x86_64/arm64 Mach-O. All required
executables and bundled libraries listed in the artifact-inspection section
were present at the copied destination.

The mounted image was detached successfully after the comparison, and a mount
check confirmed that the volume was no longer attached. No PostgreSQL binary
was executed. Cluster initialization, startup, migrations, and runtime cleanup
remain unapproved.

### PostgreSQL initialization attempt

Initialization was approved with the following isolated paths:

```text
runtime: .tooling/postgresql/runtime/postgresapp-2.9.2/17
data:    .tooling/postgresql/data/phase16-pg17
socket:  .tooling/postgresql/socket
```

The data directory and temporary-password path were confirmed absent before the
attempt. The data and socket directories were created with the invoking user's
ownership. A 44-byte generated password was written to:

```text
.tooling/postgresql/.phase16-initdb-password
```

with mode `0600`. The password was not printed. The copied project-local
`initdb` was invoked with:

```text
-D .tooling/postgresql/data/phase16-pg17
-U rightjob_phase16_owner
--encoding=UTF8
--locale=C
--auth-local=trust
--auth-host=scram-sha-256
--pwfile=.tooling/postgresql/.phase16-initdb-password
```

`initdb` confirmed the approved locale and began creating configuration files,
but its bootstrap subprocess failed:

```text
FATAL: could not create shared memory segment: Operation not permitted
DETAIL: Failed system call was shmget(...).
child process exited with exit code 1
```

This is an execution-sandbox restriction on System V shared memory, not a
manifest, migration, architecture, permission-mode, or PostgreSQL artifact
failure. Per the phase instruction, no retry was attempted.

`initdb` removed the partial cluster contents automatically. Post-attempt
verification:

| Check | Result |
|---|---|
| `initdb` exit status | 1 |
| Temporary password file | Deleted |
| Data directory | Empty, 0 KiB |
| Socket directory | Empty, 0 KiB |
| `PG_VERSION` | Absent |
| `postgresql.conf` | Absent |
| `pg_hba.conf` | Absent |
| `pg_ident.conf` | Absent |
| PostgreSQL startup | Not attempted |
| Database/migrations | Not attempted |

At that point initialization remained unverified and required a separately
approved retry in an execution context that permitted PostgreSQL's required
shared-memory operation.

#### Approved outside-sandbox initialization retry

Before the retry, the data directory was reconfirmed empty, the temporary
password file was absent, and the copied `initdb` was executable. Exactly one
outside-sandbox retry was performed because PostgreSQL requires shared memory.
All initialization parameters remained unchanged.

The retry selected POSIX dynamic shared memory and completed successfully:

```text
creating configuration files ... ok
running bootstrap script ... ok
performing post-bootstrap initialization ... ok
syncing data to disk ... ok
password_deleted=true initdb_status=0
```

Post-retry evidence:

| Check | Result |
|---|---|
| `initdb` exit status | 0 |
| Temporary password file | Deleted |
| `PG_VERSION` | `17` |
| `postgresql.conf` | Present, 30,662 bytes, mode `0600` |
| `pg_hba.conf` | Present, 5,743 bytes, mode `0600` |
| `pg_ident.conf` | Present, 2,640 bytes, mode `0600` |
| Cluster ownership | OS user `rightjobsolutions`, group `staff` |
| Cluster permissions | `0700` |
| Socket-directory ownership | OS user `rightjobsolutions`, group `staff` |
| Socket-directory permissions | `0700` |
| Initialized cluster size | 39,812 KiB (approximately 39 MiB) |
| PostgreSQL process after initialization | None |

Generated authentication rules match the approved initialization:

- local normal and replication connections: `trust`;
- IPv4 and IPv6 host normal and replication connections:
  `scram-sha-256`.

No database server was started, no application database was created, and no
migration was executed. Initialization is now verified; startup remains
unapproved.

### PostgreSQL startup verification attempt

Startup was approved for the initialized project-local cluster with explicit
data, log, host, port, and socket paths. The first startup command failed before
the server became ready:

```text
waiting for server to start.... stopped waiting
pg_ctl: could not start server
```

The project-local log identified the exact cause:

```text
postgres: invalid argument: "Agent/.tooling/postgresql/socket"
```

The repository path contains a space (`AI Agent`). `pg_ctl -o` split the
unquoted socket-directory argument before passing it to `postgres`. This is a
startup command-quoting defect, not a PostgreSQL runtime, cluster, address,
port, or architecture failure.

Per the startup instruction, no automatic retry was attempted. Failure-state
verification found:

| Check | Result |
|---|---|
| `pg_ctl` exit status | 1 |
| Server reached readiness | No |
| `postmaster.pid` | Absent |
| TCP listener on 55416 | None |
| PostgreSQL/Postgres.app process | None |
| Project-local socket | None |
| Application database | Not created |
| Migrations | Not executed |

The cluster remains initialized and stopped. A corrected retry requires
separate approval and must quote the socket path inside the `pg_ctl -o` option
string so that `postgres` receives it as one argument.

#### Approved quoted-socket startup retry

Exactly one corrected retry quoted the absolute socket directory inside the
`pg_ctl -o` option string. PostgreSQL started and reached readiness:

```text
waiting for server to start.... done
server started
startup_ms=158
.../.tooling/postgresql/socket:55416 - accepting connections
```

Runtime queries returned:

| Setting | Observed value |
|---|---|
| `server_version` | `17.7 (Postgres.app)` |
| `data_directory` | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/data/phase16-pg17` |
| `port` | `55416` |
| `listen_addresses` | `127.0.0.1` |
| `unix_socket_directories` | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/socket` |

The fail-closed verifier compared the complete vendor-qualified version string
to the literal `17.7`. Although the reported semantic PostgreSQL version is
17.7, the additional ` (Postgres.app)` qualifier caused the literal assertion
to fail:

```text
verification_failure=version
```

The verifier immediately issued a fast shutdown before proceeding to the
remaining master-runtime and listener assertions. Shutdown-state verification
confirmed:

| Check | Result |
|---|---|
| `pg_isready` after shutdown | No response |
| `postmaster.pid` | Absent |
| TCP listener on 55416 | None |
| PostgreSQL/Postgres.app process | None |
| Project-local socket | Removed |
| Database created | No |
| Migration executed | No |

The PostgreSQL log independently confirms that version 17.7 started, listened
on IPv4 `127.0.0.1:55416`, used the approved project-local socket, became ready,
received the fast-shutdown request, checkpointed, and shut down cleanly.

No further retry was attempted. To complete startup verification, a separately
approved retry must parse or prefix-match the semantic version `17.7` while
still retaining exact checks for data directory, port, listen address, socket,
runtime path, and exclusive listener state.

#### Final semantic-version startup verification

One final approved retry used PostgreSQL's numeric version setting for the exact
semantic check:

```text
server_version_num = 170007
```

The retry passed every fail-closed assertion:

| Check | Result |
|---|---|
| Startup duration | 2,256 ms |
| `pg_isready` | Accepting connections |
| `server_version` | `17.7 (Postgres.app)` |
| `server_version_num` | `170007` |
| `data_directory` | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/data/phase16-pg17` |
| `port` | `55416` |
| `listen_addresses` | `127.0.0.1` |
| `unix_socket_directories` | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/socket` |
| Master PID at verification | `11141` |
| Master executable | Copied project-local `.../runtime/postgresapp-2.9.2/17/bin/postgres` |
| TCP listeners owned by PostgreSQL | Only `127.0.0.1:55416` |
| Other PostgreSQL TCP instance | None observed |

The verified cluster remains running solely for the next separately approved
database and migration verification step. No application database, additional
role, migration, API process, or worker process was created or started during
this verification.

### Database creation attempt

Before creation, the existing `rightjob_phase16_owner` role was verified. It is
the bootstrap role created by `initdb` and retains these unmodified attributes:

- login, inherit, superuser, create-role, create-database, replication, and
  bypass-RLS enabled;
- connection limit `-1`;
- no privilege or password change was made during this step.

The target `rightjob_phase16` database was confirmed absent. The approved
creation command then failed client-side before contacting PostgreSQL:

```text
createdb: unrecognized option `--connection-limit=-1'
createdb: hint: Try "createdb --help" for more information.
```

This Postgres.app PostgreSQL 17 `createdb` build does not expose a
`--connection-limit` command-line option. PostgreSQL would assign the approved
default `-1` automatically, but no corrected retry was attempted.

Post-failure verification confirmed:

| Check | Result |
|---|---|
| `rightjob_phase16` database count | `0` |
| Partial database/object created | No |
| Role altered | No |
| Migration executed | No |
| PostgreSQL readiness | Still accepting connections on the approved socket/port |

Database creation remains incomplete. A separately approved retry should omit
the unsupported client option and verify `datconnlimit = -1` from `pg_database`
after creation, retaining the existing fail-closed removal behavior.

#### Corrected database-creation retry

Before the single approved retry, the target database count was reconfirmed as
zero. The retry omitted only the unsupported connection-limit client option and
created the database from `template0` with the approved owner, encoding, and
locale.

Catalog verification passed:

| Field | Verified value |
|---|---|
| `datname` | `rightjob_phase16` |
| owner | `rightjob_phase16_owner` |
| encoding | `UTF8` |
| `datcollate` | `C` |
| `datctype` | `C` |
| `datconnlimit` | `-1` |
| matching database count | `1` |

Active-database evidence:

| Field | Value |
|---|---|
| current database | `rightjob_phase16` |
| current role | `rightjob_phase16_owner` |
| cluster data directory | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/data/phase16-pg17` |
| approved listener setting | `127.0.0.1:55416` |
| database OID | `16387` |
| physical database directory | `/Users/rightjobsolutions/Projects/AI Agent/.tooling/postgresql/data/phase16-pg17/base/16387` |

The rollback guard was retained but was not needed. No role was altered, no
second database was created, and no schema, extension, table, migration, or
other application object was created by this step. PostgreSQL remains running
for separately approved migration verification.

### Alembic lifecycle harness attempt

The migration directory was checked immediately before execution:

```text
db/migrations/versions/README.md
migration_revision_scripts=0
```

No Python migration revision exists. The lifecycle harness then ran its initial
read-only `alembic current --verbose` probe, but aborted before step 1 because
the script attempted to assign zsh's reserved read-only `status` variable:

```text
state_probe: read-only variable: status
```

Consequences:

| Lifecycle action | Executed? |
|---|---|
| Initial read-only revision probe | Yes |
| `alembic upgrade head` | No |
| Required `alembic current --verbose` step | No |
| Repeated upgrade/idempotency check | No |
| `alembic downgrade base` | No |
| Final upgrade | No |
| Stamp/manual repair | No |

The failure occurred in the evidence shell before any lifecycle command or
database mutation. No automatic retry or later step was attempted. PostgreSQL
and the approved database remain running and unchanged. A corrected harness
requires separate approval and must use a non-reserved variable such as
`command_exit`.

#### Corrected Alembic lifecycle retry

The single approved retry changed only the harness variable from zsh's reserved
`status` name to `command_exit`. It used the locked UV environment and the
project-local socket for `rightjob_phase16`.

There are zero migration revision scripts, so Alembic `base` and `head` are the
same empty revision state. No probe or lifecycle output contained a `Rev:`
identifier or a `Running upgrade/downgrade ...` revision operation.

| Step | Exact command | Exit | Revision before | Revision after | Result |
|---:|---|---:|---|---|---|
| 1 | `alembic upgrade head` | 0 | base/no revision | head = base/no revision | Created expected Alembic version infrastructure only |
| 2 | `alembic current --verbose` | 0 | head = base/no revision | unchanged | No current revision identifier |
| 3 | `alembic upgrade head` | 0 | head = base/no revision | unchanged | Idempotent no-op |
| 4 | `alembic downgrade base` | 0 | head = base/no revision | base/no revision | Reached base; no revision operation required |
| 5 | `alembic upgrade head` | 0 | base/no revision | head = base/no revision | Returned to head; no revision operation required |

Object-specific lifecycle probes showed:

- before step 1: `public.alembic_version` absent;
- after step 1 and through step 5: `public.alembic_version` present;
- no approved migration script existed to create or remove an application
  object;
- no unexpected revision or revision-driven database object appeared.

The repeated upgrade changed nothing. Downgrade reached `base`, and the final
upgrade returned to `head`, which currently equals `base`. No stamp, generated
migration, manual repair, configuration edit, schema inventory, API, worker, or
shutdown action was performed. PostgreSQL remains running for the next
separately approved verification step.

### Read-only schema inventory

All catalog queries ran inside explicit read-only transactions against only
`rightjob_phase16`. System catalogs, information schema, temporary schemas, and
PostgreSQL internal relations were excluded from the application comparison.

#### Schemas and owners

| Schema | Owner | Classification |
|---|---|---|
| `public` | `pg_database_owner` | Standard database schema; expected |

No other non-system schema exists.

#### Tables, views, indexes, and constraints

| Type | Name | Parent | Owner | Detail |
|---|---|---|---|---|
| Table | `public.alembic_version` | — | `rightjob_phase16_owner` | Expected Alembic infrastructure |
| Index | `public.alembic_version_pkc` | `public.alembic_version` | `rightjob_phase16_owner` | Primary and unique |
| Primary-key constraint | `alembic_version_pkc` | `public.alembic_version` | Table owner: `rightjob_phase16_owner` | `PRIMARY KEY (version_num)` |

No view, materialized view, foreign table, partitioned table, separate unique
constraint, foreign key, or check constraint exists.

#### Extensions

| Extension | Version | Schema | Owner | Classification |
|---|---|---|---|---|
| `plpgsql` | `1.0` | `pg_catalog` | `rightjob_phase16_owner` | PostgreSQL default internal extension |

No application extension is installed. In particular, `pgvector` is absent.

#### Object counts

| Object type | Count |
|---|---:|
| Application tables | 1 |
| Views/materialized views | 0 |
| Indexes | 1 |
| Primary-key constraints | 1 |
| Separate unique constraints | 0 |
| Foreign-key constraints | 0 |
| Check constraints | 0 |
| Unexpected non-system schemas/relations/indexes/constraints/extensions | 0 |

`public.alembic_version` exists, is owned by
`rightjob_phase16_owner`, and contains **0 rows**, consistent with the
zero-revision Phase 1 migration state.

One shell post-processing assertion used an incorrect right join and printed
`alembic_state=417|rightjob_phase16_owner`. That value counted unrelated
`pg_class` rows and is not the Alembic row count. The immediately preceding
direct catalog query correctly and unambiguously returned
`alembic_rows = 0`. No retry or mutation was performed.

**Final inventory result: PASS.** The actual database matches the expected
Phase 1 state. No unexpected schema, table, view, index, constraint, extension,
owner, or application object was found.

### FastAPI database-connectivity verification

The unchanged Phase 1 bootstrap intentionally has no database adapter. Temporary
environment variables enabled database configuration while keeping it optional:

```text
RIGHTJOB_ENVIRONMENT=phase16-local
RIGHTJOB_BUILD_VERSION=phase1.6
RIGHTJOB_DATABASE_ENABLED=true
RIGHTJOB_API_DATABASE_REQUIRED=false
RIGHTJOB_DATABASE_URL=<project-local socket URL; no password>
```

The initialization password had been deleted as required, so changing the role
to enable a TCP client password would have violated this verification scope.
The API configuration and read-only probe therefore used the approved
project-local Unix socket to reach the same server whose verified listener is
`127.0.0.1:55416`. No credential was persisted or logged.

Startup command, with the database URL sanitized:

```text
RIGHTJOB_DATABASE_ENABLED=true \
RIGHTJOB_API_DATABASE_REQUIRED=false \
RIGHTJOB_DATABASE_URL=<sanitized-project-local-url> \
.tooling/uv/0.12.0/uv-x86_64-apple-darwin/uv run uvicorn \
  rightjob_api.main:app --app-dir apps/api/src \
  --host 127.0.0.1 --port 8016
```

API startup completed successfully and logged only service/environment
metadata. Route evidence:

| Route | Status | Sanitized response |
|---|---:|---|
| `/health` | 200 | `{"status":"running"}` |
| `/ready` | 200 | Process ready; database optional and `unavailable`; detail states no Phase 1 database adapter is connected |
| `/version` | 200 | `{"service":"rightjob-api","version":"0.1.0","build":"phase1.6"}` |
| `/not-a-route` | 404 | `{"detail":"Not Found"}` |

Every response included generated request and correlation identifiers. The
captured startup, request, and shutdown logs contained no password, database
URL, token, or sensitive connection detail.

The separate locked-environment Psycopg probe set the connection read-only and
returned:

```text
database=rightjob_phase16
role=rightjob_phase16_owner
listen_addresses=127.0.0.1
port=55416
data_directory=<approved project-local cluster>
in_recovery=false
```

This proves basic client connectivity, but does not claim that the API itself
has a database adapter. `/ready` behaved exactly as its Phase 1 contract
specifies: an enabled optional database is reported unavailable without making
overall readiness fail. No code or readiness contract was changed.

Ctrl-C initiated graceful Uvicorn shutdown. The API logged `api.stopped`,
completed application shutdown, and exited normally. PostgreSQL remains running
for the separately approved worker and final shutdown steps.

### Locked-environment worker verification

The unchanged worker ran through the locked UV/Python environment:

```text
/Users/rightjobsolutions/Projects/AI Agent/.tooling/uv/0.12.0/
uv-x86_64-apple-darwin/uv run python -m rightjob_worker.main
```

Startup evidence:

```json
{"message":"worker.started","worker_id":"worker-local","workflow_engine":"disabled","workflow_enabled":false}
```

The worker remained alive and idle for a two-second observation interval. A
process-scoped `lsof` inspection found zero network sockets. Therefore the
worker did not connect to PostgreSQL, an external provider, or any Tool
Interface, and no workflow execution or external effect began.

SIGTERM was sent to the worker process. Shutdown evidence:

```json
{"message":"worker.stopped","worker_id":"worker-local"}
```

The worker exited with status 0. Logs contained no database URL, credential,
token, provider detail, or sensitive connection value. A post-worker read-only
query confirmed that the only Phase 1 table, `public.alembic_version`, still
contains zero rows. With no other application table present, no worker database
write occurred.

No source, configuration, migration, database object, task, workflow, API
process, or external effect was created or changed. PostgreSQL remains running
for separately approved shutdown verification.

### Final PostgreSQL shutdown verification

The verified cluster was stopped with the project-local runtime:

```text
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/pg_ctl \
  -D .tooling/postgresql/data/phase16-pg17 \
  -m fast -w stop
```

`fast` mode was appropriate for the isolated verification cluster: it
terminated active sessions, performed a shutdown checkpoint, and waited for
complete server termination.

| Check | Result |
|---|---|
| `pg_ctl` exit | 0; `server stopped` |
| `pg_isready -h 127.0.0.1 -p 55416` | Exit 2; no response |
| `postmaster.pid` | Absent |
| Project-local socket entries | 0; socket removed |
| TCP listener on 55416 | Absent |
| PostgreSQL/Postgres.app processes | 0 |
| Shutdown log | Fast-shutdown request, transaction abort, shutdown checkpoint, `database system is shut down` |

No runtime, database, migration, data, log, DMG, UV, Python, or other artifact
was removed or altered by the shutdown verification. PostgreSQL was not
restarted.

Final retained disk usage:

| Retained item | Allocated size |
|---|---:|
| PostgreSQL 17 runtime | 388,924 KiB |
| Initialized cluster, including `rightjob_phase16` | 47,796 KiB |
| Socket directory after shutdown | 0 KiB |
| Verified DMG | 573,964 KiB; 583,520,231 logical bytes |
| PostgreSQL log | 4 KiB; 3,955 logical bytes |
| Complete `.tooling/postgresql` tree | 1,010,688 KiB |

**Final shutdown inventory: PASS.** No listener, socket, PID file, or orphan
process remains.

### Approved isolated PostgreSQL runtime plan and cleanup reference

The approved runtime copy is the PostgreSQL 17 directory only, not the 1.9-GiB
multi-version application:

```text
source:
/Volumes/Postgres-2.9.2-13-14-15-16-17-18/Postgres.app/Contents/Versions/17

destination:
.tooling/postgresql/runtime/postgresapp-2.9.2/17
```

The exact binaries used would be:

```text
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/initdb
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/postgres
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/pg_ctl
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/pg_isready
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/psql
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/createdb
.tooling/postgresql/runtime/postgresapp-2.9.2/17/bin/dropdb
```

Proposed isolation:

- data: `.tooling/postgresql/data/phase16-pg17`;
- Unix socket: `.tooling/postgresql/socket`;
- log: `.tooling/postgresql/phase16-postgres.log`;
- TCP: `127.0.0.1:55416` only;
- superuser/owner role: `rightjob_phase16_owner`;
- database: `rightjob_phase16`;
- authentication: local socket trust for the current OS account; TCP
  `scram-sha-256` with a temporary, uncommitted credential;
- no launch daemon, login item, shell profile, global PATH, or persistent
  service.

Proposed lifecycle commands use explicit project-local paths. The password file
would be created with owner-only access and removed immediately after
initialization:

```text
PGROOT=".tooling/postgresql/runtime/postgresapp-2.9.2/17"
PGDATA=".tooling/postgresql/data/phase16-pg17"
PGSOCKET=".tooling/postgresql/socket"

"$PGROOT/bin/initdb" \
  -D "$PGDATA" \
  -U rightjob_phase16_owner \
  --encoding=UTF8 \
  --locale=C \
  --auth-local=trust \
  --auth-host=scram-sha-256 \
  --pwfile="<owner-only temporary password file>"

"$PGROOT/bin/pg_ctl" -D "$PGDATA" \
  -l ".tooling/postgresql/phase16-postgres.log" \
  -o "-h 127.0.0.1 -p 55416 -k $PGSOCKET" start

"$PGROOT/bin/pg_isready" \
  -h 127.0.0.1 -p 55416 -d postgres -U rightjob_phase16_owner

"$PGROOT/bin/createdb" \
  -h 127.0.0.1 -p 55416 \
  -U rightjob_phase16_owner \
  -O rightjob_phase16_owner rightjob_phase16
```

Proposed migration validation:

```text
RIGHTJOB_DATABASE_URL="<temporary local URL>" uv run alembic upgrade head
RIGHTJOB_DATABASE_URL="<temporary local URL>" uv run alembic current --verbose
RIGHTJOB_DATABASE_URL="<temporary local URL>" uv run alembic upgrade head
RIGHTJOB_DATABASE_URL="<temporary local URL>" uv run alembic downgrade base
RIGHTJOB_DATABASE_URL="<temporary local URL>" uv run alembic upgrade head

"$PGROOT/bin/psql" "<temporary local URL>" \
  -c "SELECT n.nspname, c.relname, c.relkind
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
      ORDER BY 1, 2;"
```

Phase 1 has no production migration revision, so the expected application schema
is empty except for Alembic's own version infrastructure if Alembic creates it.
Rollback is expected to be a supported no-op to `base`; this must be verified,
not assumed.

Proposed shutdown:

```text
"$PGROOT/bin/pg_ctl" -D "$PGDATA" -m fast stop
"$PGROOT/bin/pg_isready" -h 127.0.0.1 -p 55416
```

The final readiness check should report no response after shutdown. Cleanup
would target only these explicit project-local paths:

```text
rm -r ".tooling/postgresql/data/phase16-pg17"
rm -r ".tooling/postgresql/socket"
rm ".tooling/postgresql/phase16-postgres.log"
rm -r ".tooling/postgresql/runtime/postgresapp-2.9.2"
rm ".tooling/postgresql/artifacts/Postgres-2.9.2-13-14-15-16-17-18.dmg"
```

Originally expected disk use:

- retained DMG: 556.5 MiB;
- measured PostgreSQL 17 runtime: 383.3 MiB;
- initial cluster/logs: reserve 100 MiB pending measurement;
- working total: approximately 1.02 GiB, or approximately 483 MiB after deleting
  the DMG.

The execution evidence above supersedes this original proposal and records the
required path-quoting and client-option corrections. Runtime copy,
initialization, startup, database creation, Alembic lifecycle, API/worker
verification, and shutdown were executed successfully. Cleanup commands remain
unapproved and were not executed.

## Files changed

| File/category | Classification |
|---|---|
| `uv.lock` | Real generated dependency lock |
| `Makefile` | Bootstrap correction: install all Python workspace packages |
| `.gitignore` | Environment configuration: ignore project-local generated tooling |
| `pyproject.toml` | Tooling boundary: exclude generated `.tooling` content from Ruff |
| `scripts/check_secrets.py` | Tooling boundary: skip generated local runtimes/caches |
| `scripts/check_phase1_scope.py` | Tooling boundary: do not inspect generated third-party manifests |
| `services/worker/src/rightjob_worker/main.py` | Lint-safe equivalent signal-handler guard |
| 33 existing Python bootstrap files | Ruff-only formatting/import normalization |
| `docs/implementation/016-python-database-toolchain-verification-report.md` | Evidence report |
| `.tooling/postgresql/runtime/postgresapp-2.9.2/17/` | Approved ignored local PostgreSQL runtime copy |
| `.tooling/postgresql/data/phase16-pg17/` | Approved ignored isolated PostgreSQL cluster and verification database |
| `.tooling/postgresql/phase16-postgres.log` | Approved ignored local runtime log |
| `.tooling/postgresql/artifacts/Postgres-2.9.2-13-14-15-16-17-18.dmg` | Verified retained artifact |

Generated `.tooling/`, `.venv/`, `dist/`, caches, and build output are ignored
local artifacts. No application business behavior was added.

## Checks passed and failed

### Passed

- Project-local UV and Python verification
- Real lock generation, lock check, stable repeat resolution
- Locked and frozen installation
- Formatting, lint, strict typing, source compilation
- Unit, integration, architecture, and scope tests
- Migration-safety and secret checks
- Python package builds
- FastAPI startup, allowed routes, 404 behavior, and shutdown
- Worker startup, idle behavior, SIGTERM shutdown
- Full repository `make ci`
- PostgreSQL artifact signature, architecture, and compatibility inspection
- Project-local PostgreSQL runtime copy and isolated cluster initialization
- PostgreSQL 17.7 startup, binding, process-path, and readiness verification
- Database creation, ownership, encoding, locale, and connection-limit verification
- Alembic upgrade/current/idempotency/downgrade/re-upgrade lifecycle
- Read-only Phase 1 schema inventory
- FastAPI bootstrap and separate read-only PostgreSQL connectivity probe
- Locked-environment idle worker verification with zero network sockets
- Clean PostgreSQL shutdown and orphan-process verification

### Not passed

None within the approved Phase 1.6 scope.

## Security conditions

- Existing npm audit findings remain as documented in the Phase 1.5 report.
- No PostCSS or Sharp override was added.
- `npm audit fix --force` was not used.
- Next.js remains 15.5.22; ESLint remains major 9.
- Clerk, Temporal, `pgvector`, Redis, and provider integrations remain absent.
- No production/shared database or credential was used.
- Runtime security, RLS, and scale have not been claimed as proven.

## Remaining conditions and deferred proof gates

1. Tenant isolation remains static scaffolding because Phase 1 contains no
   tenant-owned production tables.
2. The existing Next.js transitive PostCSS/Sharp security condition remains
   unchanged.
3. The Starlette TestClient deprecation warning should be revisited through a
   normal compatible dependency update, not a forced major migration.
4. Cleanup remains unapproved. The verified runtime, data, log, and DMG are
   retained under `.tooling/postgresql/`.

These are documented deferred or pre-existing conditions. They do not represent
a failed Python/PostgreSQL toolchain verification. Runtime security, tenant RLS,
production scale, and production deployment have not been claimed as proven.

## Final verdict

`PHASE 1 CONDITIONS CLEARED`

The Phase 1 Python, UV locking, FastAPI, worker, real PostgreSQL runtime,
database, migration lifecycle, schema inventory, and clean-shutdown conditions
are cleared. This verdict does not authorize cleanup, modify any accepted
architecture decision, prove production security or scale, or begin Phase 2.
