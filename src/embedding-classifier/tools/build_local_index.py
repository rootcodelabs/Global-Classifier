"""
Build an index for development: from a local aggregated_dataset.csv into a
Qdrant collection and a local models folder with the layout the service reads
from S3 (indexes/{model_id}/...). Point the service at it with LOCAL_MODELS_DIR.

Example, from src/embedding-classifier:
    python -m tools.build_local_index --csv aggregated_dataset.csv \\
        --model-id 9001 --models-dir <folder> --snapshot
"""

import argparse
import logging
import os
from dataclasses import replace
from pathlib import Path

from builder.index_build import GateConfig, ScoringConfig, build_index
from builder.snapshots import take_snapshot
from embedding_classifier.artifact import SNAPSHOT, write_build_files
from embedding_classifier.content import read_aggregated_dataset
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, get_model
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--model", default="multilingual-e5-large-instruct")
    parser.add_argument("--model-id", required=True, type=int)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument(
        "--qdrant-url", default=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    )
    parser.add_argument(
        "--cache",
        type=Path,
        help="Embedding cache folder (default: <models-dir>/cache)",
    )
    parser.add_argument("--threads", type=int)
    parser.add_argument(
        "--snapshot", action="store_true", help="Also save collection.snapshot"
    )
    parser.add_argument(
        "--classifier-layer",
        action="store_true",
        help="Add the classifier layer even if builder/scoring.json has it off",
    )
    args = parser.parse_args()
    config = ScoringConfig.load()
    if args.classifier_layer:
        config = replace(config, classifier_layer=True)

    model = get_model(args.model)
    api_key = os.environ.get("QDRANT_API_KEY") or None
    store = QdrantIndexStore.connect(args.qdrant_url, api_key, timeout=120)
    result = build_index(
        model_id=args.model_id,
        questions=read_aggregated_dataset(str(args.csv)),
        model=model,
        encoder=Encoder(model, threads=args.threads),
        store=store,
        gate_config=GateConfig.load(),
        dataset={"id": None, "major": None, "minor": None, "source": args.csv.name},
        cache=EmbeddingCache(args.cache or args.models_dir / "cache"),
        layer_params=config.layer_params(),
    )
    folder = args.models_dir / "indexes" / str(args.model_id)
    folder.mkdir(parents=True, exist_ok=True)
    if args.snapshot:
        take_snapshot(
            store.client, args.qdrant_url, api_key, result.collection, folder / SNAPSHOT
        )
    write_build_files(
        folder, result.manifest, result.keywords, result.report, result.layer
    )
    metrics = result.report["metrics"]
    logger.info(
        f"Built {result.collection} ({result.manifest['scoring']['method']}): "
        f"{result.manifest['vector_store']['points']} points, "
        f"test top-1 {metrics['top1']:.3f}, top-3 {metrics['top3']:.3f}; files in {folder}"
    )


if __name__ == "__main__":
    main()
