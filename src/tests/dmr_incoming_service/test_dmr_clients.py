"""HTTP clients: failures come back with readable reasons, never with request bodies."""

from unittest.mock import MagicMock

import pytest
import requests

from dmr_incoming_service.clients import (
    ClassifyClient,
    DmrAgentClient,
    ResqlClient,
    ResqlError,
)


def response(status, body=None, text=""):
    mock = MagicMock(
        status_code=status, text=text, content=b"x" if body is not None else b""
    )
    mock.json.return_value = body
    return mock


def session(answer):
    mock = MagicMock()
    if isinstance(answer, Exception):
        mock.post.side_effect = answer
    else:
        mock.post.return_value = answer
    return mock


def test_resql_returns_rows_and_posts_to_the_query_url():
    s = session(response(200, [{"id": 1}]))
    client = ResqlClient("http://resql:8082/global-classifier/", 5, s)

    assert client.call("get-agency", {"agencyId": "a"}) == [{"id": 1}]
    assert s.post.call_args.args[0] == "http://resql:8082/global-classifier/get-agency"
    assert s.post.call_args.kwargs["timeout"] == 5


def test_resql_errors_raise_resql_error():
    for answer in (requests.Timeout(), requests.ConnectionError(), response(500, [])):
        with pytest.raises(ResqlError):
            ResqlClient("http://resql", 5, session(answer)).call("q", {})


def test_resql_empty_body_is_no_rows():
    assert ResqlClient("http://resql", 5, session(response(200))).call("q", {}) == []


def test_classify_success_and_failures():
    rows = [[{"agency_id": "p", "agency_name": "Police", "confidence": 0.9}]]
    ok = ClassifyClient(
        "http://c", 30, session(response(200, {"response": rows}))
    ).classify("chat", "q", "")
    assert ok.ok and ok.top["agency_id"] == "p"

    cases = [
        (response(503, "No production model"), "classify returned HTTP 503"),
        (requests.Timeout(), "classify timed out"),
        (requests.ConnectionError(), "classify unreachable: ConnectionError"),
        (response(200, {"response": []}), "classify returned an unexpected body"),
    ]
    for answer, reason in cases:
        result = ClassifyClient("http://c", 30, session(answer)).classify(
            "chat", "q", ""
        )
        assert not result.ok
        assert result.reason == reason


def test_agent_send_reasons():
    def send(answer):
        return DmrAgentClient("http://a", 10, session(answer)).send({})

    assert send(response(200)) == (True, "", False)
    assert send(response(400, {}, "x" * 500)) == (
        False,
        "HTTP 400: " + "x" * 200,
        False,
    )
    assert send(requests.ConnectionError()) == (
        False,
        "GC DMR agent unreachable: ConnectionError",
        True,
    )
    assert send(requests.Timeout()) == (False, "GC DMR agent timed out", True)


def test_agent_send_only_transient_failures_are_retryable():
    for status, retryable in (
        (500, True),
        (502, True),
        (503, True),
        (408, True),
        (429, True),
        (400, False),
        (401, False),
        (404, False),
    ):
        _, _, got = DmrAgentClient("http://a", 10, session(response(status))).send({})
        assert got is retryable, status
