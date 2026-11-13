"""
Gate thresholds set from held-out calibration questions; the test split is
never used.
"""

from typing import Optional

import numpy as np

from embedding_classifier.gate import GateParams, margins, ranking
from embedding_classifier.scoring import Scores

KEEP_RATIO = 0.95
ROUTE_TARGET_ACCURACY = 0.9
DEFAULT_TEMPERATURE = 0.05
TEMPERATURE_GRID = np.linspace(0.01, 1.0, 100)
MIN_CALIBRATION_MESSAGES = 300


def ood_cutoff(top_similarities: np.ndarray, keep_ratio: float = KEEP_RATIO) -> float:
    """The raw dense top score that keep_ratio of real questions reach."""
    return float(np.quantile(top_similarities, 1.0 - keep_ratio))


def route_margin(
    margin: np.ndarray, correct: np.ndarray, target: float = ROUTE_TARGET_ACCURACY
) -> Optional[float]:
    """
    The margin threshold of the largest most-confident share of messages whose
    top-1 accuracy is at least target; None if no share reaches it.

    Args:
        margin: Margin of each message
        correct: Whether each message's top agency is right
        target: Accuracy the routed messages must keep
    """
    order = np.argsort(-margin, kind="stable")
    running = np.cumsum(correct[order]) / np.arange(1, len(order) + 1)
    reached = np.nonzero(running >= target)[0]
    if len(reached) == 0:
        return None
    return float(margin[order[reached.max()]])


def temperature(
    fused: np.ndarray, truth: np.ndarray, grid: np.ndarray = TEMPERATURE_GRID
) -> float:
    """The grid value minimising the negative log-likelihood of the true agency."""
    if len(truth) == 0:
        return DEFAULT_TEMPERATURE
    rows = np.arange(len(truth))
    losses = []
    for t in grid:
        logits = fused / t
        shifted = logits - logits.max(axis=1, keepdims=True)
        log_probs = shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))
        losses.append(-log_probs[rows, truth].mean())
    return float(grid[int(np.argmin(losses))])


def calibrate(
    scores: Scores,
    truth: np.ndarray,
    keep_ratio: float = KEEP_RATIO,
    target: float = ROUTE_TARGET_ACCURACY,
) -> tuple[GateParams, list[str]]:
    """
    Gate thresholds from scored calibration messages.

    Args:
        scores: Scores of the calibration messages
        truth: Position of each message's true agency

    Returns:
        Gate parameters, and warnings for the report
    """
    if len(truth) == 0:
        raise ValueError("No calibration messages")
    warnings = []
    if len(truth) < MIN_CALIBRATION_MESSAGES:
        warnings.append(
            f"Only {len(truth)} calibration messages (fewer than "
            f"{MIN_CALIBRATION_MESSAGES}); the thresholds are rough"
        )
    correct = ranking(scores.fused)[:, 0] == truth
    threshold = route_margin(margins(scores.fused), correct, target)
    if threshold is None:
        warnings.append(
            f"No share of calibration messages reaches {target:.0%} accuracy"
        )
    params = GateParams(
        ood_cutoff=ood_cutoff(scores.top_similarity, keep_ratio),
        route_margin=threshold,
        temperature=temperature(scores.fused, truth),
        route_target_accuracy=target,
    )
    return params, warnings
