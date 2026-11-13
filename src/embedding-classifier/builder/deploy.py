"""
Deploy script for embedding classifier builds. deployment_script_starter.sh
runs it instead of deployment_orchestrator.py when the model has build files.

    python -m builder.deploy --model-id 42 --has-build-files    # exit 0 if they exist
    python -m builder.deploy --model-id 42 --current-env undeployed --target-env testing --first-deployment true

It loads {id}-classifier-ensemble on the classifier for the target environment
and runs a smoke test with the classify.yml body. Unlike the orchestrator on
Triton, it leaves other loaded models alone. Progress updates stay with the
builder, as they stay with the trainer today.
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time

import requests

from builder.platform import SHARED_DIR, Platform
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-deploy")

SMOKE_TEXT = "This is a test message for classification."
SMOKE_ATTEMPTS = 10
SMOKE_WAIT_SECONDS = 5


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy an embedding classifier build")
    parser.add_argument("--model-id", required=True, type=int)
    parser.add_argument("--has-build-files", action="store_true")
    parser.add_argument(
        "--current-env", choices=["undeployed", "testing", "production"]
    )
    parser.add_argument("--target-env", choices=["undeployed", "testing", "production"])
    parser.add_argument("--first-deployment", choices=["true", "false"])
    return parser.parse_args(argv)


def fetch_manifest(platform: Platform, model_id: int):
    """The build's manifest from S3, or None if it has none."""
    folder = SHARED_DIR / "indexes" / f"{model_id}-deploy"
    try:
        platform.download(
            f"models/indexes/{model_id}/manifest.json", folder / "manifest.json"
        )
        return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (requests.RequestException, FileNotFoundError):
        return None
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def deploy(platform: Platform, store, model_id: int, target_env: str) -> None:
    manifest = fetch_manifest(platform, model_id)
    if manifest is None:
        raise RuntimeError(f"No build files at models/indexes/{model_id}/")
    collection = manifest["vector_store"]["collection"]
    if not store.collection_exists(collection):
        raise RuntimeError(
            f"Collection {collection} is missing; run python -m builder.restore --model-id {model_id}"
        )
    if target_env == "undeployed":
        logger.info(f"Model {model_id}: target is undeployed, nothing to load")
        return

    server = platform.model_server(target_env)
    name = f"{model_id}-classifier-ensemble"
    response = requests.post(
        f"{server}/v2/repository/models/{name}/load", json={}, timeout=600
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Loading {name} on {server} failed: {response.status_code} {response.text}"
        )
    logger.info(f"Loaded {name} on {server}")
    smoke_test(server, name)


def smoke_test(server: str, name: str) -> None:
    body = {
        "inputs": [
            {"name": "TEXT", "datatype": "BYTES", "shape": [1, 1], "data": [SMOKE_TEXT]}
        ]
    }
    for attempt in range(1, SMOKE_ATTEMPTS + 1):
        try:
            response = requests.post(
                f"{server}/v2/models/{name}/infer", json=body, timeout=30
            )
            if response.status_code == 200:
                predictions = json.loads(response.json()["outputs"][0]["data"][0])
                if isinstance(predictions, list) and predictions and predictions[0]:
                    logger.info(f"Smoke test of {name} passed")
                    return
            logger.warning(
                f"Smoke test attempt {attempt}: {response.status_code} {response.text[:200]}"
            )
        except (requests.RequestException, KeyError, ValueError) as error:
            logger.warning(f"Smoke test attempt {attempt}: {error}")
        time.sleep(SMOKE_WAIT_SECONDS)
    raise RuntimeError(f"Smoke test of {name} on {server} failed")


def main(argv=None) -> None:
    args = parse_args(argv)
    platform = Platform()
    if args.has_build_files:
        sys.exit(0 if fetch_manifest(platform, args.model_id) is not None else 1)
    if not args.target_env:
        sys.exit("--target-env is required")
    store = QdrantIndexStore.connect(
        os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        os.environ.get("QDRANT_API_KEY") or None,
        timeout=30,
    )
    try:
        deploy(platform, store, args.model_id, args.target_env)
    except Exception:
        logger.exception(f"Deployment of model {args.model_id} failed")
        sys.exit(1)
    logger.info(
        f"Model {args.model_id} deployed from {args.current_env} to {args.target_env}"
    )


if __name__ == "__main__":
    main()
