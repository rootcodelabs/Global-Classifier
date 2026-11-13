"""The keyword vectorizer and its JSON form."""

import json

import numpy as np

from embedding_classifier.keywords import KeywordVectorizer, sparse_row

TEXTS = [
    "Kuidas taotleda elamisluba?",
    "Elamisloa pikendamine",
    "Maamaks ja maksuamet",
    "Smart-ID PIN on blokeeritud",
    "Smart-ID ei tööta",
]


def test_vectorizer_rebuilt_from_json_gives_the_same_vectors():
    fitted = KeywordVectorizer.fit(TEXTS)
    rebuilt = KeywordVectorizer.from_json(json.loads(json.dumps(fitted.to_json())))
    messages = TEXTS + ["Mu Smart-ID ei tööta enam", "täiesti tundmatu"]

    a, b = fitted.transform(messages), rebuilt.transform(messages)

    assert (a != b).nnz == 0
    assert rebuilt.params == fitted.params


def test_vectors_are_unit_length_or_empty():
    vectors = KeywordVectorizer.fit(TEXTS).transform(TEXTS + ["qqqq"])
    norms = np.sqrt(vectors.multiply(vectors).sum(axis=1)).A1
    # Only n-grams in at least 2 stored texts count, so a text can share none
    assert np.allclose(norms[[0, 1, 3, 4]], 1.0, atol=1e-5)
    assert norms[2] == 0 and norms[-1] == 0


def test_sparse_row_gives_indices_and_values():
    vectors = KeywordVectorizer.fit(TEXTS).transform(TEXTS)
    indices, values = sparse_row(vectors, 3)
    assert len(indices) == len(values) == vectors[3].nnz
    assert np.allclose(vectors[3].toarray()[0, indices], values)
