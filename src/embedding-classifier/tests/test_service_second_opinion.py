"""
Contract tests of the second opinion in the service, with a fake model server.
"""

import json
import time
from contextlib import ExitStack
from dataclasses import replace

import pytest
import requests
from fastapi.testclient import TestClient

from embedding_classifier import second_opinion as so
from embedding_classifier.output import OOD_AGENCY_NAME
from service.app import create_app
from service.build_files import LocalBuildFiles
from service.registry import IndexRegistry
from service.second_opinion import SecondOpinion, SecondOpinionSettings
from tests.conftest import FakeEncoder
from tests.test_second_opinion import chat_response
from tests.test_service import CLASSIFY_YML_BODY, build, parse, qdrant  # noqa: F401

INFER = "/v2/models/42-classifier-ensemble/infer"
BATCH_BODY = {
    "inputs": [
        {
            "name": "TEXT",
            "datatype": "BYTES",
            "shape": [2, 1],
            "data": [["Kuidas pass taotleda?"], ["Smart-ID ei tööta"]],
        }
    ]
}


class FakeModelServer:
    """Answers like llama-server, or times out, fails, or takes its time."""

    def __init__(self, letter="B", probability=0.9, delay=0.0, fail=None):
        self.letter, self.probability = letter, probability
        self.delay, self.fail = delay, fail
        self.calls = []

    def __call__(self, url, body, timeout):
        self.calls.append({"url": url, "body": body, "timeout": timeout})
        if self.delay:
            time.sleep(self.delay)
        if self.fail == "timeout":
            raise requests.Timeout("read timed out")
        if self.fail == "error":
            raise requests.HTTPError("500 Server Error")
        rest = [x for x in "ABCN" if x != self.letter]
        probabilities = {self.letter: self.probability}
        probabilities.update({x: (1 - self.probability) / 3 for x in rest})
        return chat_response(self.letter, probabilities)


def settings(mode="on", warm_up=False, triggers=so.TRIGGERS, **kwargs):
    """
    Without the warm-up, unless a test asks for it, so call counts are the
    messages'; both triggers, so clarify messages are asked about too.
    """
    return SecondOpinionSettings(
        mode=mode,
        url="http://llm-reranker:8080",
        warm_up=warm_up,
        triggers=triggers,
        **kwargs,
    )


def catalogue_numbers(prompt):
    """Agency name -> its number in the prompt's catalogue."""
    numbers = {}
    for line in prompt.split("\n"):
        number, dot, name = line.partition(". ")
        if dot and number.isdigit():
            numbers[name] = int(number)
    return numbers


def drain(second_opinion):
    """Wait until the warm-ups queued so far have run."""
    second_opinion._warm_pool.submit(lambda: None).result()


@pytest.fixture
def built(tmp_path, qdrant, questions):  # noqa: F811
    build(tmp_path, qdrant, questions)
    return tmp_path, qdrant


@pytest.fixture
def start():
    """Starts services with model 42 loaded and its gate adjusted; stops them after the test."""
    with ExitStack() as stack:

        def started(models_dir, store, second_opinion=None, **gate):
            registry = IndexRegistry(
                store=store,
                files=LocalBuildFiles(str(models_dir)),
                index_env="testing",
                encoder_factory=lambda model: FakeEncoder(),
                models={"fake": FakeEncoder.model},
                second_opinion=second_opinion,
            )
            client = stack.enter_context(
                TestClient(create_app(registry, start_in_background=False))
            )
            load = client.post("/v2/repository/models/42-classifier-ensemble/load")
            assert load.status_code == 200
            index = registry._indexes["42"]
            index.gate = replace(index.gate, **gate)
            return client

        yield started


def decision(response):
    return json.loads(response.json()["outputs"][1]["data"][0])


# Every message that isn't off-topic is clarify
CLARIFY_ALL = {"route_margin": None}
# Every message is off-topic, and within the band below
OFF_TOPIC_ALL = {"ood_cutoff": 2.0}


@pytest.mark.parametrize("gate", [{}, CLARIFY_ALL, OFF_TOPIC_ALL])
def test_mode_off_is_byte_for_byte_the_same(built, start, gate):
    server = FakeModelServer()
    without = start(*built, **gate)
    off = start(*built, SecondOpinion(settings("off"), post=server), **gate)

    for body in (CLASSIFY_YML_BODY, BATCH_BODY):
        assert (
            off.post(INFER, json=body).content == without.post(INFER, json=body).content
        )
    assert server.calls == []


