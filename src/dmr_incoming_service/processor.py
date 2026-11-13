"""DMR message handling: accept (before the ack), process (after the ack) and the stale-row sweeper.
The GC answers every usable chat message with one result message, sent back to the sender
through the GC's own DMR agent. Message content is never stored or logged.
"""

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from dmr_incoming_service.clients import (
    ClassifyClient,
    DmrAgentClient,
    ResqlClient,
    ResqlError,
)

logger = logging.getLogger("dmr_incoming_service")

CHAT_MESSAGE = "ChatMessage"
RESULT_EVENT = "global-classifier-result"
RESULT_AUTHOR_ROLE = "global-classifier"
END_USER_ROLE = "end-user"

# dmr_incoming_messages.status
RECEIVED = "RECEIVED"
CLASSIFIED = "CLASSIFIED"
REJECTED = "REJECTED"
FAILED = "FAILED"

# dmr_incoming_messages.response_status (FAILED is shared with status). PENDING: the last try
# failed with a transient error and the sweeper will send again; SENT, SKIPPED and FAILED are final.
SENT = "SENT"
SKIPPED = "SKIPPED"
PENDING = "PENDING"

# Result status, sent in the result message and stored as result_status
RESULT_CLASSIFIED = "classified"
RESULT_OUT_OF_DISTRIBUTION = "out_of_distribution"
RESULT_FAILED = "failed"

Q_INSERT = "insert-dmr-incoming-message"
Q_UPDATE = "update-dmr-incoming-message"
Q_RESPONSE = "update-dmr-response-status"
Q_STALE = "update-stale-dmr-incoming-messages-failed"
Q_UNANSWERED = "update-unanswered-dmr-incoming-messages"
Q_GET = "get-dmr-incoming-message"
Q_GET_AGENCY = "get-agency"

# Only the canonical 8-4-4-4-12 form, which both Postgres' uuid type and the agent's @IsUUID()
# accept. uuid.UUID() is looser (it ignores stray hyphens, underscores and whitespace), and an
# id Postgres then rejects would fail the insert on every redelivery.
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


@dataclass
class Job:
    """What process() needs from an accepted message. Lives only in memory."""

    message_id: str
    sender_id: str
    response_message_id: str
    chat_id: str = ""
    chat_created: str = ""
    message_type: str = ""
    chat_url: str = ""
    messages: list = field(default_factory=list)
    # Rounds of tries to send the result so far (from the row, for the sweeper's resends)
    response_attempts: int = 0


# --------------------------------------------------------------------------- helpers


def is_uuid(value) -> bool:
    return isinstance(value, str) and UUID_RE.fullmatch(value) is not None


def parse_envelope(body: bytes):
    """The request body as JSON, or None when it can never be parsed.
    Not JSON, not UTF-8, or nested too deep (json raises RecursionError, not ValueError).
    accept() answers None with 200 "ignored", so DMR doesn't redeliver it forever.
    """
    try:
        return json.loads(body)
    except Exception:
        return None


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_timestamp(value) -> str:
    """The envelope timestamp as ISO 8601, or "" when it isn't one, so the insert never fails on it."""
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _text(value, limit: int | None = None) -> str:
    """A string field for the database: NUL removed (Postgres text can't hold it), truncated."""
    if not isinstance(value, str):
        return ""
    value = value.replace("\x00", "")
    return value[:limit] if limit else value


def is_result_message(message) -> bool:
    return isinstance(message, dict) and message.get("event") == RESULT_EVENT


def extract_question(messages) -> str:
    """The latest end-user message with content, else the latest message with content.
    GC result messages are skipped.
    """
    if not isinstance(messages, list):
        return ""
    usable = [
        m
        for m in messages
        if isinstance(m, dict)
        and not is_result_message(m)
        and isinstance(m.get("content"), str)
        and m["content"].strip()
    ]
    for message in reversed(usable):
        if message.get("authorRole") == END_USER_ROLE:
            return message["content"].strip()
    return usable[-1]["content"].strip() if usable else ""


def result_status_for(top: dict | None) -> str:
    if not top:
        return RESULT_FAILED
    agency_id = top.get("agency_id")
    if (
        agency_id in (None, "", 0, "0")
        or top.get("agency_name") == RESULT_OUT_OF_DISTRIBUTION
    ):
        return RESULT_OUT_OF_DISTRIBUTION
    return RESULT_CLASSIFIED


