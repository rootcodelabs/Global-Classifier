"""
The rows of an index: one per stored text, each with its agency and kind,
and how a build turns them into vectors.
"""

from dataclasses import dataclass
from typing import Optional, Union

import numpy as np
import pandas as pd

from embedding_classifier.embedding_cache import EmbeddingCache

QUESTION = "question"
TITLE = "title"
PASSAGE = "passage"
ANSWER = "answer"
OFFTOPIC = "offtopic"

# Which token limit (encoder.MAX_SEQ_LENGTH) each kind is embedded with
LENGTH_BY_KIND = {
    QUESTION: "short",
    TITLE: "short",
    OFFTOPIC: "short",
    PASSAGE: "long",
    ANSWER: "long",
}

AgencyId = Union[int, str]


@dataclass(frozen=True)
class Agency:
    """
    One agency of an index. agency_id keeps the type it had in the dataset,
    because the output must match today's types; key is its string form,
    used in the vector store's payload and filters.
    """

    agency_id: AgencyId
    agency_name: str

    @property
    def key(self) -> str:
        return str(self.agency_id)


@dataclass(frozen=True)
class Row:
    """One stored text."""

    agency_key: str
    agency_name: str
    kind: str
    text: str
    source: str = ""


def json_value(value):
    """numpy and pandas scalars as plain Python values, so they serialise as today."""
    return value.item() if isinstance(value, np.generic) else value


def agencies_from_frame(frame: pd.DataFrame) -> list[Agency]:
    """Distinct agencies of a frame with agency_id and agency_name, ordered by key."""
    first = frame.drop_duplicates("agency_id")
    agencies = [
        Agency(json_value(agency_id), str(name))
        for agency_id, name in zip(first["agency_id"], first["agency_name"])
    ]
    return sorted(agencies, key=lambda agency: agency.key)


def rows_from_frame(
    frame: pd.DataFrame, kind: str, names: dict[str, str], source: str = ""
) -> list[Row]:
    """
    Rows of one kind from a frame with agency_id and text.

    Args:
        frame: Columns agency_id, text
        kind: One of the kinds above
        names: Agency name by agency key
        source: Where the texts came from, stored in the payload
    """
    if kind not in LENGTH_BY_KIND:
        raise ValueError(f"Unknown kind {kind!r}")
    return [
        Row(str(agency_id), names[str(agency_id)], kind, str(text), source)
        for agency_id, text in zip(frame["agency_id"], frame["text"])
    ]


def count_by_agency(rows: list[Row]) -> dict[str, dict[str, int]]:
    """Rows per agency key and kind, for the manifest."""
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        per_kind = counts.setdefault(row.agency_key, {})
        per_kind[row.kind] = per_kind.get(row.kind, 0) + 1
    return counts


def embed_rows(
    encoder, rows: list[Row], cache: Optional[EmbeddingCache] = None
) -> np.ndarray:
    """
    Vectors for rows, each embedded with its kind's token limit.

    Returns:
        Array of shape (len(rows), encoder.dim), in row order
    """
    vectors = np.zeros((len(rows), encoder.dim), dtype=np.float32)
    for length in ("short", "long"):
        positions = [
            i for i, row in enumerate(rows) if LENGTH_BY_KIND[row.kind] == length
        ]
        if not positions:
            continue
        texts = [rows[i].text for i in positions]
        if cache is None:
            vectors[positions] = encoder.encode(texts, length)
        else:
            vectors[positions] = cache.encode(encoder, texts, length)
    return vectors
