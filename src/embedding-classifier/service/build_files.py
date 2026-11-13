"""
Where the service reads build files and keeps its loaded-set file: S3 (the
models/ prefix the rest of the system uses) or, for development, a local folder
with the same layout.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from service.settings import Settings


def index_key(model_id, name: str) -> str:
    return f"indexes/{model_id}/{name}"


def loaded_set_key(index_env: str) -> str:
    return f"{index_env}/_loaded.json"


class BuildFiles(ABC):
    """Files under models/, by key relative to it."""

    @abstractmethod
    def download(self, key: str, destination: Path) -> None:
        """Copy one file; raises FileNotFoundError if it doesn't exist."""

    @abstractmethod
    def read_json(self, key: str) -> Optional[dict]:
        """A JSON file's content, or None if it doesn't exist."""

    @abstractmethod
    def write_json(self, key: str, data: dict) -> None: ...


class LocalBuildFiles(BuildFiles):
    def __init__(self, root: str):
        self.root = Path(root)

    def download(self, key, destination) -> None:
        source = self.root / key
        if not source.is_file():
            raise FileNotFoundError(f"{source} does not exist")
        destination.write_bytes(source.read_bytes())

    def read_json(self, key):
        path = self.root / key
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, key, data) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class S3BuildFiles(BuildFiles):
    def __init__(self, settings: Settings):
        import boto3

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")

    def _key(self, key: str) -> str:
        return f"{self.prefix}/models/{key}" if self.prefix else f"models/{key}"

    def download(self, key, destination) -> None:
        from botocore.exceptions import ClientError

        try:
            self.client.download_file(self.bucket, self._key(key), str(destination))
        except ClientError as error:
            raise FileNotFoundError(
                f"s3://{self.bucket}/{self._key(key)}: {error}"
            ) from error

    def read_json(self, key):
        from botocore.exceptions import ClientError

        try:
            body = self.client.get_object(Bucket=self.bucket, Key=self._key(key))[
                "Body"
            ]
        except ClientError as error:
            # No bucket yet (a fresh stack) means no file yet
            if error.response.get("Error", {}).get("Code") in (
                "NoSuchKey",
                "NoSuchBucket",
                "404",
            ):
                return None
            raise
        return json.loads(body.read())

    def write_json(self, key, data) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=json.dumps(data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )


def from_settings(settings: Settings) -> BuildFiles:
    if settings.local_models_dir:
        return LocalBuildFiles(settings.local_models_dir)
    return S3BuildFiles(settings)