def _confidence(top: dict | None):
    try:
        return float(top.get("confidence")) if top else ""
    except (TypeError, ValueError):
        return ""


def build_result_payload(
    chat_id: str,
    chat_created: str,
    response_message_id: str,
    request_message_id: str,
    result_status: str,
    top: dict | None,
    timestamp: str,
) -> dict:
    """Minimal payload: the chat's id and created, and one result message. No original messages."""
    classified = result_status == RESULT_CLASSIFIED and top is not None
    content = {
        "requestMessageId": request_message_id,
        "status": result_status,
        "agencyId": str(top.get("agency_id")) if classified else "",
        "agencyName": str(top.get("agency_name") or "") if classified else "",
        "confidence": _confidence(top) if classified else "",
    }
    return {
        "chat": {"id": chat_id, "created": chat_created},
        "messages": [
            {
                "id": response_message_id,
                "chatId": chat_id,
                "authorRole": RESULT_AUTHOR_ROLE,
                "authorTimestamp": timestamp,
                "event": RESULT_EVENT,
                "content": json.dumps(
                    content, ensure_ascii=False, separators=(",", ":")
                ),
            }
        ],
    }


def _answerable(job: "Job") -> bool:
    """Whether a valid result message can be built for this job (the agent DTO needs these).
    recipientId (the sender) must be a UUID; chat.created only has to be a non-empty string.
    """
    return (
        job.message_type == CHAT_MESSAGE
        and is_uuid(job.chat_id)
        and bool(job.chat_created)
        and is_uuid(job.sender_id)
        and is_uuid(job.response_message_id)
    )


def build_envelope(
    recipient_id: str, response_message_id: str, payload: dict, timestamp: str
) -> dict:
    """Body for the agent's POST /v1/messages. The agent adds senderId (the GC) itself."""
    return {
        "id": response_message_id,
        "recipientId": recipient_id,
        "timestamp": timestamp,
        "type": CHAT_MESSAGE,
        "payload": payload,
    }


# --------------------------------------------------------------------------- processor


