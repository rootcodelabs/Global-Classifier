"""Evaluation measures."""

import numpy as np
import pytest

from embedding_classifier.evaluation import (
    coverage_at,
    off_topic,
    per_agency,
    routed,
    topk_accuracy,
)


def test_topk_accuracy():
    fused = np.array([[0.9, 0.5, 0.1], [0.2, 0.9, 0.5], [0.1, 0.2, 0.9]])
    truth = np.array([0, 2, 0])
    assert topk_accuracy(fused, truth, ks=(1, 2, 3)) == {
        "top1": pytest.approx(1 / 3),
        "top2": pytest.approx(2 / 3),
        "top3": 1.0,
    }


def test_coverage_at_90():
    margin = np.linspace(1.0, 0.0, 20)
    correct = np.array([True] * 18 + [False] * 2)
    correct[9] = False
    # Running accuracy is 17/18 after 18 messages, then 17/19 (under 90%) and 17/20
    assert coverage_at(margin, correct, 0.9) == pytest.approx(18 / 20)


def test_routed_by_threshold():
    margin = np.array([0.9, 0.5, 0.2, 0.1])
    correct = np.array([True, False, True, True])
    assert routed(margin, correct, 0.4) == {"share": 0.5, "accuracy": 0.5}
    assert routed(margin, correct, None)["share"] == 0.0


def test_off_topic_measures():
    result = off_topic(
        np.array([0.3, 0.7]), np.array([0.8, 0.9, 0.4, 0.95]), cutoff=0.5
    )
    assert result == {"caught": 0.5, "wrongly_flagged": 0.25}


def test_per_agency_scores():
    result = per_agency(np.array([0, 0, 1, 1]), np.array([0, 1, 1, 1]), 3)
    assert result["recall"] == pytest.approx([1.0, 2 / 3, 0.0])
    assert result["precision"] == pytest.approx([0.5, 1.0, 0.0])
