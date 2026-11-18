"""The bounded thread pool that classifies and answers accepted messages, apart from the ack.
The ack runs on Starlette's shared thread pool. If classifying ran there too, slow classifications
could take every thread and delay the ack past DMR's 2 s, and DMR would redeliver.
"""

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

logger = logging.getLogger("dmr_incoming_service")


class ProcessPool:
    """Runs jobs on `workers` threads; the rest wait in an in-memory queue.
    Counts the jobs not finished yet (waiting or running). Logs a WARNING when the count reaches
    warn_at, and an INFO when it is back to half of that, so a backlog is visible but not logged
    on every message.
    """

    def __init__(self, workers: int, warn_at: int):
        self.workers = max(1, workers)
        self.warn_at = max(1, warn_at)
        self._executor = ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix="dmr-process"
        )
        self._lock = threading.Lock()
        self._pending = 0
        self._backlogged = False

    @property
    def pending(self) -> int:
        with self._lock:
            return self._pending

    def submit(self, fn, *args) -> bool:
        """Queues fn(*args). False when the pool is shut down and the job was not queued."""
        with self._lock:
            self._pending += 1
        try:
            future = self._executor.submit(fn, *args)
        except RuntimeError:  # shut down, or the interpreter is exiting
            self._finished(None)
            return False
        with self._lock:
            pending = self._pending
            warn = pending >= self.warn_at and not self._backlogged
            if warn:
                self._backlogged = True
        if warn:
            logger.warning(
                "DMR process pool backlog: %d messages waiting or in progress (%d workers)",
                pending,
                self.workers,
            )
        # Also runs for a job cancelled at shutdown
        future.add_done_callback(self._finished)
        return True

    def _finished(self, _future: Future | None) -> None:
        with self._lock:
            self._pending -= 1
            pending = self._pending
            cleared = self._backlogged and pending <= self.warn_at // 2
            if cleared:
                self._backlogged = False
        if cleared:
            logger.info(
                "DMR process pool backlog cleared: %d messages waiting or in progress",
                pending,
            )

    def shutdown(self) -> None:
        """Stops taking jobs and drops the queued ones; running ones finish (or die with the
        process). A dropped job's row stays RECEIVED, and the sweeper answers it after a restart.
        """
        self._executor.shutdown(wait=False, cancel_futures=True)
