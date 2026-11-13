"""
Confidence gate: ranks agencies by fused score, then routes, asks the citizen
to clarify, or flags the message as off-topic.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from embedding_classifier.scoring import Scores

ROUTE = "route"
CLARIFY = "clarify"
OUT_OF_DISTRIBUTION = "out_of_distribution"


@dataclass(frozen=True)
class GateParams:
    """
    ood_cutoff: a raw dense top score below this is off-topic
    route_margin: a margin at or above this routes; None routes nothing
    temperature: softmax temperature that turns fused scores into confidences
    """

    ood_cutoff: float
    route_margin: Optional[float]
    temperature: float
    route_target_accuracy: float = 0.9
    top_k: int = 5
    clarify_candidates: int = 3


@dataclass(frozen=True)
class Decision:
    decision: str
    margin: float
    top_similarity: float
    candidates: list[int]  # agency positions, best first


def ranking(fused: np.ndarray) -> np.ndarray:
    """Agency positions per message, best first; ties keep agency order."""
    return np.argsort(-fused, axis=1, kind="stable")


def margins(fused: np.ndarray) -> np.ndarray:
    """(f1 - f2) / max(|f1|, 1e-9) of each message's top two fused scores."""
    if fused.shape[1] < 2:
        return np.ones(fused.shape[0])
    top_two = -np.sort(-fused, axis=1)[:, :2]
    return (top_two[:, 0] - top_two[:, 1]) / np.maximum(np.abs(top_two[:, 0]), 1e-9)


def softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - x.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def confidences(fused: np.ndarray, temperature: float) -> np.ndarray:
    return softmax(fused / temperature)


def decide(scores: Scores, params: GateParams) -> list[Decision]:
    """One decision per message."""
    order = ranking(scores.fused)
    margin = margins(scores.fused)
    top_similarity = scores.top_similarity
    decisions = []
    for i in range(len(order)):
        if top_similarity[i] < params.ood_cutoff:
            decision, candidates = OUT_OF_DISTRIBUTION, []
        elif params.route_margin is not None and margin[i] >= params.route_margin:
            decision, candidates = ROUTE, [int(order[i, 0])]
        else:
            decision = CLARIFY
            candidates = [int(a) for a in order[i, : params.clarify_candidates]]
        decisions.append(
            Decision(decision, float(margin[i]), float(top_similarity[i]), candidates)
        )
    return decisions
