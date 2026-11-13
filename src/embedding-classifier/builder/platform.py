"""
The rest of the system as the builder sees it: service URLs from
constants.ini, Ruuter calls as the trainer makes them, Resql queries, and file
transfers through S3 Ferry.
"""

import configparser
import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CONSTANTS_FILE = os.environ.get("CONSTANTS_FILE", "/app/constants.ini")
# Both cron-manager and S3 Ferry mount the shared volume here; S3 Ferry's
# file paths are relative to its /app
SHARED_DIR = Path(os.environ.get("SHARED_DIR", "/app/shared"))
FERRY_ROOT = Path(os.environ.get("FERRY_ROOT", "/app"))

# Progress statuses and messages exactly as the trainer sends them; the
# database casts them to its enum
INITIATING = ("Initiating Training", "Download and preparing dataset")
IN_PROGRESS = (
    "Training In-Progress",
    "The dataset is being trained on all selected models",
)
DEPLOYING = (
    "Deploying Model",
    "Model training complete. The trained model is now being deployed",
)
DEPLOYED = (
    "Model Trained And Deployed",
    "The model was trained and deployed successfully to the environment",
)
FAILED = ("Training Failed", "Model training has failed")


def load_constants(path: str = CONSTANTS_FILE) -> dict[str, str]:
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    if not config.read(path):
        raise RuntimeError(f"Constants file not found: {path}")
    return dict(config["DSL"])


