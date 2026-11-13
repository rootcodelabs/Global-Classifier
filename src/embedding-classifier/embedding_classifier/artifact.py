"""
A build's files, as stored under models/indexes/{model_id}/ in S3: the
manifest (everything needed to serve the build), the keyword vectorizer, the
classifier layer when the build has one, and the quality report, with sha256
checksums. Works on a local folder; moving it to and from S3 is the caller's job.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from embedding_classifier import classifier_layer
from embedding_classifier.classifier_layer import LAYER_FILE, ClassifierLayer
from embedding_classifier.encoder import MAX_SEQ_LENGTH, EmbeddingModel
from embedding_classifier.gate import GateParams
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import METHOD, ScoringParams
from embedding_classifier.store import Agency
from embedding_classifier.vector_store import DENSE, KEYWORDS

FORMAT_VERSION = 1
# A build with a classifier layer; services that predate it refuse the manifest
# instead of serving it without the layer
LAYER_FORMAT_VERSION = 2
FORMAT_VERSIONS = (FORMAT_VERSION, LAYER_FORMAT_VERSION)
MANIFEST = "manifest.json"
KEYWORDS_FILE = "keywords.json"
QUALITY_REPORT = "quality_report.json"
SNAPSHOT = "collection.snapshot"


class ArtifactError(Exception):
    """The build files are missing, corrupted, or don't fit this service."""


def collection_name(model_id) -> str:
    return f"gc_index_{model_id}"


def build_manifest(
    *,
    model_id,
    model: EmbeddingModel,
    dim: int,
    collection: str,
    points: int,
    scoring: ScoringParams,
    gate: GateParams,
    keywords: KeywordVectorizer,
    agencies: list[Agency],
    counts: dict[str, dict[str, int]],
    dataset: dict,
    built_at: str,
    builder_commit: str = "",
    layer: Optional[ClassifierLayer] = None,
) -> dict:
    """
    The manifest of a build (files and their checksums are added by
    write_build_files).

    Args:
        counts: Rows per agency key and kind, see store.count_by_agency
        dataset: {id, major, minor} of the dataset version
        layer: The build's classifier layer, if it has one
    """
    scoring_section = {
        "method": METHOD,
        "knn_k": scoring.knn_k,
        "keyword_weight": scoring.keyword_weight,
        "tfidf": keywords.params,
    }
    if layer is not None:
        scoring_section["method"] = classifier_layer.METHOD
        scoring_section["classifier_layer"] = layer.describe()
    return {
        "format_version": (FORMAT_VERSION if layer is None else LAYER_FORMAT_VERSION),
        "model_id": model_id,
        "embedding_model": model.hf_id,
        "embedding_model_revision": model.revision,
        "dim": dim,
        "prompt": model.prompt,
        "max_seq_length": dict(MAX_SEQ_LENGTH),
        "vector_store": {
            "type": "qdrant",
            "collection": collection,
            "points": points,
            "dense_vector": DENSE,
            "sparse_vector": KEYWORDS,
            "distance": "Cosine",
        },
        "scoring": scoring_section,
        "gate": asdict(gate),
        "agencies": [
            {
                "agency_id": agency.agency_id,
                "agency_name": agency.agency_name,
                "counts": counts.get(agency.key, {}),
            }
            for agency in agencies
        ],
        "dataset": dataset,
        "built_at": built_at,
        "builder_commit": builder_commit,
    }


def write_build_files(
    folder: Path,
    manifest: dict,
    keywords: KeywordVectorizer,
    quality_report: dict,
    layer: Optional[ClassifierLayer] = None,
) -> dict:
    """
    Write keywords.json, classifier_layer.npz (if the build has one) and
    quality_report.json, then manifest.json with the checksums of every
    other file in the folder (such as collection.snapshot).

    Returns:
        The manifest as written
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / KEYWORDS_FILE, keywords.to_json())
    if layer is not None:
        layer.save(folder / LAYER_FILE)
    _write_json(folder / QUALITY_REPORT, quality_report)
    files = {
        path.name: sha256_file(path)
        for path in sorted(folder.iterdir())
        if path.is_file() and path.name != MANIFEST
    }
    manifest = {**manifest, "files": files}
    _write_json(folder / MANIFEST, manifest)
    return manifest


def read_build_files(folder: Path) -> tuple[dict, KeywordVectorizer]:
    """
    Read the manifest and keyword vectorizer, checking the format and the
    keyword file's checksum.
    """
    folder = Path(folder)
    try:
        with open(folder / MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
    except FileNotFoundError as error:
        raise ArtifactError(f"No {MANIFEST} in {folder}") from error
    if manifest.get("format_version") not in FORMAT_VERSIONS:
        raise ArtifactError(
            f"Unsupported manifest format {manifest.get('format_version')}"
        )
    verify_checksums(folder, manifest, [KEYWORDS_FILE])
    with open(folder / KEYWORDS_FILE, encoding="utf-8") as f:
        keywords = KeywordVectorizer.from_json(json.load(f))
    return manifest, keywords


def has_layer(manifest: dict) -> bool:
    return manifest["scoring"]["method"] == classifier_layer.METHOD


def read_layer(folder: Path, manifest: dict) -> Optional[ClassifierLayer]:
    """The build's classifier layer, checksum checked; None if it has none."""
    if not has_layer(manifest):
        return None
    verify_checksums(folder, manifest, [LAYER_FILE])
    try:
        return ClassifierLayer.load(Path(folder) / LAYER_FILE)
    except (KeyError, ValueError) as error:
        raise ArtifactError(f"{LAYER_FILE}: {error}") from error


def verify_checksums(folder: Path, manifest: dict, names: list[str]) -> None:
    """Check that each named file is present and matches the manifest's sha256."""
    for name in names:
        expected = manifest.get("files", {}).get(name)
        if expected is None:
            raise ArtifactError(f"The manifest lists no checksum for {name}")
        path = Path(folder) / name
        if not path.exists():
            raise ArtifactError(f"{name} is missing")
        if sha256_file(path) != expected:
            raise ArtifactError(f"{name} does not match its checksum")


def check_model(manifest: dict, model: EmbeddingModel) -> None:
    """Refuse a build made with another embedding model or revision."""
    built = (manifest["embedding_model"], manifest["embedding_model_revision"])
    if built != (model.hf_id, model.revision):
        raise ArtifactError(
            f"Index was built with {built[0]} at {built[1]}; "
            f"this service has {model.hf_id} at {model.revision}"
        )


def agencies_from_manifest(manifest: dict) -> list[Agency]:
    return [Agency(a["agency_id"], a["agency_name"]) for a in manifest["agencies"]]


def scoring_from_manifest(manifest: dict) -> ScoringParams:
    scoring = manifest["scoring"]
    return ScoringParams(
        knn_k=scoring["knn_k"], keyword_weight=scoring["keyword_weight"]
    )


def gate_from_manifest(manifest: dict) -> GateParams:
    return GateParams(**manifest["gate"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
