"""The result envelope must pass the real DMR agent's ExternalServiceMessageDto validation.

validate_external_message mirrors the DTO (whitelist + forbidNonWhitelisted); it is copied from
dmr-poc/mock_dmr.py so the unit tests don't depend on the POC folder.
"""

import json
import re
from datetime import datetime

from dmr_incoming_service.clients import top_from_classify
from dmr_incoming_service.processor import (
    build_envelope,
    build_result_payload,
    extract_question,
    parse_timestamp,
    result_status_for,
)
from dmr_test_helpers import (
    AGENCY_A,
    CHAT_CREATED,
    CHAT_ID,
    POLICE,
    RESPONSE_ID,
    new_id,
    result_message,
)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
CHAT_FIELDS = {
    "id", "endUserFirstName", "endUserLastName", "endUserId", "endUserEmail", "endUserPhone",
    "customerSupportDisplayName", "created", "endUserOs", "endUserUrl",
}  # fmt: skip
MESSAGE_FIELDS = {
    "id", "chatId", "content", "event", "csaTitle", "authorId", "authorTimestamp",
    "authorFirstName", "authorLastName", "authorRole", "forwardedByUser", "forwardedFromCsa",
    "forwardedToCsa", "originalBaseId", "originalCreated", "rating", "created", "preview",
    "updated", "buttons", "options",
}  # fmt: skip
ENVELOPE_FIELDS = {"id", "recipientId", "timestamp", "type", "payload"}


def validate_external_message(body):
    errors = []

    def extra(obj, allowed, path):
        errors.extend(
            f"property {path}{k} should not exist" for k in obj if k not in allowed
        )

    def is_uuid(obj, key):
        return isinstance(obj.get(key), str) and UUID_RE.match(obj[key])

    def strings_only(obj, path):
        errors.extend(
            f"{path}{k} must be a string"
            for k, v in obj.items()
            if v is not None and not isinstance(v, str)
        )

    extra(body, ENVELOPE_FIELDS, "")
    if not is_uuid(body, "id") or not is_uuid(body, "recipientId"):
        errors.append("id and recipientId must be UUIDs")
    try:
        datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        errors.append("timestamp must be ISO 8601")
    if body.get("type") != "ChatMessage":
        errors.append("type must be ChatMessage")
    payload = body.get("payload") or {}
    extra(payload, {"chat", "messages"}, "payload.")
    chat = payload.get("chat") or {}
    extra(chat, CHAT_FIELDS, "payload.chat.")
    if not is_uuid(chat, "id") or not chat.get("created"):
        errors.append("chat.id must be a UUID and chat.created set")
    strings_only(chat, "payload.chat.")
    for index, message in enumerate(payload.get("messages") or []):
        path = f"payload.messages.{index}."
        extra(message, MESSAGE_FIELDS, path)
        if not is_uuid(message, "id") or not is_uuid(message, "chatId"):
            errors.append(f"{path}id and chatId must be UUIDs")
        if not message.get("authorTimestamp") or not message.get("authorRole"):
            errors.append(f"{path}authorTimestamp and authorRole are required")
        strings_only(message, path)
    return errors


def build(status, top):
    timestamp = "2026-11-09T10:15:00.000Z"
    payload = build_result_payload(
        chat_id=CHAT_ID,
        chat_created=CHAT_CREATED,
        response_message_id=RESPONSE_ID,
        request_message_id=new_id(),
        result_status=status,
        top=top,
        timestamp=timestamp,
    )
    return build_envelope(AGENCY_A, RESPONSE_ID, payload, timestamp)


def test_result_envelopes_pass_the_agent_dto_for_every_status():
    police = {"agency_id": POLICE, "agency_name": "Police", "confidence": 0.93}
    for status, top in (
        ("classified", police),
        ("out_of_distribution", None),
        ("failed", None),
    ):
        assert validate_external_message(build(status, top)) == []


def test_numeric_agency_id_is_sent_as_a_string():
    content = json.loads(
        build("classified", {"agency_id": 42, "agency_name": "X", "confidence": "0.5"})[
            "payload"
        ]["messages"][0]["content"]
    )
    assert content["agencyId"] == "42"
    assert content["confidence"] == 0.5


def test_top_from_classify_accepts_wrapped_and_bare_bodies():
    rows = [[{"agency_id": POLICE, "agency_name": "Police", "confidence": 0.9}]]
    assert top_from_classify({"response": rows})[0]["agency_id"] == POLICE
    assert top_from_classify(rows)[0]["agency_id"] == POLICE
    assert top_from_classify({"response": []})[0] is None
    assert top_from_classify("No production model")[0] is None


def test_result_status_for():
    assert (
        result_status_for({"agency_id": POLICE, "agency_name": "Police"})
        == "classified"
    )
    assert (
        result_status_for({"agency_id": 0, "agency_name": "x"}) == "out_of_distribution"
    )
    assert (
        result_status_for({"agency_id": "", "agency_name": "x"})
        == "out_of_distribution"
    )
    assert result_status_for(
        {"agency_id": "7", "agency_name": "out_of_distribution"}
    ) == ("out_of_distribution")


def test_extract_question_skips_results_and_falls_back_to_any_content():
    bot = {"authorRole": "buerokratt", "content": "Tere"}
    user = {"authorRole": "end-user", "content": "  Küsimus  "}
    assert extract_question([bot, user, bot]) == "Küsimus"
    assert extract_question([bot]) == "Tere"
    assert extract_question([user, result_message()]) == "Küsimus"
    assert extract_question([{"authorRole": "end-user", "content": "   "}]) == ""
    assert extract_question(["not a dict", None]) == ""
    assert extract_question(None) == ""


def test_parse_timestamp():
    assert parse_timestamp("2026-11-09T10:15:00.000Z").startswith("2026-11-09T10:15:00")
    assert parse_timestamp("2026-11-09T10:15:00").endswith("+00:00")
    assert parse_timestamp("not a date") == ""
    assert parse_timestamp(12345) == ""
