# Phase 2.5 Durable Workflow Engine Proof Report

**Verification date:** 2026-08-07  
**Host:** macOS 10.15.8, Intel x86_64  
**Scope:** Synthetic Temporal proof; subsequent adoption recorded 2026-08-11

## 1. Environment

Phase 2.5 used the ADR-001 localhost development exception. The API and
Rightjob PostgreSQL database were not started or modified. Temporal ran as one
headless process bound to `127.0.0.1:7233` with isolated SQLite persistence at:

`/private/tmp/rightjob-temporal-phase25.ZkBY0R/temporal.sqlite`

The original SQLite evidence was 630,784 bytes (656 KiB allocated). It was
retained through root-cause review and final report reconciliation, then removed
under the approved cleanup plan.

## 2. Dependency changes

- Worker dependency: `temporalio==1.30.0`.
- Lockfile: `uv.lock` updated; the selected Intel macOS wheel supports macOS
  10.12+ and has SHA-256
  `6773a6b708dee7675fcbb681bf28e48337ce43b8467ceba8f903e78ae68909f8`.
- Temporal SDK license: MIT.
- Temporal CLI/server license: MIT (official archive `LICENSE` retained).
- Dependency integrity, lock verification, source security scan, and license
  inspection passed during the source-only gate.
- No API, Identity, Repository, or database dependency was changed.

## 3. Engine abstraction

`DurableWorkflowEngine` is a provider-neutral application contract supporting
start, status, signal, cancel, and result. Its context carries `workspace_id`,
`correlation_id`, logical operation ID, workflow type, and workflow version.
Temporal types do not appear in the core contract.

## 4. Temporal adapter

`TemporalWorkflowEngine` exists only under worker infrastructure. It maps the
neutral contract to Temporal, creates deterministic SHA-256-derived canonical
workflow IDs, uses `WorkflowIDConflictPolicy.FAIL`, and rejects a mismatched
Workspace before obtaining a Temporal handle. Temporal is execution
infrastructure; it does not own authorization, Policy, canonical business data,
or business behavior.

## 5. Proof workflows

Only these synthetic workflows were registered:

- `proof.durable-counter`
- `proof.retry`
- `proof.approval`
- `proof.cancellation`
- `proof.timeout`
- `proof.idempotent-effect`
- `proof.unknown-outcome`
- `proof.versioned`

The only simulated external effect used a temporary SQLite idempotency ledger.
No real provider was called.

## 6. Files changed

Created:

- `packages/core/src/rightjob/orchestration/__init__.py`
- `packages/core/src/rightjob/orchestration/engine.py`
- `services/worker/src/rightjob_worker/proof_activities.py`
- `services/worker/src/rightjob_worker/proof_workflows.py`
- `services/worker/src/rightjob_worker/temporal_adapter.py`
- `services/worker/src/rightjob_worker/temporal_runtime.py`
- `tests/unit/test_workflow_engine.py`
- `tests/integration/test_temporal_proof.py`
- `docs/implementation/025-durable-workflow-engine-proof-report.md`

Modified:

- `docs/decisions/adrs/ADR-001-deployment-and-technology-baseline.md`
- `docs/implementation/phase-status.md`
- `services/worker/src/rightjob_worker/main.py`
- `services/worker/pyproject.toml`
- `scripts/check_phase1_scope.py`
- `tests/architecture/test_boundaries.py`
- `uv.lock`

The workspace does not contain Git metadata, so this inventory is based on the
approved implementation record and Phase 2.5 source locations rather than a Git
diff.

## 7. Test and quality results

The source gates passed before runtime verification and the complete quality
suite passed again after the corrected runtime proof:

- Ruff format: passed.
- Ruff lint: passed.
- strict mypy: passed.
- pytest: 67 passed, 18 skipped (runtime-gated tests skipped).
- architecture checks: passed.
- phase scope: passed.
- migration safety: passed; no migration was created or run.
- secret hygiene: passed.
- Python compilation: passed.
- UV lock verification: passed.

No gate was weakened. The corrected runtime proof passed separately in 2.97
seconds, and the final environment-independent suite completed with 67 passed
and 18 explicitly environment-gated skips.

## 8. Runtime artifact and startup evidence

Candidate A was the official Temporal CLI v1.1.0 Darwin AMD64 archive:

- Archive: `temporal_cli_1.1.0_darwin_amd64.tar.gz`
- Size: 27,533,722 bytes
- SHA-256: `61d56429c8f71fab9975624d32b1747f1370e6b68e6ea861d2f7c7296187b2d0`
- Installed output: `temporal version 1.1.0 (Server 1.25.0, UI 2.30.3)`
- Actual extracted footprint: 116,448 KiB

The earlier checksum-valid but Catalina-incompatible CLI v1.8.2 occupied
179,992 KiB. Its approved archive checksum was
`489d7f5420cae02b559774ac23df035141954c33a51dba96f5759a0ddccdf1b6`.
It was removed only after replacement verification and evidence reconciliation.

The server logged a frontend listener at exactly `127.0.0.1:7233` and SQLite
visibility/persistence at the isolated temporary path. Headless mode prevented
the UI listener.

