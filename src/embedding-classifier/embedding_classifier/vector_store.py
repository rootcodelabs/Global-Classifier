"""
Where an index's vectors live and how per-agency scores come out of them.
Production uses QdrantIndexStore; MemoryIndexStore has the same interface,
is the test oracle, and lets unit tests run without a server.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import sparse

from embedding_classifier.keywords import sparse_row
from embedding_classifier.store import QUESTION, Row

logger = logging.getLogger(__name__)

DENSE = "dense"
KEYWORDS = "keywords"
NO_ROWS_SCORE = -1.0


@dataclass(frozen=True)
class CollectionInfo:
    points: int
    dim: int
    status: str


class IndexStore(ABC):
    """A set of named collections of rows with a dense and a keyword vector each."""

    @abstractmethod
    def create_collection(
        self,
        name: str,
        rows: list[Row],
        dense: np.ndarray,
        keywords: sparse.csr_matrix,
    ) -> None:
        """Create the collection and store the rows; point ids are 0 to N-1 in row order."""

    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete the collection if it exists."""

    @abstractmethod
    def collection_exists(self, name: str) -> bool: ...

    @abstractmethod
    def describe(self, name: str) -> CollectionInfo: ...

    def ping(self) -> bool:
        """Whether the store answers."""
        return True

    @abstractmethod
    def agency_scores(
        self,
        name: str,
        agency_keys: list[str],
        dense_queries: np.ndarray,
        keyword_queries: sparse.csr_matrix,
        knn_k: int,
        with_texts: bool = False,
    ) -> tuple:
        """
        Per-agency scores for each query.

        Returns:
            (dense, keywords), each of shape (n_queries, len(agency_keys)).
            dense is the mean cosine similarity of the agency's knn_k closest
            rows (all of them if it has fewer; NO_ROWS_SCORE if none). keywords
            is the agency's best keyword similarity (0 with no shared n-gram).
            With with_texts, a third item: per query, per agency, the texts of
            those closest rows, best first (the second opinion's examples).
        """

    @abstractmethod
    def typical_texts(
        self, name: str, agency_keys: list[str], n: int
    ) -> list[list[str]]:
        """
        Per agency, the texts of its n question rows closest to the mean of
        its question vectors, closest first; empty for an agency without
        questions. The second opinion's catalogue lists them.
        """


def _closest_to_mean(vectors: np.ndarray, n: int) -> np.ndarray:
    """Indexes of the n vectors closest to their mean, closest first (ties by position)."""
    similarities = vectors @ vectors.mean(axis=0)
    return np.argsort(-similarities, kind="stable")[:n]


class MemoryIndexStore(IndexStore):
    """numpy store with exact scores."""

    def __init__(self):
        self._collections: dict[str, dict] = {}

    def create_collection(self, name, rows, dense, keywords) -> None:
        if name in self._collections:
            raise ValueError(f"Collection {name} already exists")
        _check_shapes(rows, dense, keywords)
        by_agency: dict[str, list[int]] = {}
        for i, row in enumerate(rows):
            by_agency.setdefault(row.agency_key, []).append(i)
        self._collections[name] = {
            "dense": np.asarray(dense, dtype=np.float32),
            "keywords": keywords.tocsr().astype(np.float32),
            "by_agency": {key: np.array(idx) for key, idx in by_agency.items()},
            "texts": [row.text for row in rows],
            "kinds": [row.kind for row in rows],
        }

    def delete_collection(self, name) -> None:
        self._collections.pop(name, None)

    def collection_exists(self, name) -> bool:
        return name in self._collections

    def describe(self, name) -> CollectionInfo:
        dense = self._collections[name]["dense"]
        return CollectionInfo(points=dense.shape[0], dim=dense.shape[1], status="green")

    def agency_scores(
        self, name, agency_keys, dense_queries, keyword_queries, knn_k, with_texts=False
    ):
        collection = self._collections[name]
        similarities = (
            np.asarray(dense_queries, dtype=np.float32) @ collection["dense"].T
        )
        keyword_sims = (
            keyword_queries.astype(np.float32) @ collection["keywords"].T
        ).toarray()
        n = len(dense_queries)
        dense = np.full((n, len(agency_keys)), NO_ROWS_SCORE, dtype=np.float32)
        keywords = np.zeros((n, len(agency_keys)), dtype=np.float32)
        texts = [[[] for _ in agency_keys] for _ in range(n)]
        for j, key in enumerate(agency_keys):
            columns = collection["by_agency"].get(key)
            if columns is None or n == 0:
                continue
            agency_sims = similarities[:, columns]
            k = min(knn_k, agency_sims.shape[1])
            top = np.partition(agency_sims, agency_sims.shape[1] - k, axis=1)[:, -k:]
            dense[:, j] = top.mean(axis=1)
            keywords[:, j] = keyword_sims[:, columns].max(axis=1)
            if with_texts:
                nearest = np.argsort(-agency_sims, axis=1, kind="stable")[:, :k]
                for q in range(n):
                    texts[q][j] = [collection["texts"][columns[c]] for c in nearest[q]]
        return (dense, keywords, texts) if with_texts else (dense, keywords)

    def typical_texts(self, name, agency_keys, n):
        collection = self._collections[name]
        result = []
        for key in agency_keys:
            rows = [
                i
                for i in collection["by_agency"].get(key, [])
                if collection["kinds"][i] == QUESTION
            ]
            if not rows:
                result.append([])
                continue
            closest = _closest_to_mean(collection["dense"][rows], n)
            result.append([collection["texts"][rows[c]] for c in closest])
        return result


