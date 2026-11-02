"""Run CPU-heavy image jobs off the event loop, a bounded number at a time.

Model inference takes from about a second (background removal) to minutes (8x
upscaling) on a CPU. Running it inside an ``async def`` handler would freeze the
whole server, file serving and ``/health`` included, for that long. Each job
therefore runs in a worker thread, and a semaphore caps how many run at once;
a request that cannot get a slot within the queue timeout gets a 503 with
``Retry-After`` instead of piling up.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional, TypeVar

from starlette.concurrency import run_in_threadpool

T = TypeVar("T")


class ServerBusyError(Exception):
    def __init__(self, retry_after_s: int):
        super().__init__("All processing slots are busy")
        self.retry_after_s = retry_after_s


class JobLimiter:
    def __init__(self, max_concurrent: int, queue_timeout_s: float):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        # A threading semaphore (not asyncio) so it is not tied to one event loop.
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.queue_timeout_s = queue_timeout_s

    def _run_with_slot(self, fn: Callable[..., T], *args, **kwargs) -> T:
        if not self._slots.acquire(timeout=self.queue_timeout_s):
            raise ServerBusyError(retry_after_s=max(1, int(self.queue_timeout_s)))
        try:
            return fn(*args, **kwargs)
        finally:
            self._slots.release()

    async def run(self, fn: Callable[..., T], *args, **kwargs) -> T:
        return await run_in_threadpool(self._run_with_slot, fn, *args, **kwargs)


_limiter: Optional[JobLimiter] = None
_limiter_lock = threading.Lock()


def get_job_limiter() -> JobLimiter:
    global _limiter  # noqa: PLW0603 - process-wide singleton built from settings on first use
    with _limiter_lock:
        if _limiter is None:
            from config import get_settings

            settings = get_settings()
            _limiter = JobLimiter(settings.max_concurrent_jobs, settings.job_queue_timeout_s)
        return _limiter
