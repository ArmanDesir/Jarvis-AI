"""Small shutdown primitive shared by long-running processes."""

from __future__ import annotations

import asyncio


class Shutdown:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def request(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()
