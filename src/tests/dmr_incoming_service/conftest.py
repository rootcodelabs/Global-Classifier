"""Make dmr_incoming_service importable as a package, and provide the processor with fake clients."""

import os
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# settings.py reads constants.ini, which lives at /app in the container
os.environ.setdefault(
    "CONSTANTS_FILE", str(Path(__file__).resolve().parents[3] / "constants.ini")
)

from dmr_incoming_service.processor import Processor  # noqa: E402
from dmr_test_helpers import GC_ID, FakeAgent, FakeClassifier, FakeResql  # noqa: E402


@pytest.fixture
def resql():
    return FakeResql()


@pytest.fixture
def classifier():
    return FakeClassifier()


@pytest.fixture
def agent():
    return FakeAgent()


@pytest.fixture
def sleeps():
    """The backoff delays the processor waited, instead of really sleeping."""
    return []


@pytest.fixture
def processor(resql, classifier, agent, sleeps):
    return Processor(
        resql,
        classifier,
        agent,
        gc_agent_id=GC_ID,
        stale_after_seconds=300,
        send_attempts=3,
        retry_delay_seconds=1.0,
        resend_after_seconds=120,
        max_response_attempts=5,
        sleep=sleeps.append,
    )