class Platform:
    def __init__(
        self, constants: Optional[dict[str, str]] = None, timeout: float = 300
    ):
        self.constants = constants or load_constants()
        self.ruuter = self.constants["GLOBAL_CLASSIFIER_RUUTER_PUBLIC"]
        self.resql_url = self.constants["GLOBAL_CLASSIFIER_RESQL"]
        self.ferry = f"{self.constants['GLOBAL_CLASSIFIER_S3_FERRY']}/v1/files/copy"
        self.timeout = timeout

    def model_server(self, environment: str) -> str:
        key = {
            "production": "GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER",
            "testing": "GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER",
        }[environment]
        return self.constants[key]

    def _post(self, url: str, body: dict) -> requests.Response:
        response = requests.post(
            url,
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        logger.info(f"POST {url} -> {response.status_code}")
        response.raise_for_status()
        return response

    def progress(
        self, session_id, status: tuple[str, str], percentage: int, complete: bool
    ) -> None:
        """Update the GUI's progress session; a failure here is fatal, as in the trainer."""
        self._post(
            f"{self.ruuter}/datamodels/progress/update",
            {
                "sessionId": int(session_id),
                "trainingStatus": status[0],
                "trainingMessage": status[1],
                "progressPercentage": percentage,
                "processComplete": complete,
            },
        )

    def report_training(
        self, model_id, training_results: list, s3_location: str
    ) -> None:
        self._post(
            f"{self.ruuter}/datamodels/training/status/update",
            {
                "modelId": int(model_id),
                "trainingResults": training_results,
                "modelS3Location": s3_location,
            },
        )

    def resql(self, query: str, body: Optional[dict] = None):
        return self._post(f"{self.resql_url}/{query}", body or {}).json()

    def create_progress_session(
        self, model_id, model_name, major, minor, latest
    ) -> int:
        """A GUI progress session, as train_script_starter.sh creates one."""
        body = self._post(
            f"{self.ruuter}/datamodels/progress/create",
            {
                "modelId": int(model_id),
                "modelName": model_name,
                "majorVersion": major,
                "minorVersion": minor,
                "latest": latest,
            },
        ).json()
        return int(_find(body, "sessionId"))

    def model_row(self, model_id) -> Optional[dict]:
        rows = self.resql("get-data-model-by-id", {"model_id": int(model_id)})
        return rows[0] if rows else None

    def create_model_version(self, source_model_id, major: int, dataset: dict) -> int:
        """
        A new version of a data model on a dataset version, as the GUI's major
        update creates one, but undeployed and not yet the latest; returns its id.
        """
        rows = self.resql(
            "create-refresh-data-model-version",
            {
                "sourceModelId": int(source_model_id),
                "major": int(major),
                "connectedDsId": int(dataset["id"]),
                "connectedDsMajorVersion": int(dataset["major"]),
                "connectedDsMinorVersion": int(dataset["minor"]),
            },
        )
        if not rows:
            raise RuntimeError(f"Data model {source_model_id} not found")
        return int(rows[0]["modelId"])

    def delete_model(self, model_id) -> None:
        self.resql("delete-data-model-by-id", {"model_id": int(model_id)})

    def start_training_job(
        self, model_id, model_name: str, major: int, environment: str
    ) -> Optional[int]:
        """
        A training job already in progress, so the GUI's trainings wait for it;
        its id, or None if another job is in progress.
        """
        rows = self.resql(
            "insert-refresh-training-job",
            {
                "modelId": int(model_id),
                "modelName": model_name,
                "majorVersion": int(major),
                "deploymentEnvironment": environment,
            },
        )
        return int(rows[0]["jobId"]) if rows else None

    def finish_training_job(self, job_id, status: str) -> None:
        """status: trained or training-failed, as train_script_starter.sh sets them."""
        self.resql(
            "update-training-job-status", {"jobId": int(job_id), "jobStatus": status}
        )

    def report_failed_training(
        self, model_id, training_results: list, s3_location: str
    ) -> None:
        """Mark a data model's training failed, with the results of the build that failed."""
        self.resql(
            "update-datamodels-training-status",
            {
                "modelId": int(model_id),
                "trainingStatus": "training_failed",
                "trainingResults": json.dumps(training_results),
                "modelS3Location": s3_location,
            },
        )

    def mark_training_failed(self, model_id) -> None:
        self.resql("update-training_status-failed", {"model_id": int(model_id)})

    def switch_models(
        self, new_model_id, old_model_id, environment: str, make_latest: bool
    ) -> bool:
        """
        In one statement, put a data model in the environment another one
        serves and that one to undeployed (and with make_latest, make the new
        one the latest of its group). False, with nothing changed, if the other
        one is no longer in that environment.
        """
        rows = self.resql(
            "switch-data-model",
            {
                "newModelId": int(new_model_id),
                "oldModelId": int(old_model_id),
                "deploymentEnv": environment,
                "makeLatest": bool(make_latest),
            },
        )
        return bool(rows)

    def set_environment(self, model_id, environment: str) -> None:
        self.resql(
            "update-data-model-environment",
            {"modelId": int(model_id), "deploymentEnv": environment},
        )

    def production_model_id(self) -> Optional[int]:
        """The data model the chatbot classifies with (classify.yml's query)."""
        rows = self.resql("get-production-model-id")
        return int(rows[0]["modelId"]) if rows else None

    def group_models_on_dataset(self, group_key: str, dataset_id) -> list[dict]:
        """The versions of a model group built on a dataset version, whatever their status."""
        return (
            self.resql(
                "get-group-models-on-dataset",
                {"modelGroupKey": group_key, "datasetId": int(dataset_id)},
            )
            or []
        )

    def connect_model_to_dataset(self, model_id, dataset_id) -> None:
        """List a data model among a dataset version's connected models, as the GUI's create flow does."""
        self.resql(
            "update-datasets-connected-models",
            {"modelId": int(model_id), "datasetId": int(dataset_id)},
        )

    def training_in_progress(self) -> bool:
        rows = self.resql("get-training-job-status-in-progress")
        return bool(rows and rows[0].get("hasTrainingInProgress"))

    def copy(
        self, source: str, source_type: str, destination: str, destination_type: str
    ) -> None:
        """
        Copy a file through S3 Ferry. S3 paths are relative to the bucket's
        prefix (e.g. "models/indexes/42/manifest.json"); file-system paths are
        absolute in cron-manager and must be under the shared volume.
        """
        self._post(
            self.ferry,
            {
                "sourceFilePath": self._ferry_path(source, source_type),
                "sourceStorageType": source_type,
                "destinationFilePath": self._ferry_path(destination, destination_type),
                "destinationStorageType": destination_type,
            },
        )

    def download(self, s3_path: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        self.copy(s3_path, "S3", str(local), "FS")
        if not local.exists():
            raise FileNotFoundError(f"S3 Ferry reported success but {local} is missing")

    def try_download(self, s3_path: str, local: Path) -> bool:
        """Download if the file exists; False if it doesn't."""
        try:
            self.download(s3_path, local)
            return True
        except (requests.HTTPError, FileNotFoundError):
            return False

    def upload(self, local: Path, s3_path: str) -> None:
        self.copy(str(local), "FS", s3_path, "S3")

    def _ferry_path(self, path: str, storage_type: str) -> str:
        if storage_type == "S3":
            return path.lstrip("/")
        return "/" + str(Path(path).relative_to(FERRY_ROOT)).replace("\\", "/")


def dataset_row(platform: Platform, dataset_id) -> Optional[dict]:
    """The dataset version (major, minor, generationStatus), from the GUI's dataset list query."""
    rows = platform.resql(
        "get-datasets",
        {
            "generation_status": "all",
            "dataset_name": "all",
            "sort_by": "created_at",
            "sort_type": "desc",
            "page": 1,
            "page_size": 10000,
        },
    )
    for row in rows or []:
        if str(row.get("id")) == str(dataset_id):
            return row
    return None


def latest_successful_dataset(platform: Platform) -> Optional[dict]:
    """The newest dataset version with status Generation_Success."""
    # The query returns the newest successful version below :datasetId
    rows = platform.resql("get-latest-successful-dataset-version", {"datasetId": 2**62})
    if not rows:
        return None
    return dataset_row(platform, rows[0]["id"])


def next_major_version(platform: Platform, group_key: str) -> int:
    """One above the highest major version in a model group, as the GUI's major update counts."""
    rows = platform.resql("get-highest-major-version", {"modelGroupKey": group_key})
    return int(rows[0]["major"]) + 1 if rows else 1


def _find(body, key):
    """A key anywhere in a Ruuter response body (it wraps results differently per flow)."""
    if isinstance(body, dict):
        if key in body:
            return body[key]
        for value in body.values():
            found = _find(value, key)
            if found is not None:
                return found
    elif isinstance(body, list):
        for value in body:
            found = _find(value, key)
            if found is not None:
                return found
    return None