def test_on_moves_the_pick_of_a_clarify_first(built, start):
    # A weight high enough that the model's answer outweighs any gap in e5's confidences
    server = FakeModelServer("B", 0.9)
    before = start(*built, **CLARIFY_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    after = start(
        *built, SecondOpinion(settings(weight=10), post=server), **CLARIFY_ALL
    ).post(INFER, json=CLASSIFY_YML_BODY)

    old, new = parse(before)[0], parse(after)[0]
    second = old[1]["agency_id"]
    assert new[0]["agency_id"] == second
    assert [p["confidence"] for p in new] == [p["confidence"] for p in old]
    record = decision(after)[0]
    assert record["decision"] == "clarify"
    assert record["candidates"][0] == second
    assert record["second_opinion"]["pick"] == second
    assert record["second_opinion"]["applied"] is True
    assert record["second_opinion"]["outcome"] == "ok"

    # What the model was sent: the build's catalogue, the message, e5's top 3 by
    # catalogue number, the forced letters
    sent = server.calls[0]
    assert sent["url"] == "http://llm-reranker:8080/v1/chat/completions"
    assert sent["timeout"] == 5.0
    assert "id_slot" not in sent["body"]
    prompt = sent["body"]["messages"][0]["content"]
    assert prompt.startswith(so.CATALOGUE_HEADER)
    assert "Message: Kuidas pass taotleda?" in prompt
    numbers = catalogue_numbers(prompt)
    options = "  ".join(
        f"{letter}) {numbers[p['agency_name']]}" for letter, p in zip("ABC", old)
    )
    assert f"{options}  N) none" in prompt.split("\n")
    assert sent["body"]["grammar"] == 'root ::= "A" | "B" | "C" | "N"'


def test_weight_zero_keeps_e5s_order(built, start):
    server = FakeModelServer("B", 0.99)
    before = start(*built, **CLARIFY_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    after = start(
        *built, SecondOpinion(settings(weight=0), post=server), **CLARIFY_ALL
    ).post(INFER, json=CLASSIFY_YML_BODY)

    assert parse(after) == parse(before)
    assert decision(after)[0]["second_opinion"]["applied"] is False
    assert len(server.calls) == 1


def test_the_slot_is_sent(built, start):
    server = FakeModelServer("A", 0.9)
    start(*built, SecondOpinion(settings(slot=1), post=server), **CLARIFY_ALL).post(
        INFER, json=CLASSIFY_YML_BODY
    )
    assert server.calls[0]["body"]["id_slot"] == 1


def test_a_load_sends_the_catalogue_once_in_the_background(built, start):
    server = FakeModelServer("A", 0.9)
    second_opinion = SecondOpinion(settings(warm_up=True, slot=0), post=server)
    client = start(*built, second_opinion, **CLARIFY_ALL)
    drain(second_opinion)

    warm = server.calls[0]
    assert len(server.calls) == 1
    assert warm["timeout"] == second_opinion.settings.warm_up_timeout_s
    assert warm["body"]["id_slot"] == 0
    warm_prompt = warm["body"]["messages"][0]["content"]
    assert "Message: warm-up" in warm_prompt

    client.post(INFER, json=CLASSIFY_YML_BODY)
    prompt = server.calls[1]["body"]["messages"][0]["content"]
    # The message's prompt starts with exactly what the warm-up sent, so the server reuses it
    shared = warm_prompt[: warm_prompt.index("Message: ")]
    assert prompt.startswith(shared)


@pytest.mark.parametrize("failure", ["timeout", "error"])
def test_a_timeout_or_error_sends_the_catalogue_again(built, start, failure):
    server = FakeModelServer("A", 0.9, fail=failure)
    second_opinion = SecondOpinion(
        settings(warm_up=True, rewarm_after_s=0), post=server
    )
    client = start(*built, second_opinion, **CLARIFY_ALL)
    drain(second_opinion)

    after = client.post(INFER, json=CLASSIFY_YML_BODY)
    drain(second_opinion)

    assert decision(after)[0]["second_opinion"]["outcome"] == failure
    prompts = [c["body"]["messages"][0]["content"] for c in server.calls]
    assert len(prompts) == 3  # warm-up, the message, warm-up again
    assert "Message: warm-up" in prompts[0] and "Message: warm-up" in prompts[2]


def test_a_warm_up_retries_until_the_server_answers(built, start):
    """In compose the classifier can be up before the model server."""
    answers = FakeModelServer("A", 0.9)
    calls = []

    def starting_server(url, body, timeout):
        calls.append(body)
        if len(calls) < 3:
            raise requests.ConnectionError("connection refused")
        return answers(url, body, timeout)

    second_opinion = SecondOpinion(
        settings(warm_up=True, warm_up_retry_s=0), post=starting_server
    )
    start(*built, second_opinion, **CLARIFY_ALL)
    drain(second_opinion)

    assert len(calls) == 3
    assert len(answers.calls) == 1


def test_on_rescues_a_borderline_off_topic_message(built, start):
    # Above the default min_probability of 0.9
    server = FakeModelServer("A", 0.95)
    gate = {"ood_cutoff": 2.0}
    rescued = start(
        *built, SecondOpinion(settings(ood_band=1.5), post=server), **gate
    ).post(INFER, json=CLASSIFY_YML_BODY)

    predictions = parse(rescued)[0]
    assert all(p["agency_name"] != OOD_AGENCY_NAME for p in predictions)
    record = decision(rescued)[0]
    assert record["decision"] == "clarify"
    assert len(record["candidates"]) == 3
    assert record["second_opinion"]["applied"] is True


def test_a_plainly_off_topic_message_is_not_asked_about(built, start):
    server = FakeModelServer("A", 0.9)
    before = start(*built, **OFF_TOPIC_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    after = start(
        *built, SecondOpinion(settings(ood_band=0.01), post=server), **OFF_TOPIC_ALL
    ).post(INFER, json=CLASSIFY_YML_BODY)

    assert server.calls == []
    assert after.content == before.content


@pytest.mark.parametrize("failure", ["timeout", "error", "busy"])
def test_timeout_error_or_busy_leave_the_output_unchanged(built, start, failure):
    server = FakeModelServer("B", 0.9, fail=None if failure == "busy" else failure)
    second_opinion = SecondOpinion(settings(), post=server)
    before = start(*built, **CLARIFY_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    client = start(*built, second_opinion, **CLARIFY_ALL)

    if failure == "busy":
        # Another call holds the only slot
        second_opinion._slots.acquire()
    try:
        after = client.post(INFER, json=CLASSIFY_YML_BODY)
    finally:
        if failure == "busy":
            second_opinion._slots.release()

    assert parse(after) == parse(before)
    record = decision(after)[0]
    old_record = decision(before)[0]
    assert {k: v for k, v in record.items() if k != "second_opinion"} == old_record
    assert record["second_opinion"] == {
        "pick": None,
        "probability": None,
        "applied": False,
        "ms": record["second_opinion"]["ms"],
        "outcome": failure,
    }
    assert len(server.calls) == (0 if failure == "busy" else 1)


def test_shadow_changes_no_output_and_adds_no_delay(built, start):
    server = FakeModelServer("B", 0.9, delay=1.0)
    shadow = SecondOpinion(settings("shadow"), post=server)
    before = start(*built, **CLARIFY_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    client = start(*built, shadow, **CLARIFY_ALL)

    started = time.perf_counter()
    after = client.post(INFER, json=CLASSIFY_YML_BODY)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
    assert after.content == before.content
    shadow._background.shutdown(wait=True)
    assert len(server.calls) == 1


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        SecondOpinion(settings("maybe"))


def test_an_unknown_trigger_is_refused():
    with pytest.raises(ValueError):
        SecondOpinion(settings(triggers=("clarify", "always")))


def test_only_the_chosen_triggers_are_asked_about(built, start):
    server = FakeModelServer("B", 0.9)
    before = start(*built, **CLARIFY_ALL).post(INFER, json=CLASSIFY_YML_BODY)
    after = start(
        *built,
        SecondOpinion(settings(triggers=("ood_band",), weight=10), post=server),
        **CLARIFY_ALL,
    ).post(INFER, json=CLASSIFY_YML_BODY)

    assert server.calls == []
    assert after.content == before.content
