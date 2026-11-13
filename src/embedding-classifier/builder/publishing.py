"""
A model's build files in S3, at models/indexes/{model_id}/, which is what the
classifier loads. GUI builds also keep a copy at
models/indexes/{model_id}/versions/ds{dataset_id}/.
"""

import json
from pathlib import Path
from typing import Optional

from embedding_classifier.artifact import (
    KEYWORDS_FILE,
    MANIFEST,
    QUALITY_REPORT,
    SNAPSHOT,
)
from embedding_classifier.classifier_layer import LAYER_FILE

# The manifest goes last: its presence means the files before it are complete.
# A build without a classifier layer has no layer file.
BUILD_FILES = [KEYWORDS_FILE, LAYER_FILE, QUALITY_REPORT, SNAPSHOT, MANIFEST]


def current_prefix(model_id) -> str:
    return f"models/indexes/{model_id}/"


def version_prefix(model_id, dataset_id) -> str:
    return f"models/indexes/{model_id}/versions/ds{dataset_id}/"


def publish(platform, folder: Path, prefix: str) -> None:
    """Upload a build's files from a local folder, manifest last."""
    for name in BUILD_FILES:
        if (folder / name).exists():
            platform.upload(folder / name, prefix + name)


def exists(platform, prefix: str, folder: Path) -> bool:
    """Whether a complete build is at a prefix (its manifest is there)."""
    return platform.try_download(prefix + MANIFEST, folder / MANIFEST)


def fetch(platform, prefix: str, folder: Path) -> Optional[dict]:
    """Download a build's files into a folder; its manifest, or None if there is none."""
    folder.mkdir(parents=True, exist_ok=True)
    if not platform.try_download(prefix + MANIFEST, folder / MANIFEST):
        return None
    for name in BUILD_FILES[:-1]:
        platform.try_download(prefix + name, folder / name)
    return json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
