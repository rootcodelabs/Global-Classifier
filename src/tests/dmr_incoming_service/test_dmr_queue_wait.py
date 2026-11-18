"""Processor.process: a job that waited too long in the process pool's queue is answered 'failed'
without being classified. settings.queue_wait_limit: the limit, or None when it would be useless.
"""

import json
import logging

import pytest

from dmr_incoming_service.processor import QUEUE_TIMEOUT_REASON, Processor
from dmr_incoming_service.settings import queue_wait_limit
from dmr_test_helpers import AGENCY_A, GC_ID, make_envelope


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def limited(resql, classifier, agent, sleeps, clock):
    """A processor whose jobs may wait at most 260 s, as with the default settings."""
    return Processor(
        resql,
        classifier,
        agent,
        gc_agent_id=GC_ID,
        stale_after_seconds=300,
        max_queue_wait_seconds=260,
        sleep=sleeps.append,
        clock=clock,
    )


def test_accept_records_when_the_job_was_accepted(limited, clock):
    _, _, job = limited.accept(make_envelope())
    assert job.accepted_at == clock.now


def test_job_that_waited_too_long_is_answered_failed_without_classifying(
    limited, resql, classifier, agent, clock, caplog
):
    _, _, job = limited.accept(make_envelope())
    clock.now += 261

    with caplog.at_level(logging.WARNING, logger="dmr_incoming_service"):
        limited.process(job)

    # Nothing that takes time: no sender lookup, no classify
    assert classifier.calls == []
    assert resql.params("get-agency") == []
    # Closed now with its own reason, not left for the sweeper's "processing interrupted"
    update = resql.last("update-dmr-incoming-message")
    assert update["status"] == "FAILED"
    assert update["errorReason"] == QUEUE_TIMEOUT_REASON
    assert update["resultStatus"] == "FAILED"
    assert len(agent.sent) == 1
    assert agent.sent[0]["recipientId"] == AGENCY_A
    content = json.loads(agent.sent[0]["payload"]["messages"][0]["content"])
    assert content["status"] == "failed"
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SENT"
    assert limited._in_flight == set()
    warnings = [
        r for r in caplog.records if "waited 261s in the queue" in r.getMessage()
    ]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    # Not the crash alert
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_waited_too_long_but_already_swept_sends_nothing(
    limited, resql, classifier, agent, clock
):
    _, _, job = limited.accept(make_envelope())
    clock.now += 400
    # The sweeper closed the row first
    resql.answers["update-dmr-incoming-message"] = []

    limited.process(job)

    assert classifier.calls == []
    assert agent.sent == []
    assert resql.params("update-dmr-response-status") == []


def test_unusable_message_that_waited_too_long_is_still_rejected(
    limited, resql, agent, clock
):
    _, _, job = limited.accept(make_envelope(type="SomethingElse"))
    clock.now += 261

    limited.process(job)

    assert resql.last("update-dmr-incoming-message")["status"] == "REJECTED"
    assert agent.sent == []


def test_job_within_the_limit_is_classified(limited, resql, classifier, agent, clock):
    _, _, job = limited.accept(make_envelope())
    clock.now += 260

    limited.process(job)

    assert len(classifier.calls) == 1
    assert resql.last("update-dmr-incoming-message")["status"] == "CLASSIFIED"
    assert len(agent.sent) == 1


def test_without_a_limit_any_wait_is_classified(processor, classifier, agent):
    _, _, job = processor.accept(make_envelope())
    job.accepted_at -= 10_000

    processor.process(job)

    assert len(classifier.calls) == 1
    assert len(agent.sent) == 1


def test_job_without_an_accept_time_is_classified(limited, classifier, agent):
    _, _, job = limited.accept(make_envelope())
    job.accepted_at = None

    limited.process(job)

    assert len(classifier.calls) == 1
    assert len(agent.sent) == 1


# ---- settings.queue_wait_limit


def test_limit_is_the_stale_limit_minus_the_time_to_record():
    assert queue_wait_limit(300, 40) == 260


@pytest.mark.parametrize("stale_after", [40, 10, 0])
def test_limit_is_off_when_it_would_not_be_positive(stale_after):
    # e.g. DMR_STALE_AFTER_SECONDS=10 for a quick sweeper test: a limit of 0 would answer
    # every message 'failed' without classifying it
    assert queue_wait_limit(stale_after, 40) is None
