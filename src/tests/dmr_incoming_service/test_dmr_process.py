"""Processor.process: classification and the result sent back to the sender, after the ack."""

import json

from dmr_incoming_service.clients import ClassifyResult, ResqlError
from dmr_test_helpers import (
    AGENCY_A,
    CHAT_ID,
    GC_ID,
    POLICE,
    QUESTION,
    RESPONSE_ID,
    make_envelope,
    new_id,
    result_message,
)


def accept(processor, envelope):
    status, body, job = processor.accept(envelope)
    assert body["status"] == "accepted"
    return job


def sent_content(agent):
    assert len(agent.sent) == 1
    return json.loads(agent.sent[0]["payload"]["messages"][0]["content"])


# ---- classified


def test_classified_message_sends_the_result_back_to_the_sender(
    processor, resql, classifier, agent
):
    envelope = make_envelope()
    job = accept(processor, envelope)

    processor.process(job)

    assert classifier.calls == [
        {"chatId": CHAT_ID, "message": QUESTION, "url": "https://www.eesti.ee"}
    ]
    update = resql.last("update-dmr-incoming-message")
    assert update["status"] == "CLASSIFIED"
    assert update["resultStatus"] == "classified"
    assert update["topAgencyId"] == POLICE
    assert update["topConfidence"] == "0.93"
    assert update["senderKnown"] is True

    sent = agent.sent[0]
    assert sent["id"] == RESPONSE_ID
    assert sent["id"] != envelope["id"]
    assert sent["recipientId"] == AGENCY_A
    assert sent["type"] == "ChatMessage"
    assert "senderId" not in sent
    assert sent["payload"]["chat"] == {
        "id": CHAT_ID,
        "created": "2026-11-09T10:00:00.000Z",
    }
    assert len(sent["payload"]["messages"]) == 1
    message = sent["payload"]["messages"][0]
    assert message["id"] == RESPONSE_ID
    assert message["chatId"] == CHAT_ID
    assert message["event"] == "global-classifier-result"
    assert message["authorRole"] == "global-classifier"
    assert sent_content(agent) == {
        "requestMessageId": envelope["id"],
        "status": "classified",
        "agencyId": POLICE,
        "agencyName": "Police",
        "confidence": 0.93,
    }
    response = resql.last("update-dmr-response-status")
    assert response == {
        "messageId": envelope["id"],
        "responseStatus": "SENT",
        "responseError": "",
    }


def test_result_never_contains_the_question(processor, agent):
    processor.process(accept(processor, make_envelope()))

    assert QUESTION not in json.dumps(agent.sent[0])


def test_latest_end_user_message_is_classified(processor, classifier):
    envelope = make_envelope()
    messages = envelope["payload"]["messages"]
    messages.append(
        {
            "id": new_id(),
            "chatId": CHAT_ID,
            "content": "Vastus",
            "authorTimestamp": "2026-11-09T10:01:00.000Z",
            "authorRole": "buerokratt",
        }
    )

    processor.process(accept(processor, envelope))

    assert classifier.calls[0]["message"] == QUESTION


def test_unknown_sender_is_still_classified(processor, resql, agent):
    resql.answers["get-agency"] = []

    processor.process(accept(processor, make_envelope()))

    assert resql.last("update-dmr-incoming-message")["senderKnown"] is False
    assert len(agent.sent) == 1


def test_sender_lookup_failure_does_not_block_classification(processor, resql, agent):
    resql.answers["get-agency"] = ResqlError("resql timed out")

    processor.process(accept(processor, make_envelope()))

    assert resql.last("update-dmr-incoming-message")["status"] == "CLASSIFIED"
    assert len(agent.sent) == 1


# ---- out of distribution and failures


def test_out_of_distribution_result_has_no_agency(processor, classifier, resql, agent):
    for agency_id in (0, "0"):
        agent.sent.clear()
        top = {
            "agency_id": agency_id,
            "agency_name": "out_of_distribution",
            "confidence": 1,
        }
        classifier.result = ClassifyResult(ok=True, top=top, full=[[top]])

        processor.process(accept(processor, make_envelope()))

        assert (
            resql.last("update-dmr-incoming-message")["resultStatus"]
            == "out_of_distribution"
        )
        # top_agency_id is a uuid column, so the "0" id is stored as NULL
        assert resql.last("update-dmr-incoming-message")["topAgencyId"] == ""
        content = sent_content(agent)
        assert content["status"] == "out_of_distribution"
        assert content["agencyId"] == ""
        assert content["agencyName"] == ""
        assert content["confidence"] == ""


def test_classify_failure_is_recorded_and_answered_as_failed(
    processor, classifier, resql, agent
):
    classifier.result = ClassifyResult(ok=False, reason="classify returned HTTP 503")

    processor.process(accept(processor, make_envelope()))

    update = resql.last("update-dmr-incoming-message")
    assert update["status"] == "FAILED"
    assert update["errorReason"] == "classify returned HTTP 503"
    assert update["resultStatus"] == "failed"
    assert sent_content(agent)["status"] == "failed"
    assert sent_content(agent)["agencyId"] == ""
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SENT"


def test_sender_that_is_the_gc_is_skipped(processor, resql, agent):
    processor.process(accept(processor, make_envelope(senderId=GC_ID.upper())))

    assert agent.sent == []
    response = resql.last("update-dmr-response-status")
    assert response["responseStatus"] == "SKIPPED"
    assert response["responseError"] == "sender is the GC"


