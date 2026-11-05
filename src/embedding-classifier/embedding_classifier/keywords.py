"""
Keyword vectors: character n-gram TF-IDF fitted on the stored texts. Saved as
JSON (no pickles) and rebuilt from it when an index loads.
"""

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

FORMAT_VERSION = 1

# Output rows are L2-normalised, so a dot product is a cosine similarity
TFIDF_PARAMS = {
    "analyzer": "char_wb",
    "ngram_range": [3, 5],
    "min_df": 2,
    "sublinear_tf": True,
}


class KeywordVectorizer:
    """A fitted TF-IDF vectorizer with a JSON form."""

    def __init__(self, vectorizer: TfidfVectorizer, params: dict):
        self._vectorizer = vectorizer
        self.params = params

    @classmethod
    def fit(cls, texts: list[str], params: dict = TFIDF_PARAMS) -> "KeywordVectorizer":
        vectorizer = TfidfVectorizer(**_sklearn_params(params))
        vectorizer.fit(texts)
        return cls(vectorizer, dict(params))

    @property
    def size(self) -> int:
        return len(self._vectorizer.vocabulary_)

    def transform(self, texts: list[str]) -> sparse.csr_matrix:
        """Keyword vectors of shape (len(texts), size), float32, unit length or empty."""
        return self._vectorizer.transform(texts).astype(np.float32).tocsr()

    def to_json(self) -> dict:
        vocabulary = self._vectorizer.vocabulary_
        return {
            "format_version": FORMAT_VERSION,
            "params": self.params,
            "vocabulary": {term: int(index) for term, index in vocabulary.items()},
            "idf": [float(value) for value in self._vectorizer.idf_],
        }

    @classmethod
    def from_json(cls, data: dict) -> "KeywordVectorizer":
        if data.get("format_version") != FORMAT_VERSION:
            raise ValueError(
                f"Unsupported keywords format {data.get('format_version')}"
            )
        # A fixed vocabulary plus idf_ is sklearn's supported way to rebuild
        # a fitted vectorizer without refitting
        vectorizer = TfidfVectorizer(
            **_sklearn_params(data["params"]), vocabulary=data["vocabulary"]
        )
        vectorizer.idf_ = np.asarray(data["idf"], dtype=np.float64)
        return cls(vectorizer, dict(data["params"]))


def sparse_row(matrix: sparse.csr_matrix, i: int) -> tuple[list[int], list[float]]:
    """Indices and values of one row, as the vector store takes them."""
    start, end = matrix.indptr[i], matrix.indptr[i + 1]
    return matrix.indices[start:end].tolist(), matrix.data[start:end].tolist()


def _sklearn_params(params: dict) -> dict:
    return {**params, "ngram_range": tuple(params["ngram_range"])}
