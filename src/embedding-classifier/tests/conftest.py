"""Shared test helpers: a keyword-count fake encoder, so tests run in seconds with no model download."""

import numpy as np
import pandas as pd
import pytest

from embedding_classifier.encoder import EmbeddingModel
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.store import (
    QUESTION,
    Agency,
    agencies_from_frame,
    rows_from_frame,
)

VOCABULARY = ["pass", "tarbija", "smart-id", "tomat", "maks", "kool", "vang", "auto"]


class FakeEncoder:
    """Embeds a text as the counts of a few keywords plus a small constant, at unit length."""

    # A real model id (its prompt is defined) with a revision no real build has
    model = EmbeddingModel("fake", "BAAI/bge-m3", "0" * 40)
    dim = len(VOCABULARY)

    def __init__(self):
        self.calls: list[tuple[int, str]] = []

    def encode(self, texts, length="short", batch_size=32):
        self.calls.append((len(texts), length))
        vectors = np.array(
            [[text.lower().count(word) for word in VOCABULARY] for text in texts],
            dtype=np.float32,
        ).reshape(len(texts), self.dim)
        vectors += 0.05
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def encoder():
    return FakeEncoder()


@pytest.fixture
def questions():
    """Three agencies, 6, 6 and 5 questions; "idee" has exactly knn_k rows."""
    rows = [
        ("ppa", "Politsei- ja Piirivalveamet", "Kuidas pass taotleda?"),
        ("ppa", "Politsei- ja Piirivalveamet", "Lapse pass on kadunud"),
        ("ppa", "Politsei- ja Piirivalveamet", "pass ja ID-kaart"),
        ("ppa", "Politsei- ja Piirivalveamet", "Kus saab passi kätte?"),
        ("ppa", "Politsei- ja Piirivalveamet", "pass aegus, mida teha"),
        ("ppa", "Politsei- ja Piirivalveamet", "Kas pass on vaja uuendada?"),
        ("ttja", "Tarbijakaitse ja Tehnilise Järelevalve Amet", "Tarbija õigused poes"),
        (
            "ttja",
            "Tarbijakaitse ja Tehnilise Järelevalve Amet",
            "tarbija kaebus kauplusele",
        ),
        (
            "ttja",
            "Tarbijakaitse ja Tehnilise Järelevalve Amet",
            "Tarbija sai katkise auto",
        ),
        ("ttja", "Tarbijakaitse ja Tehnilise Järelevalve Amet", "tarbija ja garantii"),
        (
            "ttja",
            "Tarbijakaitse ja Tehnilise Järelevalve Amet",
            "Kuhu tarbija pöördub?",
        ),
        (
            "ttja",
            "Tarbijakaitse ja Tehnilise Järelevalve Amet",
            "tarbija lepingust taganemine",
        ),
        ("idee", "ID.ee", "Smart-ID ei tööta"),
        ("idee", "ID.ee", "Smart-ID PIN on blokeeritud"),
        ("idee", "ID.ee", "Kuidas Smart-ID uuendada?"),
        ("idee", "ID.ee", "Smart-ID konto on lukus"),
        ("idee", "ID.ee", "Unustasin Smart-ID PIN-koodi"),
    ]
    return pd.DataFrame(rows, columns=["agency_id", "agency_name", "text"])


@pytest.fixture
def index_data(questions, encoder):
    """Agencies, rows, dense and keyword vectors, and the fitted vectorizer of the fixture."""
    agencies: list[Agency] = agencies_from_frame(questions)
    names = {a.key: a.agency_name for a in agencies}
    rows = rows_from_frame(questions, QUESTION, names, "test")
    texts = [row.text for row in rows]
    keywords = KeywordVectorizer.fit(texts)
    return {
        "agencies": agencies,
        "rows": rows,
        "dense": encoder.encode(texts),
        "keywords": keywords,
        "keyword_vectors": keywords.transform(texts),
    }
