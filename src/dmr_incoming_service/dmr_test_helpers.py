"""Fakes and builders for the dmr_incoming_service tests (unique name: tests share one sys.path)."""

import copy
import uuid

from dmr_incoming_service.clients import ClassifyResult

GC_ID = "d3b07384-d9a0-4c3f-a4e2-123456789abc"
AGENCY_A = "a1e45678-12bc-4ef0-9876-def123456789"
POLICE = "5b1f0a6e-3c2d-4e8f-9a7b-0c1d2e3f4a5b"
RESPONSE_ID = "11111111-2222-4333-8444-555555555555"
CHAT_ID = "9c3a8e57-4b2f-4d1e-8f6a-7b5c4d3e2f1a"
CHAT_CREATED = "2026-11-09T10:00:00.000Z"
QUESTION = "Kuidas ma saan taotleda uut passi?"


def new_id():
    return str(uuid.uuid4())


def make_envelope(**overrides):
    """A decrypted envelope as the GC's DMR agent posts it to /dmr/incoming."""
    envelope = {
        "id": new_id(),
        "senderId": AGENCY_A,
        "recipientId": GC_ID,
        "timestamp": "2026-11-09T10:15:00.000Z",
        "type": "ChatMessage",
        "payload": {
            "chat": {
                "id": CHAT_ID,
                "created": CHAT_CREATED,
                "endUserUrl": "https://www.eesti.ee",
            },
            "messages": [
                {
                    "id": new_id(),
                    "chatId": CHAT_ID,
                    "content": "Tere! Kuidas saan teid aidata?",
                    "authorTimestamp": CHAT_CREATED,
                    "authorRole": "buerokratt",
                },
                {
                    "id": new_id(),
                    "chatId": CHAT_ID,
                    "content": QUESTION,
                    "authorTimestamp": CHAT_CREATED,
                    "authorRole": "end-user",
                },
            ],
        },
    }
    envelope.update(overrides)
    return envelope


def result_message(chat_id=CHAT_ID):
    return {
        "id": new_id(),
        "chatId": chat_id,
        "authorRole": "global-classifier",
        "authorTimestamp": CHAT_CREATED,
        "event": "global-classifier-result",
        "content": '{"status":"classified"}',
    }


def police_result():
    top = {"agency_id": POLICE, "agency_name": "Police", "confidence": 0.93}
    return ClassifyResult(ok=True, top=top, full=[[copy.deepcopy(top)]])


class FakeResql:
    """Records calls. Answers per query from `answers`: a list of rows, a callable or an exception."""

    def __init__(self):
        self.calls = []
        self.answers = {
            "insert-dmr-incoming-message": [
                {"id": 1, "responseMessageId": RESPONSE_ID}
            ],
            "update-dmr-incoming-message": [{"messageId": "x"}],
            "update-dmr-response-status": [{"messageId": "x"}],
            "get-agency": [{"agencyId": AGENCY_A}],
            "update-stale-dmr-incoming-messages-failed": [],
            "update-unanswered-dmr-incoming-messages": [],
            "get-dmr-incoming-message": [],
        }

    def call(self, query, params):
        self.calls.append((query, params))
        answer = self.answers.get(query, [])
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return answer(params)
        return answer

    def params(self, query):
        return [p for q, p in self.calls if q == query]

    def last(self, query):
        found = self.params(query)
        return found[-1] if found else None


class FakeClassifier:
    def __init__(self):
        self.calls = []
        self.result = police_result()

    def classify(self, chat_id, message, url):
        self.calls.append({"chatId": chat_id, "message": message, "url": url})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeAgent:
    """answer is (ok, reason, retryable), or a list of them to answer one per send."""

    def __init__(self):
        self.sent = []
        self.answer = (True, "", False)

    def send(self, envelope):
        self.sent.append(envelope)
        if isinstance(self.answer, list):
            return self.answer.pop(0)
        return self.answer