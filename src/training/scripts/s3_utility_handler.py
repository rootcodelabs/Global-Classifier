import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime

from scripts.s3_ferry_service import S3Ferry

from loguru import logger
from scripts.constants import (
    LOG_DIRECTORY,
    LOG_FORMAT,
    LOG_FILE_NAME,
    ROTATION_SIZE,
    RETENTION_PERIOD,
    LOG_FILE_HANDLER_FORMAT,
    DATASETS_ARTIFACTS_DIR,
    MODELS_DIR,
    TRAINING_DATASET_FOLDER_NAME,
    PROCESSED_DATASET_FOLDER_NAME,
)

os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Remove default handler and add custom ones
logger.remove()

# Add console handler for immediate feedback
logger.add(
    sys.stderr,
    level="DEBUG",
    format=LOG_FORMAT,
    colorize=True,
)

# Add file handler
logger.add(
    sink=os.path.join(LOG_DIRECTORY, LOG_FILE_NAME),
    level="DEBUG",
    rotation=ROTATION_SIZE,
    retention=RETENTION_PERIOD,
    backtrace=True,
    diagnose=True,
    format=LOG_FILE_HANDLER_FORMAT,
)


class S3DatasetService:
    """Service for downloading datasets from S3 and uploading trained models."""

    def __init__(self):
        self.s3_ferry = S3Ferry()
        self.dataset_artifacts_dir = DATASETS_ARTIFACTS_DIR
        self.models_dir = MODELS_DIR

        # Create required directories
        os.makedirs(
            os.path.join(self.dataset_artifacts_dir, TRAINING_DATASET_FOLDER_NAME),
            exist_ok=True,
        )
        os.makedirs(
            os.path.join(self.dataset_artifacts_dir, PROCESSED_DATASET_FOLDER_NAME),
            exist_ok=True,
        )
        os.makedirs(self.models_dir, exist_ok=True)

    def download_aggregated_dataset(self, dataset_id: str) -> str:
        """
        Download aggregated dataset from S3.

        Args:
            dataset_id: Dataset ID (e.g., "3")

        Returns:
            Path to downloaded dataset file
        """
        try:
            logger.info(f"Downloading aggregated dataset for dataset ID: {dataset_id}")

            # Define paths
            s3_source_path = f"{dataset_id}/aggregated_dataset.json"
            local_dest_path = (
                f"src/training/dataset_artifacts/training_datasets/{dataset_id}.json"
            )

            logger.info(f"S3 source: {s3_source_path}")
            logger.info(f"Local destination: {local_dest_path}")

            # Download from S3 using S3Ferry
            response = self.s3_ferry.transfer_file(
                destination_file_path=local_dest_path,
                destination_storage_type="FS",
                source_file_path=s3_source_path,
                source_storage_type="S3",
            )

            logger.info(f"S3Ferry response status: {response.status_code}")

            if response.status_code in [200, 201]:
                full_local_path = f"/app/{local_dest_path}"

                if os.path.exists(full_local_path):
                    logger.info(
                        f"Successfully downloaded dataset to: {full_local_path}"
                    )
                    return full_local_path
                else:
                    raise FileNotFoundError(
                        f"Downloaded file not found at: {full_local_path}"
                    )
            else:
                raise RuntimeError(
                    f"S3 download failed: HTTP {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Error downloading dataset {dataset_id}: {str(e)}")
            raise

    def upload_trained_model(
        self, model_dir: str, model_id: int, model_type: str
    ) -> str:
        """
        Zip and upload trained model to S3.

        Args:
            model_dir: Path to the trained model directory
            dataset_id: Dataset ID
            model_type: Model type (e.g., "bert", "roberta")

        Returns:
            S3 path of uploaded model
        """
        try:
            logger.info(f"Preparing to upload model from: {model_dir}")

            # Create zip file name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_id = str(model_id)
            zip_filename = f"{model_type}_dataset_{model_id}_model_{timestamp}.zip"
            zip_path = os.path.join(self.models_dir, zip_filename)

            # Zip the model directory
            self._zip_directory(model_dir, zip_path)

            # Upload to S3
            s3_dest_path = f"trained_models/{model_id}/{zip_filename}"

            logger.info(f"Uploading zipped model to S3: {s3_dest_path}")

            response = self.s3_ferry.transfer_file(
                destination_file_path=s3_dest_path,
                destination_storage_type="S3",
                source_file_path=zip_path.replace("/app/", ""),
                source_storage_type="FS",
            )

            if response.status_code in [200, 201]:
                logger.info(f"Successfully uploaded model to S3: {s3_dest_path}")

                # Clean up local zip file
                os.remove(zip_path)
                logger.info(f"Cleaned up local zip file: {zip_path}")

                return s3_dest_path
            else:
                raise RuntimeError(
                    f"S3 upload failed: HTTP {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Error uploading model: {str(e)}")
            raise

    def _zip_directory(self, source_dir: str, zip_path: str):
        """Zip a directory and all its contents."""
        logger.info(f"Zipping directory {source_dir} to {zip_path}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            source_path = Path(source_dir)

            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    # Create relative path for zip
                    relative_path = file_path.relative_to(source_path)
                    zipf.write(file_path, relative_path)
                    logger.debug(f"Added to zip: {relative_path}")

        logger.info(f"Successfully created zip file: {zip_path}")

        # Log zip file size
        zip_size = os.path.getsize(zip_path)
        logger.info(f"Zip file size: {zip_size / (1024 * 1024):.2f} MB")
