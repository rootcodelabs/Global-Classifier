"""
The two index stores: the in-memory oracle, and Qdrant through qdrant-client's
local mode. Tests marked qdrant_server also run against a real server when
QDRANT_URL is set.
"""

import os
import uuid
import warnings

import numpy as np
import pytest
from scipy import sparse

from embedding_classifier.gate import ranking
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import ScoringParams, score
from embedding_classifier.store import QUESTION, Row
from embedding_classifier.vector_store import (
    DENSE,
    KEYWORDS,
    NO_ROWS_SCORE,
    MemoryIndexStore,
    QdrantIndexStore,
)


@pytest.fixture
def local_qdrant():
    from qdrant_client import QdrantClient

    with warnings.catch_warnings():
        # Local mode warns that payload indexes and search params have no effect
        warnings.simplefilter("ignore", UserWarning)
        yield QdrantIndexStore(QdrantClient(":memory:"), requests_per_call=50)


@pytest.fixture
def server_qdrant():
    url = os.environ.get("QDRANT_URL")
    if not url:
        pytest.skip("QDRANT_URL is not set")
    return QdrantIndexStore.connect(url, os.environ.get("QDRANT_API_KEY"), timeout=10)


def tiny_collection():
    """Agency a has 7 rows, b has 3 (fewer than knn_k), c has 6 with no keyword overlap."""
    rng = np.random.default_rng(0)
    dense = rng.normal(size=(16, 8)).astype(np.float32)
    dense /= np.linalg.norm(dense, axis=1, keepdims=True)
    agency_of = ["a"] * 7 + ["b"] * 3 + ["c"] * 6
    rows = [Row(a, a.upper(), QUESTION, f"text {i}") for i, a in enumerate(agency_of)]
    keywords = sparse.lil_matrix((16, 120), dtype=np.float32)
    for i, a in enumerate(agency_of):
        if a == "c":
            keywords[i, 100 + i] = 1.0
        else:
            keywords[i, i % 4] = 0.6
            keywords[i, 10 + i] = 0.8
    return rows, dense, keywords.tocsr()


def query():
    rng = np.random.default_rng(1)
    q = rng.normal(size=(2, 8)).astype(np.float32)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    keywords = sparse.csr_matrix(
        np.array([[0.7, 0.7] + [0] * 118, [0] * 120], dtype=np.float32)
    )
    return q, keywords


def test_memory_store_scores_match_their_definition():
    rows, dense, keywords = tiny_collection()
    store = MemoryIndexStore()
    store.create_collection("c1", rows, dense, keywords)
    q, q_keywords = query()

    d, k = store.agency_scores("c1", ["a", "b", "c", "none"], q, q_keywords, knn_k=5)

    sims = q @ dense.T
    assert d[0, 0] == pytest.approx(np.sort(sims[0, :7])[-5:].mean(), abs=1e-6)
    # Fewer rows than knn_k: the mean of all of them
    assert d[0, 1] == pytest.approx(sims[0, 7:10].mean(), abs=1e-6)
    assert d[0, 3] == NO_ROWS_SCORE
    # Keywords: the best match per agency, 0 with no shared n-gram or no rows
    assert k[0, 0] == pytest.approx((q_keywords[0] @ keywords[:7].T).toarray().max())
    assert k[0, 2] == 0 and k[0, 3] == 0
    # A message with no known n-gram gets 0 everywhere
    assert np.all(k[1] == 0)


def check_parity(store):
    rows, dense, keywords = tiny_collection()
    oracle = MemoryIndexStore()
    name = f"test_{uuid.uuid4().hex[:8]}"
    oracle.create_collection(name, rows, dense, keywords)
    store.create_collection(name, rows, dense, keywords)
    try:
        q, q_keywords = query()
        keys = ["a", "b", "c", "none"]
        served = store.agency_scores(name, keys, q, q_keywords, 5)
        expected = oracle.agency_scores(name, keys, q, q_keywords, 5)
        assert np.allclose(served[0], expected[0], atol=1e-4)
        assert np.allclose(served[1], expected[1], atol=1e-4)
    finally:
        store.delete_collection(name)
    assert not store.collection_exists(name)


def test_qdrant_local_mode_gives_the_oracle_scores(local_qdrant):
    check_parity(local_qdrant)


@pytest.mark.parametrize("kind", ["memory", "qdrant"])
def test_nearest_texts_ride_along_without_changing_scores(kind, local_qdrant):
    """The second opinion's examples: each agency's nearest stored texts, best first."""
    store = MemoryIndexStore() if kind == "memory" else local_qdrant
    rows, dense, keywords = tiny_collection()
    store.create_collection("texts", rows, dense, keywords)
    q, q_keywords = query()
    keys = ["a", "b", "c", "none"]

    plain = store.agency_scores("texts", keys, q, q_keywords, 5)
    d, k, texts = store.agency_scores("texts", keys, q, q_keywords, 5, with_texts=True)

    assert np.array_equal(d, plain[0]) and np.array_equal(k, plain[1])
    sims = q @ dense.T
    nearest_a = [f"text {i}" for i in np.argsort(-sims[0, :7])[:5]]
    assert texts[0][0] == nearest_a
    assert len(texts[0][1]) == 3  # b has fewer rows than knn_k
    assert texts[1][3] == []  # no rows
    with_texts = score(
        store, "texts", keys, q, q_keywords, ScoringParams(), with_texts=True
    )
    assert with_texts.texts == texts
    assert np.array_equal(
        with_texts.fused,
        score(store, "texts", keys, q, q_keywords, ScoringParams()).fused,
    )


