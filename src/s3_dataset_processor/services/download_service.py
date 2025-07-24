"""Service for file download operations."""

import os
import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
from config.settings import settings
from models.schemas import DownloadedFile
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class DownloadService:
    """Service class for handling file download operations."""

    def __init__(self):
        """Initialize the download service."""
        self.data_dir = settings.DATA_DIR
        self.timeout = settings.DOWNLOAD_TIMEOUT
        self.chunk_size = settings.CHUNK_SIZE

    def download_file(self, url: str, local_path: str) -> bool:
        """
        Download a file from URL to local path.

        Args:
            url: The presigned URL to download from
            local_path: Local file path to save the file

        Returns:
            True if download successful, False otherwise
        """
        try:
            logger.info(1)
            response = requests.get(url, stream=True, timeout=self.timeout)
            logger.info(2)
            response.raise_for_status()
            logger.info(3)
            logger.info(f"resonse_payload:{response}")

            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(4)

            with open(local_path, "wb") as f:
                logger.info(5)
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    logger.info(6)
                    if chunk:
                        logger.info(7)
                        f.write(chunk)
            logger.info(8)

            return True
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return False

    def process_downloads(self, decoded_data: List[Dict[str, Any]]) -> tuple:
        """
        Process multiple downloads from decoded data.

        Args:
            decoded_data: List of decoded URL data

        Returns:
            Tuple of (downloaded_files, successful_downloads, failed_downloads)
        """
        downloaded_files = []
        successful_downloads = 0
        failed_downloads = 0
        try:
            for entry in decoded_data:
                agency_id = entry.get("agencyId", "unknown")
                agency_name = entry.get("agencyName", "Unknown Agency")
                signed_url = entry.get("dataUrl", "")

                if not signed_url:
                    failed_downloads += 1
                    continue

                # Parse URL to get filename
                parsed_url = urlparse(signed_url)
                original_filename = (
                    parsed_url.path.split("/")[-1]
                    if parsed_url.path
                    else f"{agency_id}.zip"
                )

                # Download file to data directory
                local_file_path = os.path.join(self.data_dir, original_filename)
                logger.info(
                    f"Downloading {original_filename} for agency {agency_id} with name {agency_name}"
                )

                if self.download_file(signed_url, local_file_path):
                    file_size = os.path.getsize(local_file_path)

                    downloaded_file = DownloadedFile(
                        agency_id=agency_id,
                        agency_name=agency_name,
                        original_filename=original_filename,
                        local_path=local_file_path,
                        file_size=file_size,
                    )

                    downloaded_files.append(downloaded_file)
                    successful_downloads += 1
                    logger.info(f"Successfully downloaded {original_filename}")

                else:
                    failed_downloads += 1
                    logger.error(f"Failed to download {original_filename}")
        except Exception as e:
            logger.error(f"Error processing downloads: {e}")
            return downloaded_files, successful_downloads, failed_downloads
        return downloaded_files, successful_downloads, failed_downloads
