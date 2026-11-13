"""Processor.sweep_stale: messages acked but never processed get a 'failed' result and an alert log."""

import json
import logging

from dmr_incoming_service.clients import ResqlError
from dmr_test_helpers import (
    AGENCY_A,
    CHAT_CREATED,
    CHAT_ID,
    POLICE,
    RESPONSE_ID,
    new_id,
)


def stale_row(**overrides):
    row = {
        "messageId": new_id(),
        "responseMessageId": RESPONSE_ID,
        "senderId": AGENCY_A,
        "chatId": CHAT_ID,
        "chatCreated": CHAT_CREATED,
        "messageType": "ChatMessage",
    }
    row.update(overrides)
    return row


def test_stale_rows_get_a_failed_result_and_an_error_log(
    processor, resql, agent, caplog
):
    row = stale_row()
    resql.answers["update-stale-dmr-incoming-messages-failed"] = [row]

    with caplog.at_level(logging.ERROR, logger="dmr_incoming_service"):
        assert processor.sweep_stale() == 1

    assert resql.last("update-stale-dmr-incoming-messages-failed") == {
        "olderThanSeconds": 300
    }
    assert len(agent.sent) == 1
    sent = agent.sent[0]
    assert sent["recipientId"] == AGENCY_A
    content = json.loads(sent["payload"]["messages"][0]["content"])
    assert content["status"] == "failed"
    assert content["requestMessageId"] == row["messageId"]
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SENT"
    assert f"stale DMR message {row['messageId']}" in caplog.text


def test_stale_row_without_a_usable_chat_is_skipped(processor, resql, agent):
    resql.answers["update-stale-dmr-incoming-messages-failed"] = [
        stale_row(chatId=None)
    ]

    processor.sweep_stale()

    assert agent.sent == []
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SKIPPED"


def test_no_stale_rows_does_nothing(processor, resql, agent):
    assert processor.sweep_stale() == 0
    assert agent.sent == []


def test_sweeper_survives_resql_errors(processor, resql, agent):
    resql.answers["update-stale-dmr-incoming-messages-failed"] = ResqlError("down")

    assert processor.sweep_stale() == 0


def test_stale_row_send_failure_is_tried_once_and_left_pending(
    processor, resql, agent, sleeps
):
    resql.answers["update-stale-dmr-incoming-messages-failed"] = [stale_row()]
    agent.answer = (False, "GC DMR agent timed out", True)

    processor.sweep_stale()

    assert len(agent.sent) == 1 and sleeps == []  # the sweeper itself is the retry loop
    assert resql.last("update-dmr-response-status")["responseStatus"] == "PENDING"


# ---- results never delivered


def unanswered_row(**overrides):
    row = stale_row(
        resultStatus="classified",
        topAgencyId=POLICE,
        topAgencyName="Police",
        topConfidence=0.93,
        responseAttempts=1,
    )
    row.update(overrides)
    return row


def test_unanswered_classified_result_is_sent_again_unchanged(processor, resql, agent):
    row = unanswered_row()
    resql.answers["update-unanswered-dmr-incoming-messages"] = [row]

    assert processor.sweep_unanswered() == 1

    assert resql.last("update-unanswered-dmr-incoming-messages") == {
        "olderThanSeconds": 120
    }
    sent = agent.sent[0]
    assert sent["id"] == RESPONSE_ID  # same envelope id as the first try
    assert sent["recipientId"] == AGENCY_A
    assert json.loads(sent["payload"]["messages"][0]["content"]) == {
        "requestMessageId": row["messageId"],
        "status": "classified",
        "agencyId": POLICE,
        "agencyName": "Police",
        "confidence": 0.93,
    }
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SENT"


def test_unanswered_failed_result_is_sent_as_failed(processor, resql, agent):
    resql.answers["update-unanswered-dmr-incoming-messages"] = [
        unanswered_row(resultStatus="failed", topAgencyId=None, topAgencyName=None)
    ]

    processor.sweep_unanswered()

    content = json.loads(agent.sent[0]["payload"]["messages"][0]["content"])
    assert content["status"] == "failed" and content["agencyId"] == ""


def test_unanswered_resend_failure_stays_pending_until_the_last_round(
    processor, resql, agent, sleeps
):
    agent.answer = (False, "HTTP 503: down", True)
    resql.answers["update-unanswered-dmr-incoming-messages"] = [
        unanswered_row(responseAttempts=2)
    ]
    processor.sweep_unanswered()
    assert len(agent.sent) == 1 and sleeps == []
    assert resql.last("update-dmr-response-status")["responseStatus"] == "PENDING"

    resql.answers["update-unanswered-dmr-incoming-messages"] = [
        unanswered_row(responseAttempts=4)
    ]
    processor.sweep_unanswered()
    assert resql.last("update-dmr-response-status")["responseStatus"] == "FAILED"


def test_unanswered_row_still_being_processed_is_left_alone(processor, resql, agent):
    row = unanswered_row()
    processor._claim(row["messageId"])
    resql.answers["update-unanswered-dmr-incoming-messages"] = [row]

    assert processor.sweep_unanswered() == 0
    assert agent.sent == []
    assert resql.params("update-dmr-response-status") == []


def test_unanswered_row_without_a_usable_chat_is_skipped(processor, resql, agent):
    resql.answers["update-unanswered-dmr-incoming-messages"] = [
        unanswered_row(chatId=None)
    ]

    processor.sweep_unanswered()

    assert agent.sent == []
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SKIPPED"


def test_unanswered_sweep_survives_resql_errors(processor, resql):
    resql.answers["update-unanswered-dmr-incoming-messages"] = ResqlError("down")

    assert processor.sweep_unanswered() == 0


def test_sweep_runs_both_passes(processor, resql):
    processor.sweep()

    queries = [query for query, _ in resql.calls]
    assert queries == [
        "update-stale-dmr-incoming-messages-failed",
        "update-unanswered-dmr-incoming-messages",
    ]


def test_one_failing_row_does_not_stop_the_others(processor, resql, agent):
    rows = [stale_row(), stale_row()]
    resql.answers["update-stale-dmr-incoming-messages-failed"] = rows
    calls = {"n": 0}

    def flaky(params):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ResqlError("resql timed out")
        return [{"messageId": params["messageId"]}]

    resql.answers["update-dmr-response-status"] = flaky

    assert processor.sweep_stale() == 2
    assert len(agent.sent) == 2