@pytest.mark.parametrize("kind", ["memory", "qdrant"])
def test_typical_texts_are_closest_to_the_agency_mean(kind, local_qdrant):
    """The second opinion's catalogue: each agency's questions nearest its mean, questions only."""
    store = MemoryIndexStore() if kind == "memory" else local_qdrant
    rows, dense, keywords = tiny_collection()
    # One of a's rows isn't a question; it must not be picked or counted in the mean
    rows[0] = Row("a", "A", "passage", "a passage")
    store.create_collection("typical", rows, dense, keywords)

    typical = store.typical_texts("typical", ["a", "b", "c", "none"], 3)

    a = dense[1:7]
    expected_a = [
        f"text {1 + i}" for i in np.argsort(-(a @ a.mean(axis=0)), kind="stable")[:3]
    ]
    assert typical[0] == expected_a
    assert len(typical[1]) == 3 and set(typical[1]) == {"text 7", "text 8", "text 9"}
    assert len(typical[2]) == 3
    assert typical[3] == []  # no rows


@pytest.mark.qdrant_server
def test_qdrant_server_gives_the_oracle_scores(server_qdrant):
    check_parity(server_qdrant)


def test_qdrant_collection_layout(local_qdrant):
    rows, dense, keywords = tiny_collection()
    local_qdrant.create_collection("layout", rows, dense, keywords)

    info = local_qdrant.client.get_collection("layout")
    assert info.config.params.vectors[DENSE].size == 8
    assert info.config.params.vectors[DENSE].distance.value == "Cosine"
    assert KEYWORDS in info.config.params.sparse_vectors
    assert local_qdrant.describe("layout").points == len(rows)

    first = local_qdrant.client.retrieve("layout", [0, 15], with_payload=True)
    payloads = {point.id: point.payload for point in first}
    assert payloads[0] == {
        "agency_id": "a",
        "agency_name": "A",
        "kind": QUESTION,
        "text": "text 0",
        "source": "",
    }
    assert payloads[15]["agency_id"] == "c"


def test_parity_through_scoring_on_the_fixture(local_qdrant, index_data, encoder):
    rows, agencies = index_data["rows"], index_data["agencies"]
    keys = [a.key for a in agencies]
    oracle = MemoryIndexStore()
    for store in (oracle, local_qdrant):
        store.create_collection(
            "fixture", rows, index_data["dense"], index_data["keyword_vectors"]
        )
    messages = [
        "Mul on vaja uut passi",
        "tarbija kaebus",
        "Smart-ID ei tööta",
        "tomatid",
    ]
    vectors, keyword_vectors = (
        encoder.encode(messages),
        index_data["keywords"].transform(messages),
    )

    a = score(oracle, "fixture", keys, vectors, keyword_vectors, ScoringParams())
    b = score(local_qdrant, "fixture", keys, vectors, keyword_vectors, ScoringParams())

    assert np.allclose(a.fused, b.fused, atol=1e-4)
    assert (ranking(a.fused)[:, :5] == ranking(b.fused)[:, :5]).all()


def test_mismatched_inputs_are_refused():
    rows, dense, keywords = tiny_collection()
    with pytest.raises(ValueError):
        MemoryIndexStore().create_collection("bad", rows[:-1], dense, keywords)


def test_rows_without_keywords_are_stored(local_qdrant):
    rows = [Row("a", "A", QUESTION, "x"), Row("a", "A", QUESTION, "y")]
    dense = np.eye(2, 4, dtype=np.float32)
    keywords = KeywordVectorizer.fit(["abc abc", "abc abd"]).transform(["x", "y"])
    assert keywords.nnz == 0

    local_qdrant.create_collection("empty_keywords", rows, dense, keywords)
    assert local_qdrant.describe("empty_keywords").points == 2


@pytest.mark.qdrant_server
def test_snapshot_and_restore_round_trip(server_qdrant, tmp_path):
    from builder.snapshots import restore_snapshot, take_snapshot

    rows, dense, keywords = tiny_collection()
    name = f"test_{uuid.uuid4().hex[:8]}"
    url = os.environ["QDRANT_URL"]
    server_qdrant.create_collection(name, rows, dense, keywords)
    q, q_keywords = query()
    before = server_qdrant.agency_scores(name, ["a", "b", "c"], q, q_keywords, 5)
    try:
        take_snapshot(
            server_qdrant.client, url, None, name, tmp_path / "collection.snapshot"
        )
        server_qdrant.delete_collection(name)
        assert not server_qdrant.collection_exists(name)

        restore_snapshot(url, None, name, tmp_path / "collection.snapshot")
        assert server_qdrant.describe(name).points == len(rows)
        after = server_qdrant.agency_scores(name, ["a", "b", "c"], q, q_keywords, 5)
        assert np.allclose(before[0], after[0]) and np.allclose(before[1], after[1])
        # The snapshot was removed from the Qdrant node after download
        assert server_qdrant.client.list_snapshots(name) == []
    finally:
        server_qdrant.delete_collection(name)
