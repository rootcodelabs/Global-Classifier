"""
The service side of the second opinion (docs/ARCHITECTURE.md):
asks the llm-reranker about unsure messages within a time limit, one call at
a time, and applies the answer (mode on) or only logs it (mode shadow). The
prompt and the rules come from embedding_classifier.second_opinion.

Each build's catalogue (the prompt's fixed opening) is sent once after the
build loads, so the model server has read it before the first citizen's
message; until then calls time out and e5's answer stands. Pinning a service
to its own server slot keeps production's and testing's catalogues from
pushing each other out.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

import requests
from loguru import logger

from embedding_classifier import second_opinion as so
from embedding_classifier.gate import Decision, GateParams, ranking
from embedding_classifier.scoring import Scores
from embedding_classifier.store import Agency

CHAT_COMPLETIONS = "/v1/chat/completions"
WARM_UP_MESSAGE = "warm-up"


@dataclass(frozen=True)
class SecondOpinionSettings:
    mode: str = so.OFF
    url: str = "http://llm-reranker:8080"
    timeout_ms: int = 5000
    max_concurrent: int = 1
    # How sure the model must be to rescue a borderline off-topic message
    min_probability: float = 0.9
    ood_band: float = 0.03
    # How much the model's answer counts against e5's confidences (so.combined_order)
    weight: float = 0.25
    # Which unsure messages are asked about: clarify, ood_band (borderline off-topic) or both
    triggers: tuple[str, ...] = (so.OOD_TRIGGER,)
    # The llm-reranker slot this service uses; None lets the server choose
    slot: Optional[int] = None
    # Send each build's catalogue once after it loads, and again after a timeout or error
    warm_up: bool = True
    warm_up_timeout_s: float = 900
    # A warm-up that can't connect (the model server still starting) tries again
    warm_up_attempts: int = 20
    warm_up_retry_s: float = 15
    # A timeout or error re-sends the catalogue at most this often
    rewarm_after_s: float = 60


@dataclass(frozen=True)
class Reply:
    answer: Optional[so.Answer]
    ms: float
    outcome: str


def post_json(url: str, body: dict, timeout: float) -> dict:
    response = requests.post(url, json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()


class SecondOpinion:
    def __init__(
        self,
        settings: SecondOpinionSettings,
        post: Callable[[str, dict, float], dict] = post_json,
    ):
        """
        Args:
            settings: Mode, model server URL and limits
            post: Sends a JSON body and returns the JSON answer (a fake in tests)
        """
        if settings.mode not in so.MODES:
            raise ValueError(
                f"SECOND_OPINION_MODE must be one of {so.MODES}, not {settings.mode!r}"
            )
        unknown = set(settings.triggers) - set(so.TRIGGERS)
        if unknown:
            raise ValueError(
                f"SECOND_OPINION_TRIGGERS must be among {so.TRIGGERS}, not {sorted(unknown)}"
            )
        self.settings = settings
        self._post = post
        self._url = settings.url.rstrip("/") + CHAT_COMPLETIONS
        # A call that finds every slot taken is skipped ("busy"), never queued
        self._slots = threading.BoundedSemaphore(max(1, settings.max_concurrent))
        self._background = (
            ThreadPoolExecutor(
                max_workers=max(1, settings.max_concurrent),
                thread_name_prefix="second-opinion",
            )
            if settings.mode == so.SHADOW
            else None
        )
        # Warm-ups run one after another, outside the call slots
        self._warm_pool = (
            ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="second-opinion-warm-up"
            )
            if self.enabled and settings.warm_up
            else None
        )
        self._warm_lock = threading.Lock()
        self._warm_queued = 0
        self._last_warm = -float("inf")

    @property
    def enabled(self) -> bool:
        return self.settings.mode != so.OFF

    def ask(self, prompt: str, n_options: int) -> Reply:
        """One call within the time limit, or busy if the calls allowed are all running."""
        if not self._slots.acquire(blocking=False):
            return Reply(None, 0.0, so.BUSY)
        return self._call(prompt, n_options)

    def warm_up(self, opening: Optional[str]) -> None:
        """Send a build's catalogue in the background, so the server has read it before the first message."""
        if self._warm_pool is None or opening is None:
            return
        with self._warm_lock:
            self._warm_queued += 1
        self._warm_pool.submit(self._warm, opening)

    def _rewarm(self, opening: Optional[str]) -> None:
        """After a timeout or error: the server may have lost the catalogue (a restart, another build)."""
        if self._warm_pool is None or opening is None:
            return
        with self._warm_lock:
            if (
                self._warm_queued
                or time.monotonic() - self._last_warm < self.settings.rewarm_after_s
            ):
                return
            self._warm_queued += 1
        self._warm_pool.submit(self._warm, opening)

    def _warm(self, opening: str) -> None:
        prompt = so.build_catalogue_prompt(
            opening, WARM_UP_MESSAGE, range(so.CANDIDATES)
        )
        try:
            for attempt in range(1, max(1, self.settings.warm_up_attempts) + 1):
                start = time.perf_counter()
                try:
                    response = self._post(
                        self._url,
                        self._body(prompt, so.CANDIDATES),
                        self.settings.warm_up_timeout_s,
                    )
                except requests.ConnectionError as error:
                    if attempt >= self.settings.warm_up_attempts:
                        raise
                    logger.info(
                        f"Second opinion warm-up can't connect yet ({type(error).__name__}); "
                        f"retrying in {self.settings.warm_up_retry_s:.0f}s"
                    )
                    time.sleep(self.settings.warm_up_retry_s)
                    continue
                tokens = (response.get("usage") or {}).get("prompt_tokens")
                logger.info(
                    f"second_opinion warm-up ms={_ms(start):.0f} prompt_tokens={tokens} "
                    f"slot={self.settings.slot}"
                )
                return
        except Exception as error:
            logger.warning(
                f"Second opinion warm-up failed: {type(error).__name__}: {str(error)[:200]}"
            )
        finally:
            with self._warm_lock:
                self._warm_queued -= 1
                self._last_warm = time.monotonic()

    def _body(self, prompt: str, n_options: int) -> dict:
        body = so.request_body(prompt, n_options)
        if self.settings.slot is not None:
            body["id_slot"] = self.settings.slot
        return body

    def _call(self, prompt: str, n_options: int) -> Reply:
        """Makes the call with a slot already taken, and frees it."""
        start = time.perf_counter()
        try:
            response = self._post(
                self._url,
                self._body(prompt, n_options),
                self.settings.timeout_ms / 1000,
            )
            answer = so.read_answer(response, n_options)
            return Reply(answer, _ms(start), so.OK)
        except requests.Timeout:
            return Reply(None, _ms(start), so.TIMEOUT)
        except Exception as error:
            logger.warning(
                f"Second opinion failed: {type(error).__name__}: {str(error)[:200]}"
            )
            return Reply(None, _ms(start), so.ERROR)
        finally:
            self._slots.release()

    def review(
        self,
        model_id: str,
        agencies: list[Agency],
        gate: GateParams,
        opening: Optional[str],
        texts: list[str],
        scores: Scores,
        decisions: list[Decision],
        prediction_lists: list[list[dict]],
        records: list[dict],
    ) -> tuple[list[list[dict]], list[dict]]:
        """
        The output after the second opinion. Only messages that trigger it are
        asked about. Mode on applies the answer and adds the second_opinion
        field; mode shadow asks in the background and changes nothing.

        Args:
            opening: The build's catalogue (so.catalogue); None asks nothing
        """
        if not self.enabled or opening is None:
            return prediction_lists, records
        order = ranking(scores.fused)
        prediction_lists, records = list(prediction_lists), list(records)
        for i, decision in enumerate(decisions):
            reason = so.trigger(decision, gate.ood_cutoff, self.settings.ood_band)
            if reason not in self.settings.triggers:
                continue
            positions = [int(a) for a in order[i, : gate.clarify_candidates]]
            ids = [agencies[p].agency_id for p in positions]
            prompt = so.build_catalogue_prompt(opening, texts[i], positions)

            if self.settings.mode == so.SHADOW:
                if self._slots.acquire(blocking=False):
                    self._background.submit(
                        self._shadow,
                        model_id,
                        reason,
                        ids,
                        prompt,
                        opening,
                        prediction_lists[i],
                        records[i],
                    )
                else:
                    self._log(model_id, reason, ids, Reply(None, 0.0, so.BUSY), False)
                continue

            reply = self.ask(prompt, len(ids))
            if reply.outcome in (so.TIMEOUT, so.ERROR):
                self._rewarm(opening)
            applied = False
            if reply.answer is not None:
                prediction_lists[i], records[i], applied = so.apply_combined(
                    prediction_lists[i],
                    records[i],
                    reason,
                    ids,
                    reply.answer,
                    self.settings.weight,
                    self.settings.min_probability,
                )
            records[i] = {
                **records[i],
                "second_opinion": so.record_field(
                    reply.answer, ids, applied, reply.ms, reply.outcome
                ),
            }
            self._log(model_id, reason, ids, reply, applied)
        return prediction_lists, records

    def _shadow(self, model_id, reason, ids, prompt, opening, items, record) -> None:
        reply = self._call(prompt, len(ids))
        if reply.outcome in (so.TIMEOUT, so.ERROR):
            self._rewarm(opening)
        # In shadow mode "applied" says whether mode on would have changed the output
        would_apply = (
            reply.answer is not None
            and (
                so.apply_combined(
                    items,
                    record,
                    reason,
                    ids,
                    reply.answer,
                    self.settings.weight,
                    self.settings.min_probability,
                )[2]
            )
        )
        self._log(model_id, reason, ids, reply, would_apply)

    def _log(self, model_id, reason, ids, reply: Reply, applied: bool) -> None:
        """Never the message or the prompt: they hold citizen text."""
        answer = reply.answer
        logger.info(
            f"second_opinion model={model_id} mode={self.settings.mode} trigger={reason} "
            f"top3={ids} answer={answer.letter if answer else '-'} "
            f"probability={f'{answer.probability:.3f}' if answer else '-'} applied={applied} "
            f"ms={reply.ms:.0f} outcome={reply.outcome} prompt_version={so.PROMPT_VERSION}"
        )


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
