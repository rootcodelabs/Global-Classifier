"""
Index build job. train_script_starter.sh runs it instead of model_trainer.py
for embedding-model keys, with the same arguments, in its own virtual
environment (/app/embedding_venv).

    python -m builder.cli --model_types '["multilingual-e5-large-instruct"]' --model_id 42 \\
        --job_id 7 --dataset_id 3 --model_name m --major_version 1 --minor_version 0 \\
        --latest true --deployment_environment testing --session_id 12

The GUI saves an e5 data model undeployed and leaves the model serving its
environment alone; the job puts the new one there only after it passes the
quality gate and loads. A build that fails the gate is marked failed, with its
results, and leaves no collection.

Environment: QDRANT_URL, QDRANT_API_KEY, EMBEDDING_CACHE_DIR, TORCH_THREADS,
HF_HOME, CONSTANTS_FILE.
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time

from builder.index_build import BuildResult, GateConfig, ScoringConfig, build_index
from builder.platform import (
    DEPLOYED,
    DEPLOYING,
    FAILED,
    IN_PROGRESS,
    SHARED_DIR,
    Platform,
    dataset_row,
)
from builder.publishing import current_prefix, publish, version_prefix
from builder.refresh import UNLOAD_DELAY_SECONDS, reload_model, unload_model
from builder.snapshots import take_snapshot
from builder.training_results import training_results
from embedding_classifier.artifact import QUALITY_REPORT, SNAPSHOT, write_build_files
from embedding_classifier.content import read_aggregated_dataset
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, get_model
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-builder")

UNDEPLOYED = "undeployed"


class GateFailed(Exception):
    """The quality gate failed in enforce mode; the build isn't deployed."""


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an embedding index (replaces model training)"
    )
    parser.add_argument(
        "--model_types",
        required=True,
        help='JSON list of model keys, e.g. ["multilingual-e5-large-instruct"]',
    )
    parser.add_argument("--model_id", required=True, type=int)
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--dataset_id", required=True, type=int)
    parser.add_argument("--model_name", required=True)
    parser.add_argument("--major_version", required=True, type=int)
    parser.add_argument("--minor_version", required=True, type=int)
    parser.add_argument("--latest", required=True)
    parser.add_argument("--deployment_environment", required=True)
    parser.add_argument("--session_id", required=True)
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    platform = Platform()
    try:
        run(args, platform)
    except Exception:
        logger.exception(f"Index build for model {args.model_id} failed")
        try:
            platform.progress(args.session_id, FAILED, 100, False)
        except Exception:
            logger.exception("Could not report the failure to the progress session")
        sys.exit(1)


def run(args: argparse.Namespace, platform: Platform) -> None:
    model_id, dataset_id = args.model_id, args.dataset_id
    platform.progress(args.session_id, IN_PROGRESS, 30, False)
    models = [get_model(key) for key in json.loads(args.model_types)]

    csv_path = SHARED_DIR / "datasets" / f"dataset_{dataset_id}.csv"
    platform.download(f"datasets/{dataset_id}/aggregated_dataset.csv", csv_path)
    questions = read_aggregated_dataset(str(csv_path))
    logger.info(f"Dataset {dataset_id}: {len(questions)} questions")

    warnings = []
    row = dataset_row(platform, dataset_id) or {}
    if row.get("generationStatus") != "Generation_Success":
        warnings.append(
            f"Dataset version {dataset_id} has generation status {row.get('generationStatus')}, "
            "not Generation_Success"
        )
    dataset = {"id": dataset_id, "major": row.get("major"), "minor": row.get("minor")}
    platform.progress(args.session_id, IN_PROGRESS, 40, False)

    qdrant_url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    api_key = os.environ.get("QDRANT_API_KEY") or None
    store = QdrantIndexStore.connect(qdrant_url, api_key, timeout=120)
    cache = EmbeddingCache(
        os.environ.get("EMBEDDING_CACHE_DIR", "/app/embedding_cache")
    )
    threads = (
        int(os.environ["TORCH_THREADS"]) if os.environ.get("TORCH_THREADS") else None
    )
    gate_config = GateConfig.load()
    layer_params = ScoringConfig.load().layer_params()

    def build(model) -> BuildResult:
        return build_index(
            model_id=model_id,
            questions=questions,
            model=model,
            encoder=Encoder(model, threads=threads),
            store=store,
            gate_config=gate_config,
            dataset=dataset,
            cache=cache,
            warnings=warnings,
            builder_commit=os.environ.get("BUILDER_COMMIT", ""),
            layer_params=layer_params,
        )

    results = [(model, build(model)) for model in models]
    best_model, best = max(
        results,
        key=lambda r: (
            r[1].passed,
            r[1].report["metrics"]["routed_at_90_share"],
            r[1].report["metrics"]["top1"],
        ),
    )
    # Every build writes gc_index_{model_id}; the winner's must be the one left
    if len(results) > 1 and best is not results[-1][1] and best.passed:
        best = build(best_model)

    folder = SHARED_DIR / "indexes" / str(model_id)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    s3_folder = f"models/indexes/{model_id}/"
    results_for_gui = training_results(
        [(m.key, m.hf_id, r.report) for m, r in results], s3_folder
    )
    try:
        if not best.passed:
            (folder / QUALITY_REPORT).write_text(
                json.dumps(best.report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            platform.upload(folder / QUALITY_REPORT, s3_folder + QUALITY_REPORT)
            # With the results, so the GUI shows why
            platform.report_failed_training(model_id, results_for_gui, s3_folder)
            raise GateFailed(
                f"Quality gate failed: {[c['check'] for c in best.report['gate']['checks'] if c['status'] == 'failed']}"
            )

        take_snapshot(
            store.client, qdrant_url, api_key, best.collection, folder / SNAPSHOT
        )
        write_build_files(folder, best.manifest, best.keywords, best.report, best.layer)
        # Also kept per dataset version
        publish(platform, folder, version_prefix(model_id, dataset_id))
        publish(platform, folder, current_prefix(model_id))
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    platform.report_training(model_id, results_for_gui, s3_folder)
    platform.progress(args.session_id, DEPLOYING, 100, True)
    if args.deployment_environment == UNDEPLOYED:
        logger.info(f"Model {model_id} targets {UNDEPLOYED}; not deploying")
    else:
        # Loaded and smoke-tested before it takes the environment
        try:
            reload_model(platform, model_id, args.deployment_environment)
        except Exception:
            unload_model(platform, model_id, args.deployment_environment)
            raise
        take_environment(platform, model_id, args.deployment_environment)
    platform.progress(args.session_id, DEPLOYED, 100, True)
    logger.info(f"Index build for model {model_id} finished")


def take_environment(platform: Platform, model_id: int, environment: str) -> None:
    """
    Put a built and loaded model in its environment. In production, the model
    serving there moves to undeployed in the same statement and is unloaded a
    few seconds later.
    """
    serving = platform.production_model_id() if environment == "production" else None
    if serving not in (None, model_id) and platform.switch_models(
        model_id, serving, environment, make_latest=False
    ):
        logger.info(
            f"Model {model_id} now serves {environment} in place of model {serving}"
        )
        time.sleep(UNLOAD_DELAY_SECONDS)
        unload_model(platform, serving, environment)
    else:
        platform.set_environment(model_id, environment)


if __name__ == "__main__":
    main()