UNREACHABLE = (False, "GC DMR agent unreachable: ConnectionError", True)


def test_validation_failure_is_final_and_not_retried(processor, resql, agent, sleeps):
    agent.answer = (False, "HTTP 400: property x should not exist", False)

    processor.process(accept(processor, make_envelope()))

    assert len(agent.sent) == 1 and sleeps == []
    response = resql.last("update-dmr-response-status")
    assert response["responseStatus"] == "FAILED"
    assert response["responseError"] == "HTTP 400: property x should not exist"


def test_transient_failure_is_retried_with_backoff_then_sent(
    processor, resql, agent, sleeps
):
    agent.answer = [UNREACHABLE, UNREACHABLE, (True, "", False)]

    processor.process(accept(processor, make_envelope()))

    assert len(agent.sent) == 3
    assert sleeps == [1.0, 2.0]
    assert {sent["id"] for sent in agent.sent} == {RESPONSE_ID}  # same envelope id
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SENT"


def test_transient_failure_left_pending_for_the_sweeper(processor, resql, agent):
    agent.answer = UNREACHABLE

    processor.process(accept(processor, make_envelope()))

    assert len(agent.sent) == 3
    response = resql.last("update-dmr-response-status")
    assert response["responseStatus"] == "PENDING"
    assert response["responseError"] == UNREACHABLE[1]


def test_failed_resend_on_the_last_round_is_final(processor, resql, agent, caplog):
    agent.answer = UNREACHABLE
    job = accept(processor, make_envelope())
    job.response_attempts = 4  # rounds already used, max is 5

    processor.process(job)

    assert resql.last("update-dmr-response-status")["responseStatus"] == "FAILED"
    assert "FAILED for good" in caplog.text


def test_unexpected_error_on_an_unanswerable_job_records_skipped(
    processor, resql, agent
):
    # The row is closed as FAILED but no result can be built: the response must not stay
    # unset, or the sweeper would keep picking the row up
    job = accept(processor, make_envelope())
    job.chat_id = ""

    processor._fail(job, RuntimeError("boom"))

    assert resql.last("update-dmr-incoming-message")["status"] == "FAILED"
    assert agent.sent == []
    assert resql.last("update-dmr-response-status")["responseStatus"] == "SKIPPED"


def test_row_closed_by_the_sweeper_gets_no_second_result(processor, resql, agent):
    resql.answers["update-dmr-incoming-message"] = []

    processor.process(accept(processor, make_envelope()))

    assert agent.sent == []
    assert resql.params("update-dmr-response-status") == []


def test_unexpected_error_marks_the_row_failed_and_answers(
    processor, classifier, resql, agent
):
    classifier.result = RuntimeError("boom")

    processor.process(accept(processor, make_envelope()))

    update = resql.last("update-dmr-incoming-message")
    assert update["status"] == "FAILED"
    assert update["errorReason"] == "internal error: RuntimeError"
    assert sent_content(agent)["status"] == "failed"


def test_process_never_raises_even_when_resql_is_down(processor, resql, agent):
    job = accept(processor, make_envelope())
    resql.answers["update-dmr-incoming-message"] = ResqlError("resql unreachable")

    processor.process(job)  # must not raise

    assert agent.sent == []


# ---- rejects


def rejected_reason(resql):
    update = resql.last("update-dmr-incoming-message")
    assert update["status"] == "REJECTED"
    return update["errorReason"]


def test_unsupported_type_is_rejected(processor, resql, classifier, agent):
    processor.process(accept(processor, make_envelope(type="ClassificationResult")))

    assert rejected_reason(resql) == "unsupported message type: ClassificationResult"
    assert classifier.calls == [] and agent.sent == []


def test_missing_chat_id_is_rejected(processor, resql, agent):
    envelope = make_envelope()
    del envelope["payload"]["chat"]["id"]

    processor.process(accept(processor, envelope))

    assert rejected_reason(resql) == "chat id missing or not a UUID"
    assert agent.sent == []


def test_missing_chat_created_is_rejected(processor, resql, agent):
    envelope = make_envelope()
    del envelope["payload"]["chat"]["created"]

    processor.process(accept(processor, envelope))

    assert rejected_reason(resql) == "chat created missing"
    assert agent.sent == []


def test_no_content_is_rejected(processor, resql, classifier, agent):
    envelope = make_envelope()
    for message in envelope["payload"]["messages"]:
        del message["content"]

    processor.process(accept(processor, envelope))

    assert rejected_reason(resql) == "no message content"
    assert classifier.calls == [] and agent.sent == []


def test_echoed_result_is_rejected_without_classifying(
    processor, resql, classifier, agent
):
    envelope = make_envelope()
    envelope["payload"]["messages"].append(result_message())

    processor.process(accept(processor, envelope))

    assert rejected_reason(resql) == "already classified"
    assert classifier.calls == [] and agent.sent == []


def test_follow_up_after_a_result_is_classified(processor, classifier, agent):
    envelope = make_envelope()
    messages = envelope["payload"]["messages"]
    messages.append(result_message())
    messages.append(
        {
            "id": new_id(),
            "chatId": CHAT_ID,
            "content": "Aga ID-kaart?",
            "authorTimestamp": "2026-11-09T10:20:00.000Z",
            "authorRole": "end-user",
        }
    )

    processor.process(accept(processor, envelope))

    assert classifier.calls[0]["message"] == "Aga ID-kaart?"
    assert sent_content(agent)["status"] == "classified"
