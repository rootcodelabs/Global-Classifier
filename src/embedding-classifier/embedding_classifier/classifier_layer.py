"""
Classifier layer: a logistic regression on the index's keyword vectors,
trained on the rows the index stores, added on top of the nearest-neighbour
search. Its log-probabilities and the neighbour scores are summed with weights
chosen on the calibration split, and the result, as probabilities, replaces the
fused score; the gate, the confidences and the second opinion work on it
unchanged. A weight of 0 for the regression is the nearest-neighbour ranking
alone, so a layer that doesn't help on calibration changes nothing.

Saved as one .npz file (no pickles), next to the manifest.
"""

import itertools
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.special import log_softmax, softmax
from sklearn.linear_model import LogisticRegression

from embedding_classifier.scoring import Scores

METHOD = "knn_keywords_classifier"
FORMAT_VERSION = 1
LAYER_FILE = "classifier_layer.npz"
KNN, KEYWORDS = "knn", "keywords"
COMPONENTS = (KNN, KEYWORDS)
WEIGHT_GRID = (0.0, 0.25, 0.5, 1.0)
# Fused scores span about 0..1.3; this sharpens them into log-probabilities
KNN_SCALES = (10.0, 30.0, 100.0)
# An agency the training rows lack is never predicted
MISSING_AGENCY_INTERCEPT = -1e9


@dataclass(frozen=True)
class LayerParams:
    """c: the regression's inverse regularisation strength."""

    c: float = 10.0
    max_iter: int = 5000


@dataclass(frozen=True)
class ClassifierLayer:
    coef: np.ndarray  # (n_agencies, n_keyword_features)
    intercept: np.ndarray  # (n_agencies,)
    weights: dict[str, float]
    knn_scale: float

    def parts(
        self, scores: Scores, keywords: sparse.csr_matrix
    ) -> dict[str, np.ndarray]:
        """Each component's log-probabilities, shape (n_messages, n_agencies)."""
        return {
            KNN: log_softmax(scores.fused * self.knn_scale, axis=1),
            KEYWORDS: log_softmax(
                np.asarray(keywords @ self.coef.T) + self.intercept, axis=1
            ),
        }

    def apply(self, scores: Scores, keywords: sparse.csr_matrix) -> Scores:
        """The scores with fused replaced by the combined probabilities."""
        combined = combine(self.parts(scores, keywords), self.weights)
        return Scores(scores.dense, scores.keywords, combined, scores.texts)

    def save(self, path: Path) -> None:
        np.savez(
            path,
            format_version=FORMAT_VERSION,
            coef=self.coef.astype(np.float32),
            intercept=self.intercept,
            weights=np.array([self.weights[c] for c in COMPONENTS]),
            knn_scale=self.knn_scale,
        )

    @classmethod
    def load(cls, path: Path) -> "ClassifierLayer":
        with np.load(path, allow_pickle=False) as data:
            if int(data["format_version"]) != FORMAT_VERSION:
                raise ValueError(
                    f"Unsupported classifier layer format {int(data['format_version'])}"
                )
            return cls(
                coef=data["coef"],
                intercept=data["intercept"],
                weights=dict(zip(COMPONENTS, data["weights"].tolist())),
                knn_scale=float(data["knn_scale"]),
            )

    def describe(self) -> dict:
        """For the manifest and the report."""
        return {"weights": dict(self.weights), "knn_scale": self.knn_scale}


def combine(parts: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    """Probabilities from the weighted sum of the components' log-probabilities."""
    total = sum(weights[c] * parts[c] for c in COMPONENTS if weights[c])
    return softmax(total, axis=1)


def fit(
    keywords: sparse.csr_matrix,
    truth: np.ndarray,
    n_agencies: int,
    params: LayerParams = LayerParams(),
    weights: dict[str, float] | None = None,
    knn_scale: float = KNN_SCALES[1],
) -> ClassifierLayer:
    """
    Train the regression on an index's rows.

    Args:
        keywords: The rows' keyword vectors
        truth: Agency position of each row; at least two agencies
        weights, knn_scale: Chosen later with choose_weights when not known yet
    """
    if len(np.unique(truth)) < 2:
        raise ValueError("The classifier layer needs at least two agencies")
    model = LogisticRegression(C=params.c, max_iter=params.max_iter).fit(
        keywords, truth
    )
    coef = np.zeros((n_agencies, keywords.shape[1]))
    intercept = np.full(n_agencies, MISSING_AGENCY_INTERCEPT)
    coef[model.classes_] = model.coef_
    intercept[model.classes_] = model.intercept_
    return ClassifierLayer(
        coef, intercept, weights or {KNN: 1.0, KEYWORDS: 1.0}, knn_scale
    )


def choose_weights(
    layer: ClassifierLayer,
    scores: Scores,
    keywords: sparse.csr_matrix,
    truth: np.ndarray,
) -> tuple[ClassifierLayer, dict[str, float]]:
    """
    The layer with the weights and neighbour scale that give the best top-1
    on calibration messages; the first in grid order wins a tie, so equal
    accuracy keeps the smallest regression weight.

    Returns:
        The layer, and the top-1 of each component alone and combined
    """
    best = None
    for scale in KNN_SCALES:
        candidate = replace(layer, knn_scale=scale)
        parts = candidate.parts(scores, keywords)
        for values in itertools.product(WEIGHT_GRID, repeat=len(COMPONENTS)):
            if not values[0]:
                # The neighbour scores always count; the regression may not
                continue
            weights = dict(zip(COMPONENTS, values))
            accuracy = _top1(combine(parts, weights), truth)
            if best is None or accuracy > best[0]:
                best = (accuracy, replace(candidate, weights=weights), parts)
    accuracy, chosen, parts = best
    alone = {c: _top1(parts[c], truth) for c in COMPONENTS}
    return chosen, {**alone, "combined": accuracy}


def _top1(scores: np.ndarray, truth: np.ndarray) -> float:
    return float(np.mean(np.argmax(scores, axis=1) == truth))
