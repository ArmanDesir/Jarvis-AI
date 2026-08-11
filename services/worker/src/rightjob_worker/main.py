"""Worker lifecycle with an isolated Phase 2.5 Temporal proof adapter."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from contextlib import suppress

from rightjob.shared.config import Settings
from rightjob.shared.lifecycle import Shutdown
from rightjob.shared.logging import configure_logging

from rightjob_worker.temporal_runtime import TemporalSettings, run_temporal_worker


async def run(*, once: bool = False) -> None:
    settings = Settings.load()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    shutdown = Shutdown()
    loop = asyncio.get_running_loop()

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal_name, shutdown.request)

    logger.info(
        "worker.started",
        extra={
            "worker_id": settings.worker.worker_id,
            "workflow_engine": settings.workflow.adapter,
            "workflow_enabled": settings.workflow.enabled,
        },
    )
    if once:
        shutdown.request()
    if settings.workflow.enabled and settings.workflow.adapter == "temporal":
        await run_temporal_worker(shutdown.wait, TemporalSettings.load())
    else:
        await shutdown.wait()
    logger.info("worker.stopped", extra={"worker_id": settings.worker.worker_id})


def main() -> None:
    parser = argparse.ArgumentParser(description="Rightjob idle worker")
    parser.add_argument("--once", action="store_true", help="start and stop for verification")
    args = parser.parse_args()
    asyncio.run(run(once=args.once))


if __name__ == "__main__":
    main()
