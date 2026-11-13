"""
Recreate a build's collection from its snapshot in S3, after losing the Qdrant
volume or to bring back an old build. The snapshot's checksum is checked
against the manifest first, and the point count after.

    python -m builder.restore --model-id 42
"""

import argparse
import json
import logging
import os
import shutil
import sys

from builder.platform import SHARED_DIR, Platform
from builder.snapshots import restore_snapshot
from embedding_classifier.artifact import MANIFEST, SNAPSHOT, verify_checksums
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-restore")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model-id", required=True, type=int)
    args = parser.parse_args(argv)

    platform = Platform()
    qdrant_url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    api_key = os.environ.get("QDRANT_API_KEY") or None
    folder = SHARED_DIR / "indexes" / f"{args.model_id}-restore"
    try:
        for name in (MANIFEST, SNAPSHOT):
            platform.download(f"models/indexes/{args.model_id}/{name}", folder / name)
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        verify_checksums(folder, manifest, [SNAPSHOT])
        collection = manifest["vector_store"]["collection"]
        restore_snapshot(qdrant_url, api_key, collection, folder / SNAPSHOT)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    info = QdrantIndexStore.connect(qdrant_url, api_key, timeout=30).describe(
        collection
    )
    if info.points != manifest["vector_store"]["points"]:
        sys.exit(
            f"{collection} has {info.points} points, the manifest says {manifest['vector_store']['points']}"
        )
    logger.info(f"Restored {collection} with {info.points} points")


if __name__ == "__main__":
    main()
