"""
What goes into an index: question cleaning, passage chunking, titles, and the
two input adapters (the production dataset CSV and the knowledge base used for
evaluation).
"""

import json
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

MIN_QUESTIONS = 5
TITLE_MIN_WORDS = 2
PASSAGE_MIN_WORDS = 80
PASSAGE_MAX_WORDS = 160
PASSAGE_MIN_TAIL_WORDS = 20
PASSAGES_PER_AGENCY = 150
PASSAGE_SEED = 0

QUESTION_COLUMNS = ["agency_id", "agency_name", "text"]

TURN_MARKER = re.compile(r"\b(user|assistant):", flags=re.IGNORECASE)


def read_aggregated_dataset(path: str) -> pd.DataFrame:
    """
    Read a dataset version's aggregated_dataset.csv.

    It is read as the trainer reads it (no dtype), so numeric agency ids stay
    integers and the output keeps today's agency_id types.

    Returns:
        Columns agency_id, agency_name, text
    """
    frame = pd.read_csv(path)
    return frame.rename(columns={"data_item": "text"})[QUESTION_COLUMNS]


def clean_questions(
    questions: pd.DataFrame, min_questions: int = MIN_QUESTIONS
) -> tuple[pd.DataFrame, list[str]]:
    """
    Drop empty texts, duplicates within an agency, questions that appear word
    for word under several agencies, and agencies left with too few questions.

    Args:
        questions: Columns agency_id, agency_name, text
        min_questions: Agencies with fewer questions are left out

    Returns:
        The kept questions, and a warning per thing dropped
    """
    warnings = []
    frame = questions.assign(text=questions["text"].fillna("").astype(str).str.strip())
    frame = frame[frame["text"] != ""]
    frame = frame.drop_duplicates(["agency_id", "text"])

    key = frame["text"].map(_normalise)
    shared = key.map(frame.groupby(key)["agency_id"].nunique()) > 1
    if shared.any():
        warnings.append(
            f"Dropped {int(shared.sum())} questions that appear under several agencies"
        )
    frame = frame[~shared]

    counts = frame.groupby("agency_id")["text"].size()
    names = frame.groupby("agency_id")["agency_name"].first()
    for agency_id, count in counts[counts < min_questions].items():
        warnings.append(
            f"Left out {names[agency_id]} ({agency_id}): {count} questions, "
            f"fewer than {min_questions}"
        )
    frame = frame[frame["agency_id"].map(counts) >= min_questions]
    return frame.reset_index(drop=True), warnings


def chunk_passages(text: str) -> list[str]:
    """
    Split a document into passages: accumulate newline-separated blocks until
    the chunk has PASSAGE_MIN_WORDS words, emit its first PASSAGE_MAX_WORDS,
    and emit a final remainder of at least PASSAGE_MIN_TAIL_WORDS.
    """
    passages, chunk = [], []
    for block in text.split("\n"):
        chunk.append(block)
        words = " ".join(chunk).split()
        if len(words) >= PASSAGE_MIN_WORDS:
            passages.append(" ".join(words[:PASSAGE_MAX_WORDS]))
            chunk = []
    if len(" ".join(chunk).split()) >= PASSAGE_MIN_TAIL_WORDS:
        # The remainder keeps its blocks as written, joined by spaces
        passages.append(" ".join(chunk))
    return passages


def is_title(text: str) -> bool:
    """Page or topic titles of one word say too little to store."""
    return len(text.split()) >= TITLE_MIN_WORDS


def sample_passages(
    passages: pd.DataFrame,
    per_agency: int = PASSAGES_PER_AGENCY,
    seed: int = PASSAGE_SEED,
) -> pd.DataFrame:
    """
    Remove duplicate passages and keep at most per_agency per agency.

    Args:
        passages: Columns agency_id, text
        per_agency: Most passages kept for one agency
        seed: Fixes which passages are kept

    Returns:
        Columns agency_id, text, grouped by agency in sorted order
    """
    unique = passages.drop_duplicates("text")
    if unique.empty:
        return unique.reset_index(drop=True)
    kept = [
        group.sample(min(len(group), per_agency), random_state=seed)
        for _, group in unique.groupby("agency_id")
    ]
    return pd.concat(kept).reset_index(drop=True)


def user_turns(conversation: str) -> str:
    """
    Keep what the citizen wrote in a "user: ... assistant: ..." conversation,
    one turn per line. Text without markers is returned stripped.
    """
    parts = TURN_MARKER.split(conversation)
    if len(parts) == 1:
        return conversation.strip()
    return "\n".join(
        text.strip()
        for speaker, text in zip(parts[1::2], parts[2::2])
        if speaker.lower() == "user" and text.strip()
    )


def read_kb_questions(kb: Path, min_questions: int = MIN_QUESTIONS) -> pd.DataFrame:
    """
    Real questions from the knowledge base's faq.csv, filtered as the
    benchmarks were: no synthetic rows, no question asked word for word
    (ignoring case) by several agencies, and only agencies with at least
    min_questions.

    Returns:
        Columns of faq.csv (agency_id, agency_name, question, answer, kind, ...)
    """
    faq = pd.read_csv(Path(kb) / "faq.csv")
    real = faq[faq["kind"] != "synthetic"]
    key = real["question"].str.lower()
    real = real[key.map(real.groupby(key)["agency_id"].nunique()) == 1]
    counts = real["agency_id"].value_counts()
    small = sorted(counts[counts < min_questions].index)
    if small:
        logger.info(
            f"Leaving out agencies with fewer than {min_questions} questions: {small}"
        )
    return real[~real["agency_id"].isin(small)].reset_index(drop=True)


def read_kb_documents(
    kb: Path, agencies: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Passages and titles from each agency's documents.jsonl in the knowledge base.

    Returns:
        (passages, titles), each with columns agency_id, text. Passages are
        sampled with sample_passages; titles are distinct per agency, ignoring case.
    """
    passages, titles = [], []
    for agency_id in agencies:
        path = Path(kb) / agency_id / "documents.jsonl"
        if not path.exists():
            continue
        seen = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                document = json.loads(line)
                title = document["title"].strip()
                if is_title(title) and title.lower() not in seen:
                    seen.add(title.lower())
                    titles.append({"agency_id": agency_id, "text": title})
                passages.extend(
                    {"agency_id": agency_id, "text": text}
                    for text in chunk_passages(document["text"])
                )
    passages = sample_passages(pd.DataFrame(passages, columns=["agency_id", "text"]))
    return passages, pd.DataFrame(titles, columns=["agency_id", "text"])


def _normalise(text: str) -> str:
    return " ".join(text.casefold().split())
