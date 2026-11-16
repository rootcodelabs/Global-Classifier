"""Service URLs from constants.ini (shared with Ruuter) and tuning from environment variables."""

import configparser
import os

from dmr_incoming_service.processor import is_uuid


def parse_gc_agent_id(value: str) -> str:
    """GLOBAL_CLASSIFIER_DMR_AGENT_ID, checked. Empty is allowed (the repo default until staging;
    app.py warns at startup). Anything else must be a UUID: a typo or a copied placeholder would
    switch the loop guard off just as quietly, while it looks set, so it stops the service.
    """
    value = (value or "").strip()
    if value and not is_uuid(value):
        raise RuntimeError(
            "GLOBAL_CLASSIFIER_DMR_AGENT_ID in constants.ini is not a UUID. Set it to the GC's "
            "CentOps clientId, or leave it empty."
        )
    return value


def queue_wait_limit(stale_after_seconds: float, record_within_seconds: float):
    """The longest a message may wait in the queue and still be classified: the stale limit minus
    the time a job needs to record its result. None (no limit) when that isn't positive: every
    message would count as waited too long and none would be classified. app.py warns then.
    """
    limit = stale_after_seconds - record_within_seconds
    return limit if limit > 0 else None


_CONSTANTS_FILE = os.environ.get("CONSTANTS_FILE", "/app/constants.ini")
_config = configparser.ConfigParser(interpolation=None)
_config.optionxform = str  # keep key case
if not _config.read(_CONSTANTS_FILE):
    raise RuntimeError(f"Constants file not found: {_CONSTANTS_FILE}")
_dsl = _config["DSL"]

RESQL_URL = _dsl["GLOBAL_CLASSIFIER_RESQL"].rstrip("/")
CLASSIFY_URL = f"{_dsl['GLOBAL_CLASSIFIER_RUUTER_PUBLIC'].rstrip('/')}/chats/classify"
DMR_AGENT_SEND_URL = f"{_dsl['GLOBAL_CLASSIFIER_DMR_AGENT'].rstrip('/')}/v1/messages"
# The GC's own DMR agent ID (its CentOps clientId), used by the loop guard
GC_AGENT_ID = parse_gc_agent_id(_dsl["GLOBAL_CLASSIFIER_DMR_AGENT_ID"])


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


# Longer than DMR's 2 s ack timeout on purpose: a slow insert that succeeds is still processed,
# and DMR's redelivery hits the dedupe. A shorter timeout could leave the row RECEIVED.
RESQL_TIMEOUT = _env_float("DMR_RESQL_TIMEOUT", 5.0)
CLASSIFY_TIMEOUT = _env_float("DMR_CLASSIFY_TIMEOUT", 30.0)
AGENT_TIMEOUT = _env_float("DMR_AGENT_TIMEOUT", 10.0)
STALE_AFTER_SECONDS = int(_env_float("DMR_STALE_AFTER_SECONDS", 300))
SWEEP_INTERVAL_SECONDS = _env_float("DMR_SWEEP_INTERVAL_SECONDS", 60.0)

# Sending the result: tries in a row on a transient failure, with backoff (delay, 2x delay, ...)
AGENT_SEND_ATTEMPTS = max(1, int(_env_float("DMR_AGENT_SEND_ATTEMPTS", 3)))
AGENT_RETRY_DELAY_SECONDS = _env_float("DMR_AGENT_RETRY_DELAY_SECONDS", 1.0)
# A result that is still unsent this long after the last try is sent again by the sweeper.
# Must be longer than one round of tries (AGENT_SEND_ATTEMPTS x DMR_AGENT_TIMEOUT plus backoff).
RESEND_AFTER_SECONDS = int(_env_float("DMR_RESEND_AFTER_SECONDS", 120))
# Rounds of tries (the first send plus the sweeper's resends) before the result is FAILED for good
RESPONSE_MAX_ATTEMPTS = max(1, int(_env_float("DMR_RESPONSE_MAX_ATTEMPTS", 5)))
# Threads that classify and answer accepted messages. A pool of their own, so slow classifications
# never take the threads the ack needs (DMR waits at most 2 s). Also the most classify calls in flight.
PROCESS_WORKERS = max(1, int(_env_float("DMR_PROCESS_WORKERS", 8)))
# Messages waiting or in progress in that pool at which a backlog WARNING is logged
QUEUE_WARN_AT = max(1, int(_env_float("DMR_QUEUE_WARN_AT", PROCESS_WORKERS * 10)))
# How long a job takes, at most by its timeouts, from start to recording its result
# (sender lookup, classify, record)
RECORD_WITHIN_SECONDS = 2 * RESQL_TIMEOUT + CLASSIFY_TIMEOUT
# A message that waited longer than this in the pool's queue is answered 'failed' without being
# classified: the sweeper would likely close its row before the result is recorded. None: no
# limit. Not an env variable: it follows from the values above.
MAX_QUEUE_WAIT_SECONDS = queue_wait_limit(STALE_AFTER_SECONDS, RECORD_WITHIN_SECONDS)

# Threads that may use an HTTP session at once: the ack's (Starlette's run_in_threadpool, which
# uses anyio's default limit of 40), the process workers, and the sweeper. Each session keeps up
# to this many connections per host, so none is opened and thrown away for lack of room.
ACK_THREADS = 40
HTTP_POOL_MAXSIZE = ACK_THREADS + PROCESS_WORKERS + 1
