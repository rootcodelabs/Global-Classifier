"""Classifier layer: training, combining with the neighbour scores, choosing weights, saving."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from builder.index_build import SCORING_CONFIG_FILE, ScoringConfig
from embedding_classifier import classifier_layer
from embedding_classifier.classifier_layer import (
    KEYWORDS,
    KNN,
    ClassifierLayer,
    LayerParams,
    choose_weights,
    fit,
)
from embedding_classifier.gate import ranking
from embedding_classifier.scoring import ScoringParams, score
from embedding_classifier.vector_store import MemoryIndexStore


@pytest.fixture
def scored(index_data):
    """The fixture's rows in a memory store, scored against themselves, and its truth."""
    store = MemoryIndexStore()
    store.create_collection(
        "c", index_data["rows"], index_data["dense"], index_data["keyword_vectors"]
    )
    keys = [a.key for a in index_data["agencies"]]
    truth = np.array([keys.index(row.agency_key) for row in index_data["rows"]])
    scores = score(
        store,
        "c",
        keys,
        index_data["dense"],
        index_data["keyword_vectors"],
        ScoringParams(),
    )
    return scores, index_data["keyword_vectors"], truth


def test_combined_scores_are_probabilities_and_keep_the_rest(scored):
    scores, keywords, truth = scored
    layer = fit(keywords, truth, 3)

    combined = layer.apply(scores, keywords)

    assert combined.fused.shape == scores.fused.shape
    np.testing.assert_allclose(combined.fused.sum(axis=1), 1.0)
    assert combined.dense is scores.dense and combined.keywords is scores.keywords
    # Trained and scored on the same rows: every one is right
    assert (ranking(combined.fused)[:, 0] == truth).all()


def test_a_zero_regression_weight_keeps_the_neighbour_ranking(scored):
    scores, keywords, truth = scored
    layer = replace(fit(keywords, truth, 3), weights={KNN: 1.0, KEYWORDS: 0.0})

    combined = layer.apply(scores, keywords)

    assert (ranking(combined.fused) == ranking(scores.fused)).all()


def test_chosen_weights_are_at_least_as_good_as_the_neighbours_alone(scored):
    scores, keywords, truth = scored
    layer, top1 = choose_weights(fit(keywords, truth, 3), scores, keywords, truth)

    assert layer.weights[KNN] > 0
    assert layer.knn_scale in classifier_layer.KNN_SCALES
    assert set(top1) == {KNN, KEYWORDS, "combined"}
    assert top1["combined"] >= top1[KNN]
    assert top1["combined"] == pytest.approx(
        np.mean(ranking(layer.apply(scores, keywords).fused)[:, 0] == truth)
    )


def test_an_agency_missing_from_the_rows_is_never_picked(scored):
    scores, keywords, truth = scored
    kept = truth != 2
    layer = fit(keywords[kept], truth[kept], 3, weights={KNN: 0.0, KEYWORDS: 1.0})

    assert layer.coef.shape == (3, keywords.shape[1])
    assert not (ranking(layer.apply(scores, keywords).fused)[:, 0] == 2).any()


def test_one_agency_is_refused(scored):
    _, keywords, truth = scored
    with pytest.raises(ValueError, match="two agencies"):
        fit(keywords[truth == 0], truth[truth == 0], 3)


def test_save_and_load_round_trip(scored, tmp_path):
    scores, keywords, truth = scored
    layer = fit(
        keywords, truth, 3, LayerParams(c=5.0), {KNN: 0.5, KEYWORDS: 0.25}, 100.0
    )
    path = tmp_path / classifier_layer.LAYER_FILE
    layer.save(path)

    loaded = ClassifierLayer.load(path)

    assert loaded.weights == {KNN: 0.5, KEYWORDS: 0.25}
    assert loaded.knn_scale == 100.0
    np.testing.assert_allclose(
        loaded.apply(scores, keywords).fused,
        layer.apply(scores, keywords).fused,
        rtol=1e-5,
    )


def test_unknown_format_is_refused(scored, tmp_path):
    _, keywords, truth = scored
    path = tmp_path / classifier_layer.LAYER_FILE
    fit(keywords, truth, 3).save(path)
    with np.load(path) as data:
        arrays = dict(data)
    arrays["format_version"] = np.array(99)
    np.savez(path, **arrays)

    with pytest.raises(ValueError, match="Unsupported classifier layer format 99"):
        ClassifierLayer.load(path)


def test_the_layer_follows_scoring_json():
    config = json.loads(Path(SCORING_CONFIG_FILE).read_text())
    expected = (
        LayerParams(c=config["classifier_c"]) if config["classifier_layer"] else None
    )
    assert ScoringConfig.load().layer_params() == expected
    # Without the file's values, the layer is off
    assert ScoringConfig().layer_params() is None
    assert ScoringConfig(
        classifier_layer=True, classifier_c=3
    ).layer_params() == LayerParams(c=3)
