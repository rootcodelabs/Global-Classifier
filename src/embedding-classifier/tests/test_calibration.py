"""Gate calibration on synthetic arrays with known answers."""

import numpy as np
import pytest

from embedding_classifier.calibration import (
    DEFAULT_TEMPERATURE,
    calibrate,
    ood_cutoff,
    route_margin,
    temperature,
)
from embedding_classifier.gate import softmax
from embedding_classifier.scoring import Scores


def test_ood_cutoff_keeps_95_percent_of_real_questions():
    top = np.linspace(0.5, 1.0, 1001)
    cutoff = ood_cutoff(top)
    assert np.mean(top >= cutoff) == pytest.approx(0.95, abs=0.002)


def test_route_margin_is_the_margin_where_running_accuracy_last_reaches_target():
    # Most confident first: 9 right, 1 wrong (90%), then 2 wrong
    margin = np.array([0.9, 0.8, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.2, 0.1])
    correct = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0], dtype=bool)
    assert route_margin(margin, correct, 0.9) == pytest.approx(0.35)


def test_route_margin_is_none_when_no_share_is_accurate_enough():
    assert route_margin(np.array([0.9, 0.5]), np.array([False, True]), 0.9) is None


def test_temperature_recovers_the_one_that_generated_the_labels():
    rng = np.random.default_rng(0)
    fused = rng.uniform(0, 1.3, size=(4000, 10))
    probabilities = softmax(fused / 0.2)
    truth = np.array([rng.choice(10, p=p) for p in probabilities])
    assert temperature(fused, truth) == pytest.approx(0.2, abs=0.03)


def test_temperature_defaults_without_data():
    assert temperature(np.zeros((0, 3)), np.array([], dtype=int)) == DEFAULT_TEMPERATURE


def test_calibrate_warns_with_fewer_than_300_messages():
    rng = np.random.default_rng(1)
    fused = rng.uniform(size=(50, 4))
    scores = Scores(dense=fused * 0.5 + 0.3, keywords=np.zeros_like(fused), fused=fused)
    params, warnings = calibrate(scores, fused.argmax(axis=1))

    assert params.route_margin is not None
    assert 0.01 <= params.temperature <= 1.0
    assert any("fewer than 300" in w for w in warnings)
