"""Service for file extraction operations."""

import os
import zipfile
import shutil
from typing import List, Dict

from config.settings import settings
from models.schemas import DownloadedFile
import sys
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class ExtractionService:
    """Service class for handling file extraction operations."""

    def __init__(self):
        """Initialize the extraction service."""
        self.data_dir = settings.DATA_DIR

    def extract_zip_file(self, zip_path: str, extract_to: str) -> bool:
        """
        Extract a ZIP file to the specified directory.

        Args:
            zip_path: Path to the ZIP file
            extract_to: Directory to extract files to

        Returns:
            True if extraction successful, False otherwise
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        except Exception as e:
            print(f"Failed to extract {zip_path}: {e}")
            return False

    def process_extractions(
        self, downloaded_files: List[DownloadedFile], extract_files: bool = True
    ) -> List[Dict[str, str]]:
        """
        Process extractions for downloaded files.

        Args:
            downloaded_files: List of downloaded files to extract
            extract_files: Whether to extract files

        Returns:
            List of extracted folder information
        """
        extracted_folders = []

        if not extract_files:
            return extracted_folders

        for downloaded_file in downloaded_files:
            if not downloaded_file.original_filename.lower().endswith(".zip"):
                continue

            # Extract agency name from filename
            # agency_name = downloaded_file.original_filename.replace(".zip", "")
            agency_name = downloaded_file.agency_name
            agency_dir = os.path.join(self.data_dir, agency_name)
            os.makedirs(agency_dir, exist_ok=True)

            # Extract to temporary directory first
            temp_extract_dir = os.path.join(self.data_dir, f"temp_{agency_name}")
            logger.info(
                f"Extracting {downloaded_file.original_filename} to temporary directory: {temp_extract_dir}"
            )

            if self.extract_zip_file(downloaded_file.local_path, temp_extract_dir):
                self._move_extracted_contents(temp_extract_dir, agency_dir)

                # Update downloaded file info
                downloaded_file.extracted_path = agency_dir
                downloaded_file.extraction_success = True
                logger.info(
                    f"Successfully extracted {downloaded_file.original_filename}"
                )

                # Add to extracted folders list
                extracted_folders.append(
                    {"agency_id": downloaded_file.agency_id, "agency_name": downloaded_file.agency_name, "folder_path": agency_dir}
                )

                # Remove the ZIP file after successful extraction
                os.remove(downloaded_file.local_path)
                logger.info(f"Removed ZIP file {downloaded_file.local_path}")
            else:
                downloaded_file.extraction_success = False
                logger.error(f"Failed to extract {downloaded_file.original_filename}")

        return extracted_folders

    def _move_extracted_contents(self, temp_extract_dir: str, agency_dir: str) -> None:
        """
        Move extracted contents from temporary directory to agency directory.

        Args:
            temp_extract_dir: Temporary extraction directory
            agency_dir: Target agency directory
        """
        extracted_items = os.listdir(temp_extract_dir)

        if len(extracted_items) == 1 and os.path.isdir(
            os.path.join(temp_extract_dir, extracted_items[0])
        ):
            # Single folder was extracted - move its contents to the agency directory
            nested_folder = os.path.join(temp_extract_dir, extracted_items[0])
            logger.info(
                f"Found nested folder structure, moving contents from {nested_folder} to {agency_dir}"
            )

            for item in os.listdir(nested_folder):
                src = os.path.join(nested_folder, item)
                dst = os.path.join(agency_dir, item)
                shutil.move(src, dst)
        else:
            # Multiple items or files extracted - move everything to agency directory
            logger.info(f"Moving extracted contents directly to {agency_dir}")
            for item in extracted_items:
                src = os.path.join(temp_extract_dir, item)
                dst = os.path.join(agency_dir, item)
                shutil.move(src, dst)

        # Clean up temporary directory
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
