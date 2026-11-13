"""
Second opinion from a small language model for unsure messages
(docs/ARCHITECTURE.md): which messages get it, the prompt, the
grammar that forces a one-letter answer, reading the answer and its
probability, and applying it to the output. Pure functions: the service and
the benchmark make the HTTP call, so both send exactly the same thing.

The service sends prompt version 2: every agency in a fixed opening that the
model server keeps cached, then only the message and e5's top 3 by number, so
a call reads about 50 new tokens instead of about 250. Its answer is combined
with e5's confidences instead of overruling them. Version 1 (build_prompt,
apply_answer) stays for the evaluation and benchmark tools.
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from embedding_classifier.gate import CLARIFY, OUT_OF_DISTRIBUTION, Decision
from embedding_classifier.output import OOD_AGENCY_ID, OOD_AGENCY_NAME

PROMPT_VERSION = 2

OFF = "off"
SHADOW = "shadow"
ON = "on"
MODES = (OFF, SHADOW, ON)

# Why a message gets a second opinion
CLARIFY_TRIGGER = "clarify"
OOD_TRIGGER = "ood_band"
TRIGGERS = (CLARIFY_TRIGGER, OOD_TRIGGER)

# How a call ended
OK = "ok"
TIMEOUT = "timeout"
ERROR = "error"
BUSY = "busy"

LETTERS = ("A", "B", "C")
NONE_LETTER = "N"
NONE_PICK = "none"
CANDIDATES = 3
MESSAGE_CHARS = 1000
EXAMPLE_CHARS = 200
EXAMPLES_PER_AGENCY = 3
# Enough to hold all four letters even when the model prefers other tokens
TOP_LOGPROBS = 20

INSTRUCTIONS = (
    "You route citizen messages to Estonian state agencies. Below are a message and three\n"
    "candidate agencies, each with questions it answers. Reply with one letter: the agency that\n"
    "should answer the message, or N if none of them should."
)

# Prompt version 2
CATALOGUE_HEADER = (
    "You route citizen messages to Estonian state agencies. These are the agencies, each with\n"
    "questions it answers:"
)
CATALOGUE_INSTRUCTIONS = (
    "A search system ranked three of these agencies for the message below. A is its first "
    "choice and is usually right. Reply A unless the message clearly belongs to B or C, or N "
    "if none of them should answer."
)
CATALOGUE_EXAMPLES = 3
# The llm-reranker's slot holds 6,144 tokens; Estonian takes about 3 characters a token,
# which leaves room for the message
CATALOGUE_MAX_CHARS = 15000
# Floors the logarithms, so a letter the model gave no probability still counts
COMBINE_FLOOR = 1e-6


@dataclass(frozen=True)
class Candidate:
    position: int  # the agency's position in the manifest
    name: str
    examples: list[str]  # its nearest stored texts, best first


@dataclass(frozen=True)
class Answer:
    letter: str
    probability: float
    prompt_tokens: Optional[int] = None
    # Every allowed letter's share, e.g. {"A": 0.7, "B": 0.2, "C": 0.05, "N": 0.05}
    letters: Optional[dict] = None

    def pick(self) -> Optional[int]:
        """The candidate index (0 for A), or None for N."""
        return None if self.letter == NONE_LETTER else LETTERS.index(self.letter)


def trigger(decision: Decision, ood_cutoff: float, ood_band: float) -> Optional[str]:
    """
    Why the message gets a second opinion, or None: every clarify, and
    out_of_distribution when the raw dense top score is within ood_band below
    ood_cutoff. Never route.
    """
    if decision.decision == CLARIFY:
        return CLARIFY_TRIGGER
    if (
        decision.decision == OUT_OF_DISTRIBUTION
        and decision.top_similarity >= ood_cutoff - ood_band
    ):
        return OOD_TRIGGER
    return None


def candidates(
    order: Sequence[int],
    names: Sequence[str],
    texts: Sequence[Sequence[str]],
    n: int = CANDIDATES,
) -> list[Candidate]:
    """
    e5's top n agencies, best first.

    Args:
        order: Agency positions of one message, best first
        names: Agency names in manifest order
        texts: Per agency position, its nearest stored texts, best first
    """
    return [
        Candidate(int(a), names[int(a)], list(texts[int(a)])[:EXAMPLES_PER_AGENCY])
        for a in list(order)[:n]
    ]


def one_line(text: str, limit: int) -> str:
    """Whitespace collapsed, so the text can't break the prompt's layout, then cut."""
    return " ".join(str(text).split())[:limit]


def build_prompt(message: str, options: list[Candidate]) -> str:
    """The single user turn of PROMPT_VERSION 1."""
    lines = [INSTRUCTIONS, "", f"Message: {one_line(message, MESSAGE_CHARS)}", ""]
    for letter, option in zip(LETTERS, options):
        lines.append(f"{letter}) {option.name}")
        lines += [
            f"   - {one_line(text, EXAMPLE_CHARS)}"
            for text in option.examples[:EXAMPLES_PER_AGENCY]
        ]
    lines += [f"{NONE_LETTER}) None of these", "", "Answer:"]
    return "\n".join(lines)


def catalogue(
    names: Sequence[str],
    examples: Sequence[Sequence[str]],
    max_chars: int = CATALOGUE_MAX_CHARS,
) -> str:
    """
    The fixed opening of prompt version 2: every agency, numbered from 1 in
    manifest order, with up to CATALOGUE_EXAMPLES of its typical questions.
    With too many agencies for max_chars, every agency keeps fewer examples.

    Args:
        names: Agency names in manifest order
        examples: Per agency, its typical stored questions, most typical first

    Raises:
        ValueError: The names alone don't fit max_chars
    """
    for keep in range(CATALOGUE_EXAMPLES, -1, -1):
        lines = [CATALOGUE_HEADER, ""]
        for number, (name, texts) in enumerate(zip(names, examples), start=1):
            lines.append(f"{number}. {one_line(name, EXAMPLE_CHARS)}")
            lines += [f"   - {one_line(text, EXAMPLE_CHARS)}" for text in texts[:keep]]
        opening = "\n".join(lines)
        if len(opening) <= max_chars:
            return opening
    raise ValueError(f"{len(names)} agency names take more than {max_chars} characters")


def build_catalogue_prompt(opening: str, message: str, positions: Sequence[int]) -> str:
    """
    The single user turn of PROMPT_VERSION 2. Everything before the message is
    the same for every message of a build, so the model server reads it once.

    Args:
        opening: catalogue() of the build
        message: The citizen's message
        positions: e5's top agencies, best first, as manifest positions
    """
    options = "  ".join(f"{letter}) {p + 1}" for letter, p in zip(LETTERS, positions))
    return "\n".join(
        [
            opening,
            "",
            CATALOGUE_INSTRUCTIONS,
            "",
            f"Message: {one_line(message, MESSAGE_CHARS)}",
            "",
            "Options:",
            f"{options}  {NONE_LETTER}) none",
            "",
            "Answer:",
        ]
    )


def valid_letters(n_options: int) -> tuple[str, ...]:
    return LETTERS[:n_options] + (NONE_LETTER,)


def grammar(n_options: int = CANDIDATES) -> str:
    """GBNF that allows only one of the option letters or N."""
    return "root ::= " + " | ".join(f'"{x}"' for x in valid_letters(n_options))


def request_body(prompt: str, n_options: int = CANDIDATES) -> dict:
    """Chat completions body for llama-server: one forced token at temperature 0, with log-probabilities."""
    return {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0,
        "grammar": grammar(n_options),
        "logprobs": True,
        "top_logprobs": TOP_LOGPROBS,
        "cache_prompt": True,
    }


def read_answer(response: dict, n_options: int = CANDIDATES) -> Answer:
    """
    The letter and its probability from a chat completions response.

    The probability is the letter's share among the allowed letters, from the
    returned log-probabilities. Raises ValueError for anything else.
    """
    choice = response["choices"][0]
    letter = (choice.get("message", {}).get("content") or "").strip()
    allowed = valid_letters(n_options)
    if letter not in allowed:
        raise ValueError(f"Unexpected answer {letter!r}")
    tokens = (choice.get("logprobs") or {}).get("content") or []
    if not tokens:
        raise ValueError("The answer has no log-probabilities")
    first = tokens[0]
    logprobs: dict[str, float] = {}
    for entry in first.get("top_logprobs") or []:
        token = str(entry.get("token", "")).strip()
        if token in allowed:
            logprobs[token] = max(logprobs.get(token, -math.inf), entry["logprob"])
    if letter not in logprobs:
        logprobs[letter] = first["logprob"]
    # The returned distribution may cover the whole vocabulary; keep the letters
    top = max(logprobs.values())
    total = sum(math.exp(lp - top) for lp in logprobs.values())
    letters = {
        x: math.exp(logprobs[x] - top) / total if x in logprobs else 0.0
        for x in allowed
    }
    usage = response.get("usage") or {}
    return Answer(letter, letters[letter], usage.get("prompt_tokens"), letters)


def is_ood_entry(item: dict) -> bool:
    return (
        item.get("agency_id") == OOD_AGENCY_ID
        and item.get("agency_name") == OOD_AGENCY_NAME
    )


def apply_answer(
    items: list[dict],
    record: dict,
    trigger_name: str,
    candidate_ids: list,
    answer: Answer,
    min_probability: float,
) -> tuple[list[dict], dict, bool]:
    """
    One message's prediction list and decision record after the answer, and
    whether anything changed.

    - clarify, B or C at min_probability or above: that agency goes first.
    - borderline out_of_distribution, A, B or C at min_probability or above:
      the out_of_distribution entry goes, the pick goes first, and the decision
      becomes clarify.
    - Anything else: no change.

    When the order changes, the confidence values keep their sorted order and
    are reassigned by the new order, so the pick also has the top confidence.
    """
    pick = answer.pick()
    if (
        pick is None
        or answer.probability < min_probability
        or pick >= len(candidate_ids)
    ):
        return items, record, False
    if trigger_name == CLARIFY_TRIGGER and pick == 0:
        return items, record, False

    agencies = [item for item in items if not is_ood_entry(item)]
    chosen = candidate_ids[pick]
    at = next(
        (i for i, item in enumerate(agencies) if item["agency_id"] == chosen), None
    )
    if at is None:
        return items, record, False
    order = [agencies[at]] + agencies[:at] + agencies[at + 1 :]
    values = sorted((item["confidence"] for item in agencies), reverse=True)
    new_items = [{**item, "confidence": c} for item, c in zip(order, values)]
    new_record = {
        **record,
        "decision": CLARIFY,
        "candidates": [item["agency_id"] for item in new_items[: len(candidate_ids)]],
    }
    return new_items, new_record, True


def combined_order(
    confidences: Sequence[float], letters: dict, weight: float
) -> list[int]:
    """
    The candidates' order by e5 and the model together: log confidence +
    weight * log of the candidate's letter probability, best first. A tie
    keeps e5's order; a weight of 0 is e5's order.

    Args:
        confidences: e5's confidences of its top candidates, best first
        letters: The model's probability per letter (Answer.letters)
        weight: How much the model counts against e5
    """
    scores = [
        math.log(max(c, COMBINE_FLOOR))
        + weight * math.log(letters.get(letter, 0.0) + COMBINE_FLOOR)
        for c, letter in zip(confidences, LETTERS)
    ]
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


def apply_combined(
    items: list[dict],
    record: dict,
    trigger_name: str,
    candidate_ids: list,
    answer: Answer,
    weight: float,
    min_probability: float,
) -> tuple[list[dict], dict, bool]:
    """
    One message's prediction list and decision record after a prompt version 2
    answer, and whether anything changed.

    - clarify: e5's top candidates are put in combined_order; the agencies
      after them keep their places.
    - borderline out_of_distribution: only an answer of A, B or C at
      min_probability or above rescues it, as in apply_answer: the
      out_of_distribution entry goes, the candidates come first in
      combined_order, and the decision becomes clarify.
    - Anything else, or a prediction list that doesn't start with the
      candidates (a top_k below their number): no change.

    The confidence values keep their sorted order and are reassigned by the
    new order, so the first agency also has the top confidence.
    """
    agencies = [item for item in items if not is_ood_entry(item)]
    n = len(candidate_ids)
    if [item["agency_id"] for item in agencies[:n]] != list(candidate_ids):
        return items, record, False
    if trigger_name == OOD_TRIGGER and (
        answer.pick() is None or answer.probability < min_probability
    ):
        return items, record, False

    letters = answer.letters or {answer.letter: answer.probability}
    order = combined_order(
        [item["confidence"] for item in agencies[:n]], letters, weight
    )
    if trigger_name == CLARIFY_TRIGGER and order == list(range(n)):
        return items, record, False

    reordered = [agencies[i] for i in order] + agencies[n:]
    values = sorted((item["confidence"] for item in agencies), reverse=True)
    new_items = [{**item, "confidence": c} for item, c in zip(reordered, values)]
    new_record = {
        **record,
        "decision": CLARIFY,
        "candidates": [item["agency_id"] for item in new_items[:n]],
    }
    return new_items, new_record, True


def record_field(
    answer: Optional[Answer],
    candidate_ids: list,
    applied: bool,
    ms: float,
    outcome: str,
) -> dict:
    """The second_opinion field of a DECISION record."""
    pick = None
    if answer is not None:
        index = answer.pick()
        pick = NONE_PICK if index is None else candidate_ids[index]
    return {
        "pick": pick,
        "probability": None if answer is None else answer.probability,
        "applied": applied,
        "ms": round(ms),
        "outcome": outcome,
    }
