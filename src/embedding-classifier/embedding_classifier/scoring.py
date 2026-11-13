"""
Scoring a message against an index: meaning (dense) and keyword scores per
agency from the index store, fused into one ranking score.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import sparse

from embedding_classifier.vector_store import IndexStore

METHOD = "knn_keywords"


@dataclass(frozen=True)
class ScoringParams:
    knn_k: int = 5
    keyword_weight: float = 0.3


@dataclass
class Scores:
    """Per-agency scores, each of shape (n_messages, n_agencies), in manifest agency order."""

    dense: np.ndarray
    keywords: np.ndarray
    fused: np.ndarray
    # Per message, per agency, its nearest stored texts (only when asked for)
    texts: Optional[list[list[list[str]]]] = None

    @property
    def top_similarity(self) -> np.ndarray:
        """The raw dense top score of each message, which the off-topic check uses."""
        return self.dense.max(axis=1)


def rescale_rows(x: np.ndarray) -> np.ndarray:
    """Rescale each row to 0..1 by its own min and max; a constant row becomes 0."""
    low = x.min(axis=1, keepdims=True)
    high = x.max(axis=1, keepdims=True)
    return (x - low) / np.maximum(high - low, 1e-9)


def fuse(dense: np.ndarray, keywords: np.ndarray, keyword_weight: float) -> np.ndarray:
    return rescale_rows(dense) + keyword_weight * rescale_rows(keywords)


def score(
    store: IndexStore,
    collection: str,
    agency_keys: list[str],
    dense_queries: np.ndarray,
    keyword_queries: sparse.csr_matrix,
    params: ScoringParams,
    with_texts: bool = False,
) -> Scores:
    """Score embedded messages against a collection; with_texts also returns the nearest stored texts."""
    result = store.agency_scores(
        collection,
        agency_keys,
        dense_queries,
        keyword_queries,
        params.knn_k,
        with_texts=with_texts,
    )
    dense = result[0].astype(np.float64)
    keywords = result[1].astype(np.float64)
    texts = result[2] if with_texts else None
    return Scores(dense, keywords, fuse(dense, keywords, params.keyword_weight), texts)
