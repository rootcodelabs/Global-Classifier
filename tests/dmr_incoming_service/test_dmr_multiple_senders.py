"""Several agencies sending at the same time: each result goes back to its own sender, on its own chat.
The processor is driven from plain threads here, the way FastAPI runs accept() and the background
tasks in its thread pool. The classifier waits on a barrier, so every classification is in flight
at once before any of them answers.
"""

import json
import threading

from dmr_incoming_service.clients import ClassifyResult
from dmr_test_helpers import make_envelope, new_id

CONCURRENT_SENDERS = 20
THREAD_TIMEOUT_SECONDS = 10


class AgencyPerQuestionClassifier:
    """Classifies each question to its own agency, so a result sent to the wrong sender shows up.
    With a barrier, every classify() waits until all of them have started.
    """

    def __init__(self, agency_for_question, barrier=None):
        self.agency_for_question = agency_for_question
        self.barrier = barrier
        self.calls = []

    def classify(self, chat_id, message, url):
        self.calls.append(chat_id)
        if self.barrier is not None:
            self.barrier.wait()
        agency_id = self.agency_for_question[message]
        top = {
            "agency_id": agency_id,
            "agency_name": f"Agency {agency_id[:8]}",
            "confidence": 0.9,
        }
        return ClassifyResult(ok=True, top=top, full=[[dict(top)]])


class PerRecipientAgent:
    """The GC DMR agent. Fails with a retryable 502 for the recipients in `failing`."""

    def __init__(self, failing=()):
        self.failing = set(failing)
        self.sent = []
        self._lock = threading.Lock()

    def send(self, envelope):
        with self._lock:
            self.sent.append(envelope)
        if envelope["recipientId"] in self.failing:
            return False, "HTTP 502: bad gateway", True
        return True, "", False


def use_unique_response_ids(resql):
    """Makes the fake insert hand out a new response_message_id per message, like the table does."""
    response_ids = {}
    lock = threading.Lock()

    def insert(params):
        with lock:
            response_ids[params["messageId"]] = new_id()
            return [
                {
                    "id": len(response_ids),
                    "responseMessageId": response_ids[params["messageId"]],
                }
            ]

    resql.answers["insert-dmr-incoming-message"] = insert
    return response_ids


def make_senders(count):
    """One agency per sender, each with its own chat, question and expected classified agency."""
    senders = []
    for number in range(count):
        sender_id = new_id()
        chat_id = new_id()
        question = f"Question {number} from agency {sender_id}"
        envelope = make_envelope(senderId=sender_id)
        envelope["payload"]["chat"]["id"] = chat_id
        for message in envelope["payload"]["messages"]:
            message["chatId"] = chat_id
        envelope["payload"]["messages"][-1]["content"] = question
        senders.append(
            {
                "sender": sender_id,
                "chat": chat_id,
                "question": question,
                "agency": new_id(),
                "envelope": envelope,
            }
        )
    return senders


def classifier_for(senders, barrier=None):
    return AgencyPerQuestionClassifier(
        {s["question"]: s["agency"] for s in senders}, barrier
    )


def receive(processor, envelope):
    """What one request to POST /dmr/incoming does: accept, then the background task."""
    status, body, job = processor.accept(envelope)
    assert (status, body["status"]) == (200, "accepted")
    processor.process(job)


def receive_all_at_once(processor, senders):
    start = threading.Event()
    errors = []

    def run(envelope):
        start.wait()
        try:
            receive(processor, envelope)
        except BaseException as error:  # surface assertion errors from the thread
            errors.append(error)

    threads = [
        threading.Thread(target=run, args=(s["envelope"],), daemon=True)
        for s in senders
    ]
    for thread in threads:
        thread.start()
    start.set()
    for thread in threads:
        thread.join(THREAD_TIMEOUT_SECONDS)
    assert not any(thread.is_alive() for thread in threads), "processing hung"
    assert errors == []


