"""
Switch a model group back to an earlier version: the given data model takes
the place of the one serving now (in production or testing), which becomes
undeployed. If retention has already deleted the earlier version's collection,
it is restored from the build's snapshot. Rows, version numbers, results and
latest stay as they are; only which version serves changes, with the same
switch the automatic refresh makes.

    python -m builder.rollback --model-id 2 --replacing 3

It also switches to a version the refresh built but couldn't switch to.
"""

import argparse
import logging
import shutil
import sys
import time

from builder import refresh
from builder.platform import SHARED_DIR, Platform
from builder.publishing import current_prefix, fetch
from builder.refresh import ENVIRONMENTS, api_key, reload_model, store_url, unload_model
from builder.snapshots import restore_snapshot
from embedding_classifier.artifact import SNAPSHOT
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-rollback")


def rollback(platform: Platform, store, model_id: int, replacing: int) -> None:
    target, current = platform.model_row(model_id), platform.model_row(replacing)
    if not target or not current:
        raise RuntimeError(
            f"Data model {model_id if not target else replacing} not found"
        )
    if target.get("modelGroupKey") != current.get("modelGroupKey"):
        raise RuntimeError(
            f"Models {model_id} and {replacing} are versions of different models"
        )
    environment = current.get("deploymentEnv")
    if environment not in ENVIRONMENTS:
        raise RuntimeError(f"Model {replacing} is {environment}, not serving")

    folder = SHARED_DIR / "indexes" / f"{model_id}-rollback"
    shutil.rmtree(folder, ignore_errors=True)
    try:
        manifest = fetch(platform, current_prefix(model_id), folder)
        if manifest is None:
            raise RuntimeError(f"Model {model_id} has no embedding classifier build")
        collection = manifest["vector_store"]["collection"]
        if not store.collection_exists(collection):
            if not (folder / SNAPSHOT).exists():
                raise RuntimeError(
                    f"{collection} is gone and the build has no snapshot"
                )
            logger.info(f"Restoring {collection} from its snapshot")
            restore_snapshot(store_url(), api_key(), collection, folder / SNAPSHOT)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    reload_model(platform, model_id, environment)
    if not platform.switch_models(model_id, replacing, environment, make_latest=False):
        unload_model(platform, model_id, environment)
        raise RuntimeError(
            f"Model {replacing} left {environment} meanwhile; nothing switched"
        )
    logger.info(
        f"Model {model_id} serves {environment} again, in place of model {replacing}"
    )
    time.sleep(refresh.UNLOAD_DELAY_SECONDS)
    unload_model(platform, replacing, environment)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--model-id", required=True, type=int, help="The version to serve"
    )
    parser.add_argument(
        "--replacing", required=True, type=int, help="The version serving now"
    )
    args = parser.parse_args(argv)
    store = QdrantIndexStore.connect(store_url(), api_key(), timeout=60)
    try:
        rollback(Platform(), store, args.model_id, args.replacing)
    except Exception:
        logger.exception(f"Switching to model {args.model_id} failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
