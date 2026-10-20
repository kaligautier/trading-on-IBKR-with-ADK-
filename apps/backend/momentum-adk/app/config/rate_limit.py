"""Share the virtual key's request allowance across all worker model roles."""

import asyncio
import time
from contextlib import asynccontextmanager


class ModelRequestGate:
    def __init__(self, concurrency=2, minimum_interval=6.5):
        self._slots = asyncio.Semaphore(concurrency)
        self._starts = asyncio.Lock()
        self._interval = minimum_interval
        self._last_start = float("-inf")

    @asynccontextmanager
    async def acquire(self):
        async with self._slots:
            async with self._starts:
                delay = self._interval - (time.monotonic() - self._last_start)
                if delay > 0:
                    await asyncio.sleep(delay)
                self._last_start = time.monotonic()
            yield