def assert_each_sender_got_its_own_result(senders, sent_envelopes, response_ids):
    assert len(sent_envelopes) == len(senders)
    by_recipient = {envelope["recipientId"]: envelope for envelope in sent_envelopes}
    assert set(by_recipient) == {s["sender"] for s in senders}, (
        "a sender got no result, or two results went to the same sender"
    )
    for s in senders:
        sent = by_recipient[s["sender"]]
        message = sent["payload"]["messages"][0]
        content = json.loads(message["content"])
        assert sent["id"] == response_ids[s["envelope"]["id"]]
        assert message["id"] == sent["id"]
        assert sent["payload"]["chat"]["id"] == s["chat"]
        assert message["chatId"] == s["chat"]
        assert content["requestMessageId"] == s["envelope"]["id"]
        assert content["status"] == "classified"
        assert content["agencyId"] == s["agency"]


def response_statuses(resql):
    return {
        p["messageId"]: p["responseStatus"]
        for p in resql.params("update-dmr-response-status")
    }


# ---- tests


def test_two_senders_interleaved_each_get_their_own_result(processor, resql):
    """Both accepted before either is processed, and processed in the opposite order."""
    response_ids = use_unique_response_ids(resql)
    agency_a, agency_b = make_senders(2)
    processor.classifier = classifier_for([agency_a, agency_b])
    processor.agent = agent = PerRecipientAgent()

    _, _, job_a = processor.accept(agency_a["envelope"])
    _, _, job_b = processor.accept(agency_b["envelope"])
    processor.process(job_b)
    processor.process(job_a)

    assert_each_sender_got_its_own_result(
        [agency_a, agency_b], agent.sent, response_ids
    )
    assert response_statuses(resql) == {
        agency_a["envelope"]["id"]: "SENT",
        agency_b["envelope"]["id"]: "SENT",
    }


def test_many_senders_at_once_each_get_their_own_result(processor, resql):
    response_ids = use_unique_response_ids(resql)
    senders = make_senders(CONCURRENT_SENDERS)
    # Every classify waits here until all of them are in flight. If processing were serialised,
    # the barrier would time out, the classify would fail and the results would say 'failed'.
    barrier = threading.Barrier(CONCURRENT_SENDERS, timeout=THREAD_TIMEOUT_SECONDS)
    processor.classifier = classifier = classifier_for(senders, barrier)
    processor.agent = agent = PerRecipientAgent()

    receive_all_at_once(processor, senders)

    assert sorted(classifier.calls) == sorted(s["chat"] for s in senders)
    assert_each_sender_got_its_own_result(senders, agent.sent, response_ids)
    assert response_statuses(resql) == {s["envelope"]["id"]: "SENT" for s in senders}
    closed = {
        p["messageId"]: p["status"] for p in resql.params("update-dmr-incoming-message")
    }
    assert closed == {s["envelope"]["id"]: "CLASSIFIED" for s in senders}
    assert processor._in_flight == set()


def test_one_unreachable_sender_does_not_affect_the_others(processor, resql, sleeps):
    response_ids = use_unique_response_ids(resql)
    senders = make_senders(5)
    unreachable = senders[2]
    processor.classifier = classifier_for(senders)
    processor.agent = agent = PerRecipientAgent(failing={unreachable["sender"]})

    receive_all_at_once(processor, senders)

    statuses = response_statuses(resql)
    assert statuses.pop(unreachable["envelope"]["id"]) == "PENDING"
    assert statuses == {
        s["envelope"]["id"]: "SENT" for s in senders if s is not unreachable
    }
    # The unreachable sender was tried 3 times; every other sender exactly once
    tries = [e["recipientId"] for e in agent.sent]
    assert tries.count(unreachable["sender"]) == 3
    for s in senders:
        if s is not unreachable:
            assert tries.count(s["sender"]) == 1
    delivered = [e for e in agent.sent if e["recipientId"] != unreachable["sender"]]
    others = [s for s in senders if s is not unreachable]
    assert_each_sender_got_its_own_result(others, delivered, response_ids)