## 9. Mandatory SDK/server capability preflight

No application workflow was created before this gate passed. Python SDK 1.30.0
connected successfully, `GetSystemInfo` succeeded, and
`DescribeNamespace(default)` returned registered state `1`.

- Server version: `1.25.0`
- Namespace: `default`
- SDK/server connection: successful
- Advertised capabilities: `activity_failure_include_heartbeat`,
  `build_id_based_versioning`, `count_group_by_execution_status`,
  `eager_workflow_start`, `encoded_failure_attributes`,
  `internal_error_differentiation`, `sdk_metadata`,
  `signal_and_query_header`, `supports_schedules`, and `upsert_memo`

The required baseline RPCs and capabilities for the synthetic proof were
available. No incompatibility was observed at this gate.

## 10. Runtime proof results

Command:

`RIGHTJOB_TEMPORAL_TEST_TARGET=127.0.0.1:7233 ... pytest tests/integration/test_temporal_proof.py -x -vv`

Initial result: **1 failed in 18.43 seconds**. Execution stopped at the first
failure.

Proof assertions completed before the failure:

- Durable worker restart recovery: passed. State was `count=1` while waiting,
  survived complete worker termination, resumed on a replacement worker, and
  completed with `count=2`.
- Bounded successful retry: passed on attempt 3 after two synthetic failures.
- Exhausted retry: passed; maximum attempts 2 produced a failed workflow.
- Approval wait/resume and duplicate signal suppression: passed; two approval
  signals produced one accepted transition.
- Cancellation: passed with deterministic `CANCELLED` status.
- Activity timeout: passed with `timed_out` result and maximum attempts 1.
- Idempotent fake effect: passed; two executions retained one logical effect.
- Unknown outcome: passed; one effect was retained as `unknown` and the workflow
  entered `reconciliation_required` without blind retry.
- Workspace isolation: passed; Workspace B status access was rejected before a
  Temporal call.
- Correlation propagation: passed for the durable restart result
  (`phase25-restart-counter`) and was carried in workflow/activity inputs.
- Versioning and replay: passed; a v1 history replayed through the patched v2
  implementation with no replay failure.

Original proof-harness defect:

- Two-worker task-queue processing: **failed before either worker context was
  started and before its four workflows were created**. Constructing the second
  `Worker` on the same Python SDK runtime, namespace, task queue, task types, and
  unversioned Build ID raised:

  `Registration of multiple workers with overlapping worker task types on the same namespace, task queue, and deployment build ID not allowed`

This was a Python SDK Core in-process registration constraint, not a Temporal
Server rejection. The production architecture calls for separate worker
processes, but the original harness accidentally used two workers in one SDK
runtime. It was classified as
`PHASE 2.5 PROOF-HARNESS DEFECT — TEMPORAL CAPABILITY NOT YET FAILED`.

Corrected proof command:

`RIGHTJOB_TEMPORAL_TEST_TARGET=127.0.0.1:7233 ... pytest tests/integration/test_temporal_proof.py::test_phase25_temporal_multiprocess_proof -x -vv`

Corrected result: **1 passed in 2.97 seconds**.

The correction changed only the integration test and this report. Worker A PID
18209 and Worker B PID 18210 ran as independent Python interpreter processes,
with independent SDK Core runtimes, on task queue
`rightjob-phase25-proof-multiprocess`. Temporal `DescribeTaskQueue` returned
both poller identities. Actual `WorkflowTaskStarted` history attributed at least
one completed task to each PID; process existence alone was not treated as
execution evidence.

Exactly five unique synthetic executions completed:

- `rj-proof.versioned-2d0573517c81c46fde6f88be`
- `rj-proof.versioned-8e1e74f9862f5e1df77b8d22`
- `rj-proof.versioned-c4965e5f189339913dad3ad0`
- `rj-proof.versioned-d8e1012741d00208d4f73ba3`
- `rj-proof.versioned-f50560c5e125b4a28c865c2f`

They corresponded to two initial executions, one survivor execution after
Worker A stopped, and two executions after Worker A restarted as PID 18211.
Worker B remained alive and processed the survivor execution. After restart,
poller discovery and workflow history again attributed work to both Worker B and
the new Worker A process. Every returned result preserved its expected
Workspace ID and correlation ID. The harness asserted that all canonical IDs
were disjoint and started once. This corrected proof scheduled no external
effect Activity, so it could not duplicate the synthetic effect ledger.

## 11. Restart recovery evidence

The API process was not involved. A worker subprocess started, processed the
counter to its wait state, received SIGTERM, and exited cleanly. Temporal
reported the workflow still running. A separate replacement worker subprocess
then resumed and completed the exact workflow. Both `worker.started` and
`worker.stopped` records were asserted.

## 12. Approval, cancellation, timeout, and retry evidence

Approval state was durable in workflow history and duplicate signals were
suppressed by workflow state. Cancellation produced a cancelled terminal state.
The long-running synthetic activity exceeded its 0.1-second start-to-close
timeout and the workflow handled the timeout without retry. Retry policies were
bounded and used a fixed 100 ms interval in the successful and exhausted cases.

## 13. Idempotency and unknown-outcome evidence

