"""
Qdrant snapshots of a build's collection: take one and download it (so it can
go to S3), and restore a collection from one.
"""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def take_snapshot(
    client, qdrant_url: str, api_key, collection: str, destination: Path
) -> None:
    """Snapshot a collection, download it, then delete it from the Qdrant node."""
    snapshot = client.create_snapshot(collection, wait=True)
    try:
        url = f"{qdrant_url.rstrip('/')}/collections/{collection}/snapshots/{snapshot.name}"
        with requests.get(
            url, headers=_headers(api_key), stream=True, timeout=600
        ) as response:
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "wb") as f:
                for block in response.iter_content(1 << 20):
                    f.write(block)
    finally:
        client.delete_snapshot(collection, snapshot.name, wait=True)
    logger.info(
        f"Snapshot of {collection} saved to {destination} ({destination.stat().st_size} bytes)"
    )


def restore_snapshot(qdrant_url: str, api_key, collection: str, snapshot: Path) -> None:
    """Recreate a collection from a snapshot file (replaces it if it exists)."""
    base = f"{qdrant_url.rstrip('/')}/collections/{collection}/snapshots"
    with open(snapshot, "rb") as f:
        response = requests.post(
            f"{base}/upload?priority=snapshot&wait=true",
            headers=_headers(api_key),
            files={"snapshot": (snapshot.name, f, "application/octet-stream")},
            timeout=1800,
        )
    response.raise_for_status()
    # Qdrant keeps the uploaded file on the node; the S3 copy is the one that matters
    requests.delete(
        f"{base}/{snapshot.name}?wait=true", headers=_headers(api_key), timeout=60
    ).raise_for_status()
    logger.info(f"Restored {collection} from {snapshot}")


def _headers(api_key) -> dict:
    return {"api-key": api_key} if api_key else {}
