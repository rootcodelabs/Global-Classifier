"""Rows, embedding by kind, the embedding cache and the model registry."""

import numpy as np
import pytest

from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import TASK, EmbeddingModel, get_model, load_models
from embedding_classifier.store import (
    ANSWER,
    PASSAGE,
    QUESTION,
    TITLE,
    Row,
    count_by_agency,
    embed_rows,
)


def test_each_kind_is_embedded_with_its_token_limit(encoder):
    rows = [
        Row("a", "A", QUESTION, "pass"),
        Row("a", "A", PASSAGE, "pikk tekst pass"),
        Row("b", "B", TITLE, "tarbija õigused"),
        Row("b", "B", ANSWER, "vastus"),
    ]
    vectors = embed_rows(encoder, rows)

    assert sorted(encoder.calls) == [(2, "long"), (2, "short")]
    assert np.allclose(vectors[0], encoder.encode(["pass"])[0])
    assert np.allclose(vectors[1], encoder.encode(["pikk tekst pass"])[0])


def test_count_by_agency():
    rows = [
        Row("a", "A", QUESTION, "x"),
        Row("a", "A", TITLE, "y"),
        Row("a", "A", QUESTION, "z"),
    ]
    assert count_by_agency(rows) == {"a": {"question": 2, "title": 1}}


def test_cache_embeds_only_new_texts_and_survives_a_restart(encoder, tmp_path):
    cache = EmbeddingCache(tmp_path)
    first = cache.encode(encoder, ["pass", "tarbija", "pass"], "short")
    assert encoder.calls == [(2, "short")]

    again = EmbeddingCache(tmp_path).encode(
        encoder, ["tarbija", "pass", "tomat"], "short"
    )
    assert encoder.calls == [(2, "short"), (1, "short")]
    assert np.allclose(again[:2], first[[1, 0]])


def test_cache_keeps_short_and_long_apart(encoder, tmp_path):
    cache = EmbeddingCache(tmp_path)
    cache.encode(encoder, ["pass"], "short")
    cache.encode(encoder, ["pass"], "long")
    assert encoder.calls == [(1, "short"), (1, "long")]
    assert len(list(tmp_path.glob("*.npz"))) == 2


def test_cache_refuses_a_file_from_another_model(encoder, tmp_path):
    EmbeddingCache(tmp_path).encode(encoder, ["pass"], "short")
    # Same file name (model name and revision prefix), different model
    encoder.model = EmbeddingModel("other", "other/bge-m3", encoder.model.revision)

    with pytest.raises(ValueError, match="holds"):
        EmbeddingCache(tmp_path).encode(encoder, ["pass"], "short")


def test_model_registry_pins_a_revision_for_each_model():
    models = load_models()
    assert set(models) == {
        "multilingual-e5-large-instruct",
        "bge-m3",
        "paraphrase-multilingual-mpnet-base-v2",
    }
    assert all(len(m.revision) == 40 for m in models.values())


def test_prompts():
    assert (
        get_model("multilingual-e5-large-instruct").prompt
        == f"Instruct: {TASK}\nQuery: "
    )
    assert get_model("bge-m3").prompt == ""


def test_unknown_model_key():
    with pytest.raises(KeyError, match="Unknown embedding model"):
        get_model("estbert")
