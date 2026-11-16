"""ProcessPool: the bounded pool that classifies and answers, apart from the ack's threads."""

import logging
import threading
import time

from dmr_incoming_service.process_pool import ProcessPool


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def messages(caplog, text):
    return [r.getMessage() for r in caplog.records if text in r.getMessage()]


def test_jobs_run_on_the_pools_own_threads():
    pool = ProcessPool(workers=2, warn_at=10)
    names = []
    done = threading.Event()

    def job(value):
        names.append((threading.current_thread().name, value))
        done.set()

    try:
        assert pool.submit(job, "x") is True
        assert done.wait(5)
        wait_until(lambda: pool.pending == 0)
    finally:
        pool.shutdown()
    assert names[0][0].startswith("dmr-process")
    assert names[0][1] == "x"


def test_submit_after_shutdown_is_refused():
    pool = ProcessPool(workers=1, warn_at=10)
    pool.shutdown()

    assert pool.submit(print) is False
    assert pool.pending == 0


def test_backlog_is_logged_once_and_again_when_cleared(caplog):
    caplog.set_level(logging.INFO, logger="dmr_incoming_service")
    pool = ProcessPool(workers=1, warn_at=4)
    gate = threading.Event()
    try:
        for _ in range(6):
            assert pool.submit(gate.wait)
        assert pool.pending == 6
        warnings = messages(caplog, "backlog:")
        assert len(warnings) == 1
        assert "4 messages waiting or in progress (1 workers)" in warnings[0]
        assert messages(caplog, "backlog cleared") == []
    finally:
        gate.set()
    wait_until(lambda: pool.pending == 0)
    pool.shutdown()

    assert len(messages(caplog, "backlog cleared")) == 1
    assert len(messages(caplog, "backlog:")) == 1


def test_shutdown_drops_queued_jobs_and_stops_counting_them():
    pool = ProcessPool(workers=1, warn_at=100)
    started = threading.Event()
    gate = threading.Event()
    ran = []

    def blocking():
        started.set()
        gate.wait(5)

    assert pool.submit(blocking)
    assert started.wait(5)
    for i in range(3):
        assert pool.submit(ran.append, i)
    assert pool.pending == 4

    pool.shutdown()
    gate.set()
    wait_until(lambda: pool.pending == 0)

    assert ran == []
