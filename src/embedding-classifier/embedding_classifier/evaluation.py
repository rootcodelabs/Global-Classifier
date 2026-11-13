"""
Measures for an index: top-k accuracy, per-agency precision, recall and F1,
the share routed at 90% accuracy, and off-topic detection.
"""

from typing import Optional

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from embedding_classifier.gate import ranking


def topk_accuracy(
    fused: np.ndarray, truth: np.ndarray, ks=(1, 3, 5)
) -> dict[str, float]:
    """Share of messages whose true agency is among the top k, for each k."""
    order = ranking(fused)
    rank = np.argmax(order == truth[:, None], axis=1)
    return {f"top{k}": float(np.mean(rank < k)) for k in ks}


def per_agency(
    predicted: np.ndarray, truth: np.ndarray, n_agencies: int
) -> dict[str, list[float]]:
    """Precision, recall and F1 per agency position, 0 where undefined."""
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, predicted, labels=np.arange(n_agencies), zero_division=0
    )
    return {
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "f1": f1.tolist(),
    }


def coverage_at(margin: np.ndarray, correct: np.ndarray, target: float = 0.9) -> float:
    """
    The largest share of messages, most confident (highest margin) first, whose
    top-1 accuracy is at least target.
    """
    order = np.argsort(-margin, kind="stable")
    running = np.cumsum(correct[order]) / np.arange(1, len(order) + 1)
    reached = np.nonzero(running >= target)[0]
    return float((reached.max() + 1) / len(order)) if len(reached) else 0.0


def routed(
    margin: np.ndarray, correct: np.ndarray, route_margin: Optional[float]
) -> dict[str, float]:
    """Share routed by a margin threshold, and the accuracy of what was routed."""
    if route_margin is None:
        return {"share": 0.0, "accuracy": float("nan")}
    sent = margin >= route_margin
    return {
        "share": float(np.mean(sent)),
        "accuracy": float(np.mean(correct[sent])) if sent.any() else float("nan"),
    }


def off_topic(
    off_topic_top: np.ndarray, in_domain_top: np.ndarray, cutoff: float
) -> dict[str, float]:
    """Off-topic messages caught and real questions wrongly flagged by a raw dense cutoff."""
    return {
        "caught": float(np.mean(off_topic_top < cutoff)),
        "wrongly_flagged": float(np.mean(in_domain_top < cutoff)),
    }
