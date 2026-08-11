import pytest
from rightjob_worker.main import run


@pytest.mark.asyncio
async def test_worker_starts_and_stops_once() -> None:
    await run(once=True)