class QdrantIndexStore(IndexStore):
    """
    Qdrant store. Each collection has a dense vector "dense" (cosine) and a
    sparse vector "keywords" (TF-IDF weights, no IDF modifier), and keyword
    payload indexes on agency_id and kind.
    """

    def __init__(
        self,
        client,
        exact: bool = True,
        upload_batch: int = 256,
        requests_per_call: int = 2048,
        retries: int = 1,
    ):
        """
        Args:
            client: qdrant_client.QdrantClient (a server, or ":memory:" in tests)
            exact: Exact search; approximate (HNSW) only if the parity test passes
            upload_batch: Points per upsert call
            requests_per_call: Most search requests sent in one batch call
            retries: Extra attempts for a failed batch call
        """
        from qdrant_client import models

        self.client = client
        self.models = models
        self.upload_batch = upload_batch
        self.requests_per_call = requests_per_call
        self.retries = retries
        self.search_params = models.SearchParams(exact=exact)

    @classmethod
    def connect(
        cls,
        url: str,
        api_key: Optional[str] = None,
        timeout: float = 2.0,
        prefer_grpc: bool = False,
        **kwargs,
    ) -> "QdrantIndexStore":
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=url, api_key=api_key or None, timeout=timeout, prefer_grpc=prefer_grpc
        )
        return cls(client, **kwargs)

    def create_collection(self, name, rows, dense, keywords) -> None:
        m = self.models
        _check_shapes(rows, dense, keywords)
        self.client.create_collection(
            name,
            vectors_config={
                DENSE: m.VectorParams(size=dense.shape[1], distance=m.Distance.COSINE)
            },
            sparse_vectors_config={KEYWORDS: m.SparseVectorParams()},
        )
        # Indexes before points, so they cover every upload
        for field in ("agency_id", "kind"):
            self.client.create_payload_index(name, field, m.PayloadSchemaType.KEYWORD)

        keywords = keywords.tocsr()
        for start in range(0, len(rows), self.upload_batch):
            points = []
            for i in range(start, min(start + self.upload_batch, len(rows))):
                row = rows[i]
                vector = {DENSE: dense[i].tolist()}
                indices, values = sparse_row(keywords, i)
                if indices:
                    vector[KEYWORDS] = m.SparseVector(indices=indices, values=values)
                points.append(
                    m.PointStruct(
                        id=i,
                        vector=vector,
                        payload={
                            "agency_id": row.agency_key,
                            "agency_name": row.agency_name,
                            "kind": row.kind,
                            "text": row.text,
                            "source": row.source,
                        },
                    )
                )
            self.client.upsert(name, points, wait=True)

        stored = self.client.count(name, exact=True).count
        if stored != len(rows):
            raise RuntimeError(
                f"Collection {name} has {stored} points, expected {len(rows)}"
            )
        logger.info(f"Created collection {name} with {stored} points")

    def delete_collection(self, name) -> None:
        if self.client.collection_exists(name):
            self.client.delete_collection(name)

    def collection_exists(self, name) -> bool:
        return self.client.collection_exists(name)

    def ping(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def describe(self, name) -> CollectionInfo:
        info = self.client.get_collection(name)
        status = getattr(info.status, "value", info.status)
        return CollectionInfo(
            points=info.points_count or 0,
            dim=info.config.params.vectors[DENSE].size,
            status=str(status),
        )

    def agency_scores(
        self, name, agency_keys, dense_queries, keyword_queries, knn_k, with_texts=False
    ):
        m = self.models
        filters = [
            m.Filter(
                must=[m.FieldCondition(key="agency_id", match=m.MatchValue(value=key))]
            )
            for key in agency_keys
        ]
        keyword_queries = keyword_queries.tocsr()
        n = len(dense_queries)
        dense = np.full((n, len(agency_keys)), NO_ROWS_SCORE, dtype=np.float32)
        keywords = np.zeros((n, len(agency_keys)), dtype=np.float32)
        texts = [[[] for _ in agency_keys] for _ in range(n)]
        # The texts ride along on the dense requests; the scores don't change
        dense_payload = ["text"] if with_texts else False

        # Two requests per agency and message, sent a few messages per call
        per_call = max(1, self.requests_per_call // (2 * max(1, len(agency_keys))))
        for first in range(0, n, per_call):
            requests, slots = [], []
            for q in range(first, min(first + per_call, n)):
                vector = dense_queries[q].tolist()
                indices, values = sparse_row(keyword_queries, q)
                for j, agency_filter in enumerate(filters):
                    requests.append(
                        m.QueryRequest(
                            query=vector,
                            using=DENSE,
                            filter=agency_filter,
                            limit=knn_k,
                            params=self.search_params,
                            with_payload=dense_payload,
                        )
                    )
                    slots.append((q, j, DENSE))
                    # A message with no known n-gram matches nothing; its keyword scores stay 0
                    if indices:
                        requests.append(
                            m.QueryRequest(
                                query=m.SparseVector(indices=indices, values=values),
                                using=KEYWORDS,
                                filter=agency_filter,
                                limit=1,
                                params=self.search_params,
                                with_payload=False,
                            )
                        )
                        slots.append((q, j, KEYWORDS))

            for (q, j, using), response in zip(
                slots, self._query_batch(name, requests)
            ):
                scores = [point.score for point in response.points]
                if not scores:
                    continue
                if using == DENSE:
                    dense[q, j] = np.mean(scores)
                    if with_texts:
                        texts[q][j] = [
                            (point.payload or {}).get("text", "")
                            for point in response.points
                        ]
                else:
                    keywords[q, j] = max(scores)
        return (dense, keywords, texts) if with_texts else (dense, keywords)

    def typical_texts(self, name, agency_keys, n, page: int = 256):
        m = self.models
        result = []
        for key in agency_keys:
            question_filter = m.Filter(
                must=[
                    m.FieldCondition(key="agency_id", match=m.MatchValue(value=key)),
                    m.FieldCondition(key="kind", match=m.MatchValue(value=QUESTION)),
                ]
            )
            points, offset = [], None
            while True:
                batch, offset = self.client.scroll(
                    name,
                    scroll_filter=question_filter,
                    limit=page,
                    offset=offset,
                    with_payload=["text"],
                    with_vectors=[DENSE],
                )
                points += batch
                if offset is None:
                    break
            if not points:
                result.append([])
                continue
            # Point ids are row order, so the result doesn't depend on Qdrant's paging
            points.sort(key=lambda point: point.id)
            vectors = np.array(
                [point.vector[DENSE] for point in points], dtype=np.float32
            )
            closest = _closest_to_mean(vectors, n)
            result.append([(points[c].payload or {}).get("text", "") for c in closest])
        return result

    def _query_batch(self, name: str, requests: list):
        for attempt in range(self.retries + 1):
            try:
                return self.client.query_batch_points(name, requests)
            except Exception as error:
                if attempt == self.retries:
                    raise
                logger.warning(f"Qdrant batch query failed ({error}); retrying")


def _check_shapes(
    rows: list[Row], dense: np.ndarray, keywords: sparse.csr_matrix
) -> None:
    if len(rows) != dense.shape[0] or len(rows) != keywords.shape[0]:
        raise ValueError(
            f"{len(rows)} rows, {dense.shape[0]} dense and {keywords.shape[0]} keyword vectors"
        )