class Processor:
    def __init__(
        self,
        resql: ResqlClient,
        classifier: ClassifyClient,
        agent: DmrAgentClient,
        gc_agent_id: str,
        stale_after_seconds: int = 300,
        send_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
        resend_after_seconds: int = 120,
        max_response_attempts: int = 5,
        sleep=time.sleep,
    ):
        self.resql = resql
        self.classifier = classifier
        self.agent = agent
        self.gc_agent_id = (gc_agent_id or "").strip().lower()
        self.stale_after_seconds = stale_after_seconds
        self.send_attempts = max(1, send_attempts)
        self.retry_delay_seconds = retry_delay_seconds
        self.resend_after_seconds = resend_after_seconds
        self.max_response_attempts = max(1, max_response_attempts)
        self._sleep = sleep
        # Message ids being processed right now. In-process, so the service runs one worker.
        self._in_flight: set[str] = set()
        self._lock = threading.Lock()

    # ---- before the ack

    def accept(self, envelope) -> tuple[int, dict, Job | None]:
        """Records the message and returns (HTTP status, body, job to process or None).
        200 for everything except a failed insert, so DMR only redelivers when a retry can help.
        """
        if not isinstance(envelope, dict):
            return (
                200,
                {"status": "ignored", "reason": "body is not a JSON object"},
                None,
            )
        message_id = envelope.get("id")
        if not is_uuid(message_id):
            return 200, {"status": "ignored", "reason": "id is not a UUID"}, None
        sender_id = envelope.get("senderId")
        # The result goes back to the sender as recipientId, which the agent requires to be a UUID
        if not is_uuid(sender_id):
            return (
                200,
                {"status": "ignored", "reason": "senderId missing or not a UUID"},
                None,
            )

        payload = (
            envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
        )
        chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
        messages = (
            payload.get("messages") if isinstance(payload.get("messages"), list) else []
        )
        chat_id = _text(chat.get("id"), 255)
        chat_created = _text(chat.get("created"), 100)
        message_type = _text(envelope.get("type"), 50)

        try:
            rows = self.resql.call(
                Q_INSERT,
                {
                    "messageId": message_id,
                    "senderId": sender_id,
                    "recipientId": _text(envelope.get("recipientId"), 255),
                    "chatId": chat_id,
                    "chatCreated": chat_created,
                    "messageType": message_type,
                    "sentAt": parse_timestamp(envelope.get("timestamp")),
                },
            )
        except ResqlError as error:
            logger.error(
                "DMR message %s not recorded, DMR will redeliver: %s", message_id, error
            )
            return (
                500,
                {"status": "error", "reason": "could not record the message"},
                None,
            )

        if rows:
            response_message_id = str(rows[0].get("responseMessageId") or "")
            self._claim(message_id)
            logger.info(
                "DMR message %s from %s accepted (chat %s)",
                message_id,
                sender_id,
                chat_id,
            )
        else:
            response_message_id = self._resumable(message_id)
            if response_message_id is None:
                logger.info(
                    "DMR message %s from %s is a duplicate", message_id, sender_id
                )
                return 200, {"status": "duplicate", "messageId": message_id}, None
            logger.warning(
                "DMR message %s from %s was recorded but never processed, resuming",
                message_id,
                sender_id,
            )

        job = Job(
            message_id=message_id,
            sender_id=sender_id,
            response_message_id=response_message_id,
            chat_id=chat_id,
            chat_created=chat_created,
            message_type=message_type,
            chat_url=_text(chat.get("endUserUrl")),
            messages=messages,
        )
        return 200, {"status": "accepted", "messageId": message_id}, job

    def _claim(self, message_id: str) -> bool:
        """Marks a message as being processed in this process. False if it already is."""
        with self._lock:
            if message_id in self._in_flight:
                return False
            self._in_flight.add(message_id)
            return True

    def _release(self, message_id: str) -> None:
        with self._lock:
            self._in_flight.discard(message_id)

    def _resumable(self, message_id: str) -> str | None:
        """For a duplicate: the response_message_id if the row was recorded but never processed.
        This happens when the insert timed out here but still landed in the database (e.g. the
        database came back while Resql was waiting): this service answered 500, DMR redelivered,
        and the redelivery hits the dedupe. The redelivered envelope has the full payload, so the
        message can still be processed. Not when it is being processed right now (normal
        redelivery during a slow classify) or already closed.
        """
        try:
            row = self.get_status(message_id)
        except ResqlError as error:
            logger.error(
                "DMR message %s: duplicate check failed: %s", message_id, error
            )
            return None
        if not row or row.get("status") != RECEIVED:
            return None
        response_message_id = str(row.get("responseMessageId") or "")
        if not is_uuid(response_message_id) or not self._claim(message_id):
            return None
        return response_message_id

    # ---- after the ack

    def process(self, job: Job) -> None:
        """Classifies and answers. Never raises: every outcome is recorded on the row."""
        try:
            self._process(job)
        except Exception as error:  # the background task must not die silently
            self._fail(job, error)
        finally:
            self._release(job.message_id)

    def _fail(self, job: Job, error: Exception) -> None:
        """Records an unexpected error as FAILED and answers 'failed' when possible."""
        reason = f"internal error: {type(error).__name__}"
        logger.error("DMR message %s: %s", job.message_id, reason)
        try:
            closed = self._record(job, FAILED, reason, result_status=RESULT_FAILED)
            if closed and _answerable(job):
                self._respond(job, RESULT_FAILED, None)
            elif closed:
                self._response_status(job, SKIPPED, "no usable chat to answer")
        except Exception as inner:
            logger.error(
                "DMR message %s: could not record the failure: %s",
                job.message_id,
                type(inner).__name__,
            )

    def _process(self, job: Job) -> None:
        if job.message_type != CHAT_MESSAGE:
            return self._reject(
                job, f"unsupported message type: {job.message_type or '-'}"
            )
        if not is_uuid(job.chat_id):
            return self._reject(job, "chat id missing or not a UUID")
        if not job.chat_created:
            return self._reject(job, "chat created missing")
        if job.messages and is_result_message(job.messages[-1]):
            # Echo guard: the sender sent our own result back
            return self._reject(job, "already classified")
        question = extract_question(job.messages)
        if not question:
            return self._reject(job, "no message content")

        sender_known = self._sender_known(job.sender_id)
        result = self.classifier.classify(job.chat_id, question, job.chat_url)
        if result.ok:
            result_status = result_status_for(result.top)
            claimed = self._record(
                job,
                CLASSIFIED,
                "",
                sender_known=sender_known,
                result_status=result_status,
                top=result.top,
                classification=result.full,
            )
        else:
            result_status = RESULT_FAILED
            claimed = self._record(
                job,
                FAILED,
                result.reason,
                sender_known=sender_known,
                result_status=result_status,
            )
        logger.info(
            "DMR message %s: %s, top agency %s",
            job.message_id,
            result_status,
            (result.top or {}).get("agency_id", "-"),
        )
        if not claimed:
            logger.warning(
                "DMR message %s was already closed by the sweeper, no result sent",
                job.message_id,
            )
            return
        self._respond(job, result_status, result.top)

    def _reject(self, job: Job, reason: str) -> None:
        logger.info("DMR message %s rejected: %s", job.message_id, reason)
        self._record(job, REJECTED, reason)

    def _sender_known(self, sender_id: str) -> bool:
        try:
            return bool(self.resql.call(Q_GET_AGENCY, {"agencyId": sender_id}))
        except ResqlError:
            return False

    def _record(
        self,
        job: Job,
        status: str,
        reason: str,
        sender_known: bool | None = None,
        result_status: str = "",
        top: dict | None = None,
        classification=None,
    ) -> bool:
        """Closes a RECEIVED row. False when the row was no longer RECEIVED (the sweeper got it)."""
        confidence = _confidence(top)
        rows = self.resql.call(
            Q_UPDATE,
            {
                "messageId": job.message_id,
                "status": status,
                "errorReason": reason,
                "senderKnown": sender_known,
                "resultStatus": result_status,
                "topAgencyId": str(top.get("agency_id", "")) if top else "",
                "topAgencyName": str(top.get("agency_name") or "")[:255] if top else "",
                "topConfidence": "" if confidence == "" else str(confidence),
                "classification": json.dumps(classification)
                if classification is not None
                else "",
            },
        )
        return bool(rows)

    def _respond(
        self, job: Job, result_status: str, top: dict | None, tries: int | None = None
    ) -> None:
        """Sends the result to the sender and records the response status.
        A transient failure is retried `tries` times in a row with backoff. If it still fails,
        the response is PENDING and the sweeper sends it again later, until
        max_response_attempts rounds are used up; then it is FAILED for good.
        """
        if job.sender_id.strip().lower() == self.gc_agent_id:
            self._response_status(job, SKIPPED, "sender is the GC")
            return
        timestamp = now_iso()
        payload = build_result_payload(
            chat_id=job.chat_id,
            chat_created=job.chat_created,
            response_message_id=job.response_message_id,
            request_message_id=job.message_id,
            result_status=result_status,
            top=top,
            timestamp=timestamp,
        )
        # The same envelope id on every try and resend, so the receiver can drop duplicates
        envelope = build_envelope(
            job.sender_id, job.response_message_id, payload, timestamp
        )
        ok, reason, retryable = self._send(envelope, tries or self.send_attempts)
        if ok:
            status = SENT
        elif retryable and job.response_attempts + 1 < self.max_response_attempts:
            status = PENDING
        else:
            status = FAILED
        self._response_status(job, status, reason)
        if status == FAILED:
            # ERROR on purpose: the alert hook for a sender that gets no answer
            logger.error(
                "DMR message %s: result %s to %s FAILED for good (%s)",
                job.message_id,
                result_status,
                job.sender_id,
                reason,
            )
        else:
            logger.info(
                "DMR message %s: result %s to %s %s%s",
                job.message_id,
                result_status,
                job.sender_id,
                status,
                "" if ok else f" ({reason}), will send again",
            )

    def _send(self, envelope: dict, tries: int) -> tuple[bool, str, bool]:
        delay = self.retry_delay_seconds
        for attempt in range(1, tries + 1):
            ok, reason, retryable = self.agent.send(envelope)
            if ok or not retryable or attempt == tries:
                return ok, reason, retryable
            self._sleep(delay)
            delay *= 2
        return False, "not sent", True  # unreachable: tries >= 1

    def _response_status(self, job: Job, status: str, reason: str) -> None:
        self.resql.call(
            Q_RESPONSE,
            {
                "messageId": job.message_id,
                "responseStatus": status,
                "responseError": reason,
            },
        )

    # ---- sweeper

    def sweep(self) -> None:
        """One sweeper pass: close stuck rows, then send results that never got through."""
        self.sweep_stale()
        self.sweep_unanswered()

    def sweep_stale(self) -> int:
        """Closes rows stuck in RECEIVED (acked, never processed) and answers them with 'failed'.
        The claim is one atomic UPDATE, and process() only closes RECEIVED rows, so a slow
        process() and the sweeper never both send a result.
        """
        try:
            rows = self.resql.call(
                Q_STALE, {"olderThanSeconds": self.stale_after_seconds}
            )
        except ResqlError as error:
            logger.error("DMR sweeper could not check for stale messages: %s", error)
            return 0
        for row in rows:
            message_id = str(row.get("messageId"))
            # ERROR on purpose: this is the alert hook for messages acked but never processed
            logger.error(
                "stale DMR message %s marked FAILED (processing interrupted)",
                message_id,
            )
            job = Job(
                message_id=message_id,
                sender_id=str(row.get("senderId") or ""),
                response_message_id=str(row.get("responseMessageId") or ""),
                chat_id=str(row.get("chatId") or ""),
                chat_created=str(row.get("chatCreated") or ""),
                message_type=str(row.get("messageType") or ""),
            )
            try:
                if _answerable(job):
                    # One try: if it fails, sweep_unanswered sends it again on a later pass
                    self._respond(job, RESULT_FAILED, None, tries=1)
                else:
                    self._response_status(job, SKIPPED, "no usable chat to answer")
            except Exception as error:
                logger.error(
                    "stale DMR message %s: could not send the failed result: %s",
                    message_id,
                    type(error).__name__,
                )
        return len(rows)

    def sweep_unanswered(self) -> int:
        """Sends results that were never delivered: closed rows whose response is unset or PENDING.
        This covers a crash between closing the row and sending, a close that timed out here
        but committed, and a send that failed with a transient error. The claim moves
        response_attempted_at in one atomic UPDATE, so a row is resent at most once per
        resend_after_seconds. The result is rebuilt from the stored classification, with the
        same envelope id as the first try.
        """
        try:
            rows = self.resql.call(
                Q_UNANSWERED, {"olderThanSeconds": self.resend_after_seconds}
            )
        except ResqlError as error:
            logger.error("DMR sweeper could not check for unsent results: %s", error)
            return 0
        sent = 0
        for row in rows:
            message_id = str(row.get("messageId"))
            with self._lock:
                in_flight = message_id in self._in_flight
            if in_flight:
                continue  # process() is still on it and records the outcome itself
            job = Job(
                message_id=message_id,
                sender_id=str(row.get("senderId") or ""),
                response_message_id=str(row.get("responseMessageId") or ""),
                chat_id=str(row.get("chatId") or ""),
                chat_created=str(row.get("chatCreated") or ""),
                message_type=str(row.get("messageType") or ""),
                response_attempts=int(row.get("responseAttempts") or 0),
            )
            result_status = str(row.get("resultStatus") or RESULT_FAILED)
            top = None
            if row.get("topAgencyId"):
                top = {
                    "agency_id": row.get("topAgencyId"),
                    "agency_name": row.get("topAgencyName"),
                    "confidence": row.get("topConfidence"),
                }
            logger.warning(
                "DMR message %s: result %s not delivered yet, sending again (round %d of %d)",
                message_id,
                result_status,
                job.response_attempts + 1,
                self.max_response_attempts,
            )
            try:
                if _answerable(job):
                    self._respond(job, result_status, top, tries=1)
                    sent += 1
                else:
                    self._response_status(job, SKIPPED, "no usable chat to answer")
            except Exception as error:
                logger.error(
                    "DMR message %s: could not send the result again: %s",
                    message_id,
                    type(error).__name__,
                )
        return sent

    # ---- status

    def get_status(self, message_id: str) -> dict | None:
        """The row for GET /dmr/messages/{id}. Raises ResqlError when Resql fails."""
        if not is_uuid(message_id):
            return None
        rows = self.resql.call(Q_GET, {"messageId": message_id})
        return rows[0] if rows else None
