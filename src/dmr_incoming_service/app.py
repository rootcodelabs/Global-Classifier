"""FastAPI app for the GC's DMR agent (OUTGOING_MESSAGE_ENDPOINT = http://dmr-incoming-service:8095/dmr/incoming).
POST /dmr/incoming acks after one database insert (DMR waits at most 2 s) and classifies and
answers in a background task. Run with one worker: the sweeper and background tasks are in-process.
"""

import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from dmr_incoming_service import settings
from dmr_incoming_service.clients import (
    ClassifyClient,
    DmrAgentClient,
    ResqlClient,
    ResqlError,
)
from dmr_incoming_service.processor import Processor, parse_envelope

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("dmr_incoming_service")

processor = Processor(
    resql=ResqlClient(settings.RESQL_URL, settings.RESQL_TIMEOUT),
    classifier=ClassifyClient(settings.CLASSIFY_URL, settings.CLASSIFY_TIMEOUT),
    agent=DmrAgentClient(settings.DMR_AGENT_SEND_URL, settings.AGENT_TIMEOUT),
    gc_agent_id=settings.GC_AGENT_ID,
    stale_after_seconds=settings.STALE_AFTER_SECONDS,
    send_attempts=settings.AGENT_SEND_ATTEMPTS,
    retry_delay_seconds=settings.AGENT_RETRY_DELAY_SECONDS,
    resend_after_seconds=settings.RESEND_AFTER_SECONDS,
    max_response_attempts=settings.RESPONSE_MAX_ATTEMPTS,
)


def _sweep_loop(stop: threading.Event) -> None:
    while not stop.wait(settings.SWEEP_INTERVAL_SECONDS):
        try:
            processor.sweep()
        except Exception as error:  # keep the sweeper alive
            logger.error("DMR sweeper failed: %s", type(error).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = threading.Event()
    sweeper = threading.Thread(
        target=_sweep_loop, args=(stop,), name="dmr-sweeper", daemon=True
    )
    sweeper.start()
    logger.info(
        "dmr-incoming-service started (stale after %ss, resend after %ss, sweep every %ss)",
        settings.STALE_AFTER_SECONDS,
        settings.RESEND_AFTER_SECONDS,
        settings.SWEEP_INTERVAL_SECONDS,
    )
    yield
    stop.set()


app = FastAPI(title="Global Classifier DMR incoming service", lifespan=lifespan)


@app.post("/dmr/incoming")
async def dmr_incoming(request: Request, background_tasks: BackgroundTasks):
    # The body is parsed here, not by a pydantic model: FastAPI's automatic 422 is a non-2xx,
    # and DMR would redeliver an unusable message forever.
    envelope = parse_envelope(await request.body())
    status_code, body, job = await run_in_threadpool(processor.accept, envelope)
    if job is not None:
        background_tasks.add_task(processor.process, job)
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
def health():
    return {"status": "healthy", "service": "dmr-incoming-service"}
