"""Service URLs from constants.ini (shared with Ruuter) and tuning from environment variables."""

import configparser
import os

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
GC_AGENT_ID = _dsl["GLOBAL_CLASSIFIER_DMR_AGENT_ID"].strip()


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
