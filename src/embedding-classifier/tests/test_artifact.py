"""Build files: round trip, checksums, and refusing another model or revision."""

import json

import pytest

from embedding_classifier.artifact import (
    KEYWORDS_FILE,
    ArtifactError,
    agencies_from_manifest,
    build_manifest,
    check_model,
    collection_name,
    gate_from_manifest,
    read_build_files,
    scoring_from_manifest,
    write_build_files,
)
from embedding_classifier.encoder import EmbeddingModel
from embedding_classifier.gate import GateParams
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import ScoringParams
from embedding_classifier.store import Agency

MODEL = EmbeddingModel(
    "multilingual-e5-large-instruct",
    "intfloat/multilingual-e5-large-instruct",
    "a" * 40,
)
AGENCIES = [
    Agency(123, "Maksu- ja Tolliamet"),
    Agency("ppa", "Politsei- ja Piirivalveamet"),
]


def make_build(folder):
    keywords = KeywordVectorizer.fit(
        ["maks ja tolliamet", "pass ja politsei", "maksu tagastus"]
    )
    gate = GateParams(ood_cutoff=0.61, route_margin=0.12, temperature=0.05)
    manifest = build_manifest(
        model_id=42,
        model=MODEL,
        dim=1024,
        collection=collection_name(42),
        points=3,
        scoring=ScoringParams(),
        gate=gate,
        keywords=keywords,
        agencies=AGENCIES,
        counts={"123": {"question": 2}, "ppa": {"question": 1}},
        dataset={"id": 9, "major": 1, "minor": 2},
        built_at="2026-10-30T12:00:00Z",
    )
    written = write_build_files(folder, manifest, keywords, {"passed": True})
    return written, keywords, gate


def test_build_files_round_trip(tmp_path):
    written, keywords, gate = make_build(tmp_path)
    manifest, rebuilt = read_build_files(tmp_path)

    assert manifest == written
    assert manifest["vector_store"]["collection"] == "gc_index_42"
    assert set(manifest["files"]) == {"keywords.json", "quality_report.json"}
    assert gate_from_manifest(manifest) == gate
    assert scoring_from_manifest(manifest) == ScoringParams()
    # Agency ids keep their JSON types
    assert agencies_from_manifest(manifest) == AGENCIES
    texts = ["maksu tagastus", "pass"]
    assert (rebuilt.transform(texts) != keywords.transform(texts)).nnz == 0


def test_changed_keyword_file_fails_its_checksum(tmp_path):
    make_build(tmp_path)
    data = json.loads((tmp_path / KEYWORDS_FILE).read_text(encoding="utf-8"))
    data["idf"][0] += 1.0
    (tmp_path / KEYWORDS_FILE).write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ArtifactError, match="checksum"):
        read_build_files(tmp_path)


def test_missing_manifest_is_reported(tmp_path):
    with pytest.raises(ArtifactError, match="manifest"):
        read_build_files(tmp_path)


def test_other_model_or_revision_is_refused(tmp_path):
    manifest, _, _ = make_build(tmp_path)
    check_model(manifest, MODEL)

    with pytest.raises(ArtifactError, match="was built with"):
        check_model(manifest, EmbeddingModel(MODEL.key, MODEL.hf_id, "b" * 40))
    with pytest.raises(ArtifactError, match="was built with"):
        check_model(manifest, EmbeddingModel("bge-m3", "BAAI/bge-m3", "a" * 40))
