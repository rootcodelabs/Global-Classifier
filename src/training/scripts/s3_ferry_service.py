"""Service for S3Ferry file transfer operations."""

import requests
import traceback
from typing import Dict

from loguru import logger
import os
import sys
from scripts.constants import (
    LOG_DIRECTORY,
    LOG_FORMAT,
    LOG_FILE_NAME,
    ROTATION_SIZE,
    RETENTION_PERIOD,
    LOG_FILE_HANDLER_FORMAT,
    S3_FERRY_BASE_URL,
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


class S3Ferry:
    """Service class for handling S3Ferry file transfer operations."""

    def __init__(self, base_url: str = S3_FERRY_BASE_URL):
        """
        Initialize the S3Ferry service.

        Args:
            base_url: Base URL for the S3Ferry service
        """
        self.base_url = base_url
        self.url = f"{base_url}/v1/files/copy"
        logger.info(f"S3Ferry service initialized with URL: {self.url}")

    def transfer_file(
        self,
        destination_file_path: str,
        destination_storage_type: str,
        source_file_path: str,
        source_storage_type: str,
    ) -> requests.Response:
        """
        Transfer a file using S3Ferry service.

        Args:
            destination_file_path: Path where the file should be stored in destination
            destination_storage_type: Type of destination storage (e.g., 's3', 'local')
            source_file_path: Path of the source file
            source_storage_type: Type of source storage (e.g., 'local', 's3')

        Returns:
            Response object from the S3Ferry service
        """
        try:
            payload = self.get_s3_ferry_payload(
                destination_file_path,
                destination_storage_type,
                source_file_path,
                source_storage_type,
            )

            logger.info(
                f"[S3_FERRY] Transferring file: {source_file_path} -> {destination_file_path}"
            )
            logger.debug(f"[S3_FERRY] Payload: {payload}")

            response = requests.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )

            logger.info(f"[S3_FERRY] Transfer response status: {response.status_code}")

            # Accept both 200 (OK) and 201 (Created) as success
            if response.status_code not in [200, 201]:
                logger.error(f"[S3_FERRY] Transfer failed: {response.text}")
            else:
                logger.info(
                    f"[S3_FERRY] ✅ Transfer successful (HTTP {response.status_code})"
                )

            return response

        except Exception as e:
            logger.error(f"[S3_FERRY] Error during file transfer: {str(e)}")
            traceback.print_exc()
            raise

    def get_s3_ferry_payload(
        self,
        destination_file_path: str,
        destination_storage_type: str,
        source_file_path: str,
        source_storage_type: str,
    ) -> Dict[str, str]:
        """
        Generate S3Ferry payload for file transfer.

        Args:
            destination_file_path: Path where the file should be stored in destination
            destination_storage_type: Type of destination storage
            source_file_path: Path of the source file
            source_storage_type: Type of source storage

        Returns:
            Dictionary containing the S3Ferry payload
        """
        payload = {
            "destinationFilePath": destination_file_path,
            "destinationStorageType": destination_storage_type,
            "sourceFilePath": source_file_path,
            "sourceStorageType": source_storage_type,
        }

        return payload

    def upload_to_s3(
        self, local_file_path: str, s3_destination_path: str
    ) -> requests.Response:
        """
        Convenience method to upload a local file to S3.

        Args:
            local_file_path: Path to the local file
            s3_destination_path: S3 destination path (e.g., 'bucket/folder/file.json')

        Returns:
            Response object from the S3Ferry service
        """
        return self.transfer_file(
            destination_file_path=s3_destination_path,
            destination_storage_type="S3",
            source_file_path=local_file_path,
            source_storage_type="FS",
        )

    def download_from_s3(
        self, s3_source_path: str, local_destination_path: str
    ) -> requests.Response:
        """
        Convenience method to download a file from S3 to local storage.

        Args:
            s3_source_path: S3 source path (e.g., 'bucket/folder/file.json')
            local_destination_path: Local destination path

        Returns:
            Response object from the S3Ferry service
        """
        return self.transfer_file(
            destination_file_path=local_destination_path,
            destination_storage_type="local",
            source_file_path=s3_source_path,
            source_storage_type="s3",
        )
