"""FastAPI app for the GC's DMR agent (OUTGOING_MESSAGE_ENDPOINT = http://dmr-incoming-service:8095/dmr/incoming).
POST /dmr/incoming acks after one database insert (DMR waits at most 2 s) and classifies and
answers on a separate, bounded thread pool. Run with one worker: the sweeper and the pool are in-process.
"""

import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from dmr_incoming_service import settings
from dmr_incoming_service.clients import (
    ClassifyClient,
    DmrAgentClient,
    ResqlClient,
    ResqlError,
    new_session,
)
from dmr_incoming_service.process_pool import ProcessPool
from dmr_incoming_service.processor import Processor, parse_envelope

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("dmr_incoming_service")

processor = Processor(
    resql=ResqlClient(
        settings.RESQL_URL,
        settings.RESQL_TIMEOUT,
        new_session(settings.HTTP_POOL_MAXSIZE),
    ),
    classifier=ClassifyClient(
        settings.CLASSIFY_URL,
        settings.CLASSIFY_TIMEOUT,
        new_session(settings.HTTP_POOL_MAXSIZE),
    ),
    agent=DmrAgentClient(
        settings.DMR_AGENT_SEND_URL,
        settings.AGENT_TIMEOUT,
        new_session(settings.HTTP_POOL_MAXSIZE),
    ),
    gc_agent_id=settings.GC_AGENT_ID,
    stale_after_seconds=settings.STALE_AFTER_SECONDS,
    send_attempts=settings.AGENT_SEND_ATTEMPTS,
    retry_delay_seconds=settings.AGENT_RETRY_DELAY_SECONDS,
    resend_after_seconds=settings.RESEND_AFTER_SECONDS,
    max_response_attempts=settings.RESPONSE_MAX_ATTEMPTS,
    max_queue_wait_seconds=settings.MAX_QUEUE_WAIT_SECONDS,
)


def _warn_if_no_gc_agent_id() -> None:
    """An empty GC agent ID switches the loop guard off. Not fatal: the echo guard still rejects
    the GC's own results, and the repo's constants.ini leaves it empty until staging."""
    if not settings.GC_AGENT_ID:
        logger.warning(
            "GLOBAL_CLASSIFIER_DMR_AGENT_ID is empty: the loop guard is off (messages from the "
            "GC itself are not skipped; the echo guard still rejects its own results). "
            "Set it to the GC's CentOps clientId."
        )


def _warn_if_no_queue_wait_limit() -> None:
    """With a stale limit no longer than a job needs to record its result, the queue-wait limit is
    off (it would answer every message 'failed'). Fine for a quick test of the sweeper; in real
    use the sweeper may then close rows that are still being classified."""
    if settings.MAX_QUEUE_WAIT_SECONDS is None:
        logger.warning(
            "DMR_STALE_AFTER_SECONDS (%ss) is not longer than a job may take to record its result "
            "(%.0fs: 2 x DMR_RESQL_TIMEOUT + DMR_CLASSIFY_TIMEOUT): the queue-wait limit is off, "
            "and the sweeper may answer 'failed' for messages still being classified.",
            settings.STALE_AFTER_SECONDS,
            settings.RECORD_WITHIN_SECONDS,
        )


def _sweep_loop(stop: threading.Event) -> None:
    while not stop.wait(settings.SWEEP_INTERVAL_SECONDS):
        try:
            processor.sweep()
        except Exception as error:  # keep the sweeper alive
            logger.error("DMR sweeper failed: %s", type(error).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Created per lifespan, like the sweeper, so a restart in the same process gets a live pool
    app.state.process_pool = ProcessPool(
        settings.PROCESS_WORKERS, settings.QUEUE_WARN_AT
    )
    stop = threading.Event()
    sweeper = threading.Thread(
        target=_sweep_loop, args=(stop,), name="dmr-sweeper", daemon=True
    )
    sweeper.start()
    max_wait = settings.MAX_QUEUE_WAIT_SECONDS
    logger.info(
        "dmr-incoming-service started (%s process workers, max queue wait %s, "
        "stale after %ss, resend after %ss, sweep every %ss)",
        settings.PROCESS_WORKERS,
        "off" if max_wait is None else f"{max_wait:.0f}s",
        settings.STALE_AFTER_SECONDS,
        settings.RESEND_AFTER_SECONDS,
        settings.SWEEP_INTERVAL_SECONDS,
    )
    _warn_if_no_gc_agent_id()
    _warn_if_no_queue_wait_limit()
    try:
        yield
    finally:
        stop.set()
        app.state.process_pool.shutdown()


app = FastAPI(title="Global Classifier DMR incoming service", lifespan=lifespan)


@app.post("/dmr/incoming")
async def dmr_incoming(request: Request):
    # The body is parsed here, not by a pydantic model: FastAPI's automatic 422 is a non-2xx,
    # and DMR would redeliver an unusable message forever.
    envelope = parse_envelope(await request.body())
    status_code, body, job = await run_in_threadpool(processor.accept, envelope)
    # process() never raises, so the queued job needs no error handling
    if job is not None and not request.app.state.process_pool.submit(
        processor.process, job
    ):
        # Shutting down. The row is recorded but will not be processed here, so no ack: DMR
        # redelivers, and the redelivery hits the dedupe and resumes the message (accept() →
        # _resumable), which needs the claim released.
        processor.release(job.message_id)
        logger.warning(
            "DMR message %s not queued (shutting down), DMR will redeliver",
            job.message_id,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "shutting down"},
        )
    return JSONResponse(status_code=status_code, content=body)


@app.get("/dmr/messages/{message_id}")
def dmr_message_status(message_id: str):
    """The row for a message, without content. For tests and debugging; keep the port internal."""
    try:
        row = processor.get_status(message_id)
    except ResqlError as error:
        return JSONResponse(status_code=503, content={"error": str(error)})
    if row is None:
        return JSONResponse(status_code=404, content={"error": "not found"})
    return row


@app.get("/health")
async def health():
    # async: answers on the event loop, without waiting for a free thread. So it shows the process
    # is up, not that acks are fast: a Resql outage that holds the ack threads still looks healthy.
    return {"status": "healthy", "service": "dmr-incoming-service"}
