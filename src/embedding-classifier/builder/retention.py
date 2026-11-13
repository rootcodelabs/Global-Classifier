"""
Daily retention of build collections. A model's collection is
gc_index_{model_id}; gc_index_{model_id}_ds{dataset_id} ones come from an
earlier form of the automatic refresh, which rebuilt a model in place.

Models: keeps every model in production or testing, the KEEP_RECENT most
recent other models, and anything built in the last KEEP_DAYS days; the rest
are unloaded from both classifier services and their collections deleted.
Versions: of a kept model, keeps the collection it serves now and its newest
keep_versions others (builder/refresh.json).

S3 build files and snapshots stay, so any build can be restored.

    python -m builder.retention [--dry-run]
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from builder.deploy import fetch_manifest
from builder.platform import Platform
from builder.refresh import RefreshConfig
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-retention")

PREFIX = "gc_index_"
COLLECTION = re.compile(r"^gc_index_(\d+)(?:_ds(\d+))?$")


def by_model(names: list[str]) -> dict[str, list[tuple[str, int]]]:
    """Collections per model id, as (name, dataset id); a first build counts as -1."""
    models: dict[str, list[tuple[str, int]]] = {}
    for name in names:
        match = COLLECTION.match(name)
        if match:
            dataset = int(match[2]) if match[2] else -1
            models.setdefault(match[1], []).append((name, dataset))
    return models


def old_versions(
    collections: list[tuple[str, int]], current: Optional[str], keep_versions: int
) -> list[str]:
    """A kept model's collections to delete: all but the current one and the newest keep_versions others."""
    others = sorted(
        (c for c in collections if c[0] != current), key=lambda c: c[1], reverse=True
    )
    return [name for name, _ in others[keep_versions:]]


def data_models(platform: Platform) -> tuple[list[dict], Optional[str]]:
    """Every non-production data model row, and the production model id."""
    rows, page = [], 1
    while True:
        batch = platform.resql(
            "get-data-models",
            {
                "training_status": "all",
                "model_status": "all",
                "deployment_env": "all",
                "sort_by": "createdAt",
                "sort_type": "desc",
                "page": page,
                "page_size": 500,
            },
        )
        rows += batch or []
        if not batch or page >= int(batch[0].get("totalPages") or 1):
            break
        page += 1
    production = platform.resql("get-production-model-id")
    production_id = str(production[0]["modelId"]) if production else None
    return rows, production_id


def to_keep(
    collection_ids: list[str],
    rows: list[dict],
    production_id,
    keep_recent: int,
    keep_days: int,
    now: datetime,
) -> set[str]:
    keep = {production_id} if production_id else set()
    built: dict[str, datetime] = {}
    for row in rows:
        model_id = str(row["modelId"])
        if row.get("deploymentEnv") in ("production", "testing"):
            keep.add(model_id)
        when = parse_time(row.get("lastTrained") or row.get("createdTimestamp"))
        if when:
            built[model_id] = when
    others = sorted(
        (m for m in collection_ids if m not in keep and m in built),
        key=built.get,
        reverse=True,
    )
    keep.update(others[:keep_recent])
    keep.update(
        m
        for m in collection_ids
        if m in built and now - built[m] <= timedelta(days=keep_days)
    )
    return keep


def parse_time(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    keep_recent = int(os.environ.get("KEEP_RECENT", "3"))
    keep_days = int(os.environ.get("KEEP_DAYS", "7"))

    platform = Platform()
    store = QdrantIndexStore.connect(
        os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        os.environ.get("QDRANT_API_KEY") or None,
        timeout=30,
    )
    keep_versions = RefreshConfig.load().keep_versions
    collections = by_model([c.name for c in store.client.get_collections().collections])
    ids = list(collections)
    rows, production_id = data_models(platform)
    keep = to_keep(
        ids, rows, production_id, keep_recent, keep_days, datetime.now(timezone.utc)
    )

    def delete(name: str) -> None:
        logger.info(f"{'Would delete' if args.dry_run else 'Deleting'} {name}")
        if not args.dry_run:
            store.delete_collection(name)

    for model_id in sorted(set(ids) - keep):
        if not args.dry_run:
            unload(platform, model_id)
        for name, _ in collections[model_id]:
            delete(name)
    for model_id in sorted(keep & set(ids)):
        manifest = fetch_manifest(platform, int(model_id))
        current = manifest["vector_store"]["collection"] if manifest else None
        if current is None:
            # Without its manifest the served collection is unknown; delete nothing
            continue
        for name in old_versions(collections[model_id], current, keep_versions):
            delete(name)
    logger.info(f"Kept models {sorted(keep & set(ids))}")


def unload(platform: Platform, model_id: str) -> None:
    name = f"{model_id}-classifier-ensemble"
    for environment in ("production", "testing"):
        try:
            requests.post(
                f"{platform.model_server(environment)}/v2/repository/models/{name}/unload",
                json={},
                timeout=60,
            )
        except requests.RequestException as error:
            logger.warning(f"Could not unload {name} from {environment}: {error}")


if __name__ == "__main__":
    main()
