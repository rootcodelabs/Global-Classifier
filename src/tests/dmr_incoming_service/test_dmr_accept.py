"""Processor.accept: what happens before the ack DMR waits for."""

from dmr_incoming_service.clients import ResqlError
from dmr_incoming_service.processor import parse_envelope
from dmr_test_helpers import AGENCY_A, CHAT_ID, RESPONSE_ID, make_envelope


def test_new_message_is_accepted_and_returns_a_job(processor, resql):
    envelope = make_envelope()

    status, body, job = processor.accept(envelope)

    assert status == 200
    assert body == {"status": "accepted", "messageId": envelope["id"]}
    assert job.message_id == envelope["id"]
    assert job.sender_id == AGENCY_A
    assert job.chat_id == CHAT_ID
    assert job.response_message_id == RESPONSE_ID
    assert job.chat_url == "https://www.eesti.ee"
    insert = resql.last("insert-dmr-incoming-message")
    assert insert["messageId"] == envelope["id"]
    assert insert["chatCreated"] == "2026-11-09T10:00:00.000Z"
    assert insert["sentAt"].startswith("2026-11-09T10:15:00")


def test_insert_never_receives_message_content(processor, resql):
    processor.accept(make_envelope())

    insert = resql.last("insert-dmr-incoming-message")
    assert "Kuidas" not in str(insert)


def test_redelivery_is_a_duplicate_without_a_job(processor, resql):
    resql.answers["insert-dmr-incoming-message"] = []
    envelope = make_envelope()

    status, body, job = processor.accept(envelope)

    assert status == 200
    assert body["status"] == "duplicate"
    assert job is None


def test_id_that_is_not_a_uuid_is_ignored_without_a_row(processor, resql):
    status, body, job = processor.accept(make_envelope(id="not-a-uuid"))

    assert (status, body["status"], job) == (200, "ignored", None)
    assert resql.calls == []


def test_missing_sender_is_ignored(processor, resql):
    envelope = make_envelope()
    del envelope["senderId"]

    status, body, job = processor.accept(envelope)

    assert (status, body["status"], job) == (200, "ignored", None)
    assert resql.calls == []


def test_sender_that_is_not_a_uuid_is_ignored(processor, resql):
    # The result goes back with the sender as recipientId, which the agent requires to be a UUID
    for sender in ("agency-a", "", 5, AGENCY_A + "\x00"):
        status, body, job = processor.accept(make_envelope(senderId=sender))
        assert (status, body["status"], job) == (200, "ignored", None), sender
    assert resql.calls == []


def test_ids_postgres_would_reject_are_ignored_not_retried(processor, resql):
    # uuid.UUID() accepts all of these; Postgres' uuid type rejects them, so the insert would
    # fail and DMR would redeliver forever
    loose = (
        "a1e45678-12bc-4ef0-9876-def1234567_8",
        " a1e45678-12bc-4ef0-9876-def12345678",
        "+1e45678-12bc-4ef0-9876-def123456789",
    )
    for value in loose:
        assert processor.accept(make_envelope(id=value))[1]["status"] == "ignored"
        assert processor.accept(make_envelope(senderId=value))[1]["status"] == "ignored"
    assert resql.calls == []


def test_nul_characters_are_removed_before_the_insert(processor, resql):
    envelope = make_envelope(type="Chat\x00Message", recipientId="gc\x00")
    envelope["payload"]["chat"]["created"] = "2026-11-09T10:00:00.000Z\x00"

    processor.accept(envelope)

    insert = resql.last("insert-dmr-incoming-message")
    assert "\x00" not in str(insert)
    assert insert["messageType"] == "ChatMessage"
    assert insert["chatCreated"] == "2026-11-09T10:00:00.000Z"


def test_unparseable_bodies_become_none_and_are_ignored(processor, resql):
    deep = b"[" * 100_000 + b"]" * 100_000  # json raises RecursionError, not ValueError
    for raw in (b"not json", b"\xff\xfe", deep):
        envelope = parse_envelope(raw)
        assert envelope is None
        assert processor.accept(envelope)[1]["status"] == "ignored"
    assert parse_envelope(b'{"id": "x"}') == {"id": "x"}
    assert resql.calls == []


def test_body_that_is_not_an_object_is_ignored(processor, resql):
    for body_value in (None, [], "text", 5):
        status, body, job = processor.accept(body_value)
        assert (status, body["status"], job) == (200, "ignored", None)
    assert resql.calls == []


def test_insert_failure_returns_500_so_dmr_redelivers(processor, resql):
    resql.answers["insert-dmr-incoming-message"] = ResqlError("resql timed out")

    status, body, job = processor.accept(make_envelope())

    assert status == 500
    assert job is None


STUCK_RESPONSE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def test_redelivery_of_a_row_never_processed_is_resumed(processor, resql):
    # The insert timed out here but landed later (database came back while Resql waited)
    resql.answers["insert-dmr-incoming-message"] = []
    resql.answers["get-dmr-incoming-message"] = [
        {"status": "RECEIVED", "responseMessageId": STUCK_RESPONSE_ID}
    ]
    envelope = make_envelope()

    status, body, job = processor.accept(envelope)

    assert (status, body["status"]) == (200, "accepted")
    assert job.response_message_id == STUCK_RESPONSE_ID
    assert job.messages == envelope["payload"]["messages"]


def test_redelivery_while_processing_is_a_duplicate(processor, resql):
    envelope = make_envelope()
    _, _, job = processor.accept(envelope)  # first delivery, still being processed
    resql.answers["insert-dmr-incoming-message"] = []
    resql.answers["get-dmr-incoming-message"] = [
        {"status": "RECEIVED", "responseMessageId": RESPONSE_ID}
    ]

    status, body, second = processor.accept(envelope)

    assert body["status"] == "duplicate" and second is None

    processor.process(job)  # releases the message
    resql.answers["get-dmr-incoming-message"] = [
        {"status": "CLASSIFIED", "responseMessageId": RESPONSE_ID}
    ]
    assert processor.accept(envelope)[1]["status"] == "duplicate"


def test_two_redeliveries_of_a_stuck_row_resume_once(processor, resql):
    resql.answers["insert-dmr-incoming-message"] = []
    resql.answers["get-dmr-incoming-message"] = [
        {"status": "RECEIVED", "responseMessageId": STUCK_RESPONSE_ID}
    ]
    envelope = make_envelope()

    first = processor.accept(envelope)
    second = processor.accept(envelope)

    assert first[1]["status"] == "accepted"
    assert second[1]["status"] == "duplicate"


def test_duplicate_check_failure_is_still_a_duplicate(processor, resql):
    resql.answers["insert-dmr-incoming-message"] = []
    resql.answers["get-dmr-incoming-message"] = ResqlError("resql timed out")

    status, body, job = processor.accept(make_envelope())

    assert (status, body["status"], job) == (200, "duplicate", None)


def test_invalid_timestamp_is_stored_as_empty(processor, resql):
    processor.accept(make_envelope(timestamp="yesterday"))

    assert resql.last("insert-dmr-incoming-message")["sentAt"] == ""


def test_missing_payload_still_records_the_row(processor, resql):
    envelope = make_envelope()
    del envelope["payload"]

    status, body, job = processor.accept(envelope)

    assert body["status"] == "accepted"
    assert job.chat_id == ""
    assert job.messages == []
