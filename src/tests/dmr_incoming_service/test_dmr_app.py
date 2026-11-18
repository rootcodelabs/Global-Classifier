"""app.py: the ack, the hand-off to the process pool, and the pool's life with the app's lifespan.
Driven over raw ASGI, so no HTTP client library is needed.
"""

import asyncio
import json
import logging
import threading
import time

import pytest

from dmr_incoming_service import app as app_module
from dmr_incoming_service import settings
from dmr_test_helpers import RESPONSE_ID, make_envelope

APP = app_module.app


@pytest.fixture
def app_processor(processor, monkeypatch):
    """The app's processor replaced with the one on fake clients. Records the thread process() ran on."""
    threads = []
    process = processor.process

    def spy(job):
        threads.append(threading.current_thread().name)
        process(job)

    monkeypatch.setattr(processor, "process", spy)
    monkeypatch.setattr(app_module, "processor", processor)
    processor.threads = threads
    return processor


async def call(method, path, body=b""):
    """One request to the app over ASGI. Returns (status, JSON body)."""
    incoming = [{"type": "http.request", "body": body, "more_body": False}]
    sent = []

    async def receive():
        return incoming.pop(0) if incoming else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    await APP(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    content = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return start["status"], json.loads(content)


async def post_message(envelope):
    return await call("POST", "/dmr/incoming", json.dumps(envelope).encode())


async def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def ack_and_process():
    """Starts the app, posts one message, waits for it to be processed, stops the app."""
    async with app_module.lifespan(APP):
        status, body = await post_message(make_envelope())
        pool = APP.state.process_pool
        await wait_until(lambda: pool.pending == 0)
    return status, body


def test_message_is_acked_then_processed_on_the_process_pool(app_processor, agent):
    status, body = asyncio.run(ack_and_process())

    assert (status, body["status"]) == (200, "accepted")
    assert len(agent.sent) == 1
    assert len(app_processor.threads) == 1
    assert app_processor.threads[0].startswith("dmr-process")


def test_app_can_start_again_in_the_same_process(app_processor, agent):
    # The pool is created per lifespan: a pool shut down by the first stop must not be reused
    first = asyncio.run(ack_and_process())
    second = asyncio.run(ack_and_process())

    assert first[0] == second[0] == 200
    assert len(agent.sent) == 2


def test_message_after_the_pool_stopped_is_not_acked_and_can_resume(
    app_processor, resql, agent
):
    envelope = make_envelope()

    async def scenario():
        async with app_module.lifespan(APP):
            APP.state.process_pool.shutdown()  # as during shutdown
            return await post_message(envelope)

    status, body = asyncio.run(scenario())

    # No ack, so DMR redelivers; nothing was processed or sent
    assert (status, body["status"]) == (503, "error")
    assert app_processor.threads == []
    assert agent.sent == []
    # The claim is released, so the redelivery (which hits the dedupe) resumes the message
    assert app_processor._in_flight == set()
    resql.answers["insert-dmr-incoming-message"] = []
    resql.answers["get-dmr-incoming-message"] = [
        {"status": "RECEIVED", "responseMessageId": RESPONSE_ID}
    ]
    _, redelivered, job = app_processor.accept(envelope)
    assert redelivered["status"] == "accepted" and job is not None


NO_LIMIT_WARNING = "the queue-wait limit is off"


def start_and_stop_the_app():
    async def scenario():
        async with app_module.lifespan(APP):
            pass

    asyncio.run(scenario())


def test_startup_warns_when_the_queue_wait_limit_is_off(monkeypatch, caplog):
    monkeypatch.setattr(settings, "MAX_QUEUE_WAIT_SECONDS", None)

    with caplog.at_level(logging.INFO, logger="dmr_incoming_service"):
        start_and_stop_the_app()

    assert any(NO_LIMIT_WARNING in r.getMessage() for r in caplog.records)
    assert any("max queue wait off" in r.getMessage() for r in caplog.records)


def test_no_warning_when_the_queue_wait_limit_is_on(monkeypatch, caplog):
    monkeypatch.setattr(settings, "MAX_QUEUE_WAIT_SECONDS", 260.0)

    with caplog.at_level(logging.INFO, logger="dmr_incoming_service"):
        start_and_stop_the_app()

    assert not any(NO_LIMIT_WARNING in r.getMessage() for r in caplog.records)
    assert any("max queue wait 260s" in r.getMessage() for r in caplog.records)


def test_http_sessions_have_room_for_every_thread():
    # The ack's 40 threads, the process workers and the sweeper
    assert settings.HTTP_POOL_MAXSIZE == 40 + settings.PROCESS_WORKERS + 1
    real = app_module.processor
    for client in (real.resql, real.classifier, real.agent):
        adapter = client.session.get_adapter("http://resql")
        assert adapter._pool_maxsize == settings.HTTP_POOL_MAXSIZE


def test_health_answers():
    async def scenario():
        return await call("GET", "/health")

    status, body = asyncio.run(scenario())

    assert (status, body["status"]) == (200, "healthy")