The fake adapter used `idempotency_key` as a SQLite primary key. Repeating
`phase25-effect-1` returned `effect_count=1`. The simulated lost-response case
stored one `unknown` outcome for `phase25-effect-unknown`; later execution read
that same outcome, and the workflow required reconciliation.

## 14. Versioning and replay evidence

An unpatched v1 execution completed and its real history was fetched. Temporal
SDK `Replayer` replayed that history against the v2 implementation using
`workflow.patched("phase25-version-2")`; `replay_failure` was `None`.

## 15. Observability evidence

Workflow and activity records contain correlation ID, Workspace ID, workflow ID,
and activity attempt where applicable. Recorded states include approval wait and
resume, retry, timeout, external-effect outcome, and reconciliation requirement.
No secrets, production credentials, database URLs, or real-provider data were
used. Full centralized audit persistence remains deferred.

## 16. Worker/API separation

The restart and corrected multi-worker proofs used
`python -m rightjob_worker.main` subprocesses and no API process. Worker start,
SIGTERM, stop, replacement, and concurrent polling were independent of the API.
The corrected proof demonstrated two simultaneously active worker processes,
continued processing after Worker A stopped, and safe polling after Worker A
restarted.

## 17. PostgreSQL fallback comparison

Temporal demonstrated materially stronger built-in workflow history, durable
waits, signaling, bounded retries, cancellation, timeout semantics, and replay
tooling than a custom PostgreSQL job loop. A PostgreSQL fallback would reduce
operational dependencies and vendor coupling but would require Rightjob to
implement leases, timers, signals, replay/versioning discipline, retry state,
and uncertain-outcome recovery. Temporal passed the complete bounded proof
surface; adoption nevertheless remains an owner decision.

## 18. Operational complexity

Local proof setup required a version-pinned CLI, checksum verification, an
isolated server process, SQLite lifecycle management, separate workers, and
compatibility checks. The current host cannot execute CLI v1.8.2, requiring the
older CLI v1.1.0/server 1.25.0 combination. Production remains Managed Temporal
under ADR-001; localhost behavior is not a production dependency.

## 19. Security considerations

- Listener restricted to localhost.
- No production credentials or real external effects.
- Rightjob Workspace checks remain outside Temporal.
- Temporal types remain inside worker infrastructure.
- No Rightjob PostgreSQL schema or data was touched.
- Deterministic workflow IDs prevent accidental duplicate starts.
- Retained SQLite contains synthetic proof history only.

## 20. Shutdown, cleanup, and limitations

SIGINT produced `Stopping server...`; Temporal drained services and exited with
code 0. `lsof` found no listener on port 7233, and the host process inventory
found no Temporal server, proof worker, or orphan child process.

Evidence retained through report reconciliation and then removed exactly under
the approved cleanup plan:

- `.tooling/temporal/1.8.2/`
- `/private/tmp/rightjob-temporal-phase25.ZkBY0R/temporal.sqlite`
- `/private/var/folders/s0/dky2jwvd7tj41663125ht5jc0000gn/T/pytest-of-rightjobsolutions/pytest-4/test_phase25_temporal_proof0/effects.sqlite3`
- `/private/tmp/rightjob-temporal-phase25-corrected.vi4T0H/temporal.sqlite`
- `/private/var/folders/s0/dky2jwvd7tj41663125ht5jc0000gn/T/pytest-of-rightjobsolutions/pytest-5/test_phase25_temporal_multipro0/effects.sqlite3`

The corrected SQLite evidence is 573,440 bytes and its fake-effect ledger is
12,288 bytes. SIGTERM assertions proved all three corrected-proof worker
processes exited with code zero. The server then drained and exited with code
zero. `lsof` and the host process inventory proved no listener, Temporal server,
Worker A, Worker B, or orphan child remained.

Post-cleanup checks proved both temporary state directories, both exact ledger
files, and `.tooling/temporal/1.8.2/` were absent. The compatible approved CLI
v1.1.0 remains at `.tooling/temporal/1.1.0/`; it was not included in the deletion
scope.

Limitations include use of an older local server, no Managed Temporal namespace
proof, no production load/failover or security test, no persisted audit
integration, operational and vendor-lock-in costs, and no proof of migrating
active history between engines.

## 21. Recommendation

**A. TEMPORAL PROOF PASSED — RECOMMEND ADOPTION**

Temporal demonstrated the required durability, restart recovery, bounded retry,
durable approval, cancellation, timeout, idempotency, unknown-outcome
reconciliation, deterministic versioning/replay, Workspace scoping, correlation
propagation, API/worker separation, and safe independent multi-worker polling.
This recommendation is evidence for an owner decision; it does not itself adopt
Temporal or change ADR-001's Managed Temporal production requirement.

## 22. Subsequent owner decision

On 2026-08-11 the owner accepted the completed Phase 2.5 evidence and adopted
Managed Temporal as the approved Durable Workflow Engine for Rightjob AI OS.
The provider-neutral boundary and all ownership restrictions remain in force.

## Final phase verdict

**PHASE 2.5 DURABLE WORKFLOW ENGINE PROOF PASSED**
