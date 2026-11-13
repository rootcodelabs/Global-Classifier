"""Fusion, margin, decisions and confidences."""

import numpy as np
import pytest

from embedding_classifier.gate import (
    CLARIFY,
    OUT_OF_DISTRIBUTION,
    ROUTE,
    GateParams,
    confidences,
    decide,
    margins,
)
from embedding_classifier.scoring import Scores, fuse, rescale_rows


def test_rescale_maps_each_row_to_0_1():
    x = np.array([[0.2, 0.5, 0.8], [1.0, 3.0, 2.0]])
    assert np.allclose(rescale_rows(x), [[0, 0.5, 1], [0, 1, 0.5]])


def test_rescale_of_a_constant_row_is_zero():
    assert np.all(rescale_rows(np.array([[0.4, 0.4, 0.4]])) == 0)


def test_fuse_adds_rescaled_keywords_at_their_weight():
    dense = np.array([[0.2, 0.6, 0.4]])
    keywords = np.array([[0.0, 0.1, 0.5]])
    assert np.allclose(fuse(dense, keywords, 0.3), [[0.0, 1.0 + 0.3 * 0.2, 0.5 + 0.3]])


def test_margin_is_relative_gap_between_the_top_two():
    assert np.allclose(
        margins(np.array([[1.0, 0.6, 0.1], [0.5, 0.5, 0.0]])), [0.4, 0.0]
    )
    assert margins(np.array([[0.7]]))[0] == 1.0


def scores_for(dense_rows, fused_rows):
    dense = np.array(dense_rows, dtype=float)
    fused = np.array(fused_rows, dtype=float)
    return Scores(dense=dense, keywords=np.zeros_like(dense), fused=fused)


GATE = GateParams(ood_cutoff=0.5, route_margin=0.3, temperature=0.05)


def test_each_decision_branch():
    scores = scores_for(
        [[0.9, 0.6, 0.5, 0.1], [0.9, 0.85, 0.8, 0.1], [0.4, 0.3, 0.2, 0.1]],
        [[1.2, 0.6, 0.5, 0.0], [1.0, 0.95, 0.9, 0.0], [1.3, 0.2, 0.1, 0.0]],
    )
    route, clarify, ood = decide(scores, GATE)

    assert (route.decision, route.candidates) == (ROUTE, [0])
    assert route.margin == pytest.approx(0.5)
    assert (clarify.decision, clarify.candidates) == (CLARIFY, [0, 1, 2])
    # Off-topic goes by the raw dense top score, whatever the fused margin says
    assert (ood.decision, ood.candidates) == (OUT_OF_DISTRIBUTION, [])
    assert ood.top_similarity == pytest.approx(0.4)


def test_no_route_margin_means_nothing_is_routed():
    scores = scores_for([[0.9, 0.1]], [[1.3, 0.0]])
    params = GateParams(ood_cutoff=0.5, route_margin=None, temperature=0.05)
    assert decide(scores, params)[0].decision == CLARIFY


def test_confidences_are_a_softmax_over_all_agencies():
    c = confidences(np.array([[1.0, 0.5, 0.0]]), 0.1)
    assert c.sum() == pytest.approx(1.0)
    assert c[0, 0] / c[0, 1] == pytest.approx(np.exp(5))
