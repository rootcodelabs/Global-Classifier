"""HTTP clients for Resql, /chats/classify and the GC's own DMR agent.
Classify and agent failures come back as values with a readable reason, so the processor can
record why something failed. Resql failures raise ResqlError. No client logs request bodies.
"""

from dataclasses import dataclass
from typing import Any

import requests

JSON_HEADERS = {"Content-Type": "application/json"}


class ResqlError(Exception):
    """Resql could not run a query: unreachable, timed out or answered with an error status."""


class ResqlClient:
    def __init__(
        self, base_url: str, timeout: float, session: requests.Session | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def call(self, query: str, params: dict) -> list[dict]:
        """POSTs to {RESQL}/{query} and returns the rows (camelCase keys)."""
        try:
            response = self.session.post(
                f"{self.base_url}/{query}",
                json=params,
                headers=JSON_HEADERS,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise ResqlError(f"resql {query} timed out") from error
        except requests.RequestException as error:
            raise ResqlError(
                f"resql {query} unreachable: {type(error).__name__}"
            ) from error
        if response.status_code not in (200, 201):
            raise ResqlError(f"resql {query} returned HTTP {response.status_code}")
        if not response.content:
            return []
        try:
            rows = response.json()
        except ValueError as error:
            raise ResqlError(
                f"resql {query} returned a body that is not JSON"
            ) from error
        return rows if isinstance(rows, list) else []


@dataclass
class ClassifyResult:
    ok: bool
    top: dict | None = None
    full: Any = None
    reason: str = ""


def top_from_classify(body: Any) -> tuple[dict | None, Any]:
    """Returns (top result, full result) from a /chats/classify body.
    Ruuter wraps a DSL's return value as {"response": ...}; a bare list is accepted too.
    The result is a list per input text, each a list of {agency_id, agency_name, confidence}.
    """
    if isinstance(body, dict) and "response" in body:
        body = body["response"]
    if (
        isinstance(body, list)
        and body
        and isinstance(body[0], list)
        and body[0]
        and isinstance(body[0][0], dict)
    ):
        return body[0][0], body
    return None, body


class ClassifyClient:
    def __init__(
        self, url: str, timeout: float, session: requests.Session | None = None
    ):
        self.url = url
        self.timeout = timeout
        self.session = session or requests.Session()

    def classify(self, chat_id: str, message: str, url: str) -> ClassifyResult:
        try:
            response = self.session.post(
                self.url,
                json={"chatId": chat_id, "message": message, "url": url},
                headers=JSON_HEADERS,
                timeout=self.timeout,
            )
        except requests.Timeout:
            return ClassifyResult(ok=False, reason="classify timed out")
        except requests.RequestException as error:
            return ClassifyResult(
                ok=False, reason=f"classify unreachable: {type(error).__name__}"
            )
        if response.status_code != 200:
            return ClassifyResult(
                ok=False, reason=f"classify returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError:
            return ClassifyResult(
                ok=False, reason="classify returned a body that is not JSON"
            )
        top, full = top_from_classify(body)
        if top is None:
            return ClassifyResult(
                ok=False, reason="classify returned an unexpected body"
            )
        return ClassifyResult(ok=True, top=top, full=full)


class DmrAgentClient:
    def __init__(
        self, send_url: str, timeout: float, session: requests.Session | None = None
    ):
        self.send_url = send_url
        self.timeout = timeout
        self.session = session or requests.Session()

    def send(self, envelope: dict) -> tuple[bool, str, bool]:
        """POSTs to the agent's /v1/messages. Returns (ok, reason, retryable).
        2xx means the DMR server has queued the message. Timeouts, connection errors, 408, 429
        and 5xx are retryable (the agent or the DMR server may be down for a while). Other 4xx
        are validation failures: sending the same body again can't succeed.
        """
        try:
            response = self.session.post(
                self.send_url, json=envelope, headers=JSON_HEADERS, timeout=self.timeout
            )
        except requests.Timeout:
            return False, "GC DMR agent timed out", True
        except requests.RequestException as error:
            return False, f"GC DMR agent unreachable: {type(error).__name__}", True
        status = response.status_code
        if 200 <= status < 300:
            return True, "", False
        retryable = status >= 500 or status in (408, 429)
        # The agent's error body is a validation or delivery message, never the payload
        return False, f"HTTP {status}: {response.text[:200]}", retryable
