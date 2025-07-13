"""Handler for API response formatting."""

from typing import List, Dict, Any

from models.schemas import DownloadResponse, DownloadedFile


class ResponseHandler:
    """Handler class for formatting API responses."""

    @staticmethod
    def format_download_response(
        decoded_data: List[Dict[str, Any]],
        downloaded_files: List[DownloadedFile],
        successful_downloads: int,
        failed_downloads: int,
        extracted_folders: List[Dict[str, str]],
    ) -> DownloadResponse:
        """
        Format download response.

        Args:
            decoded_data: Original decoded data
            downloaded_files: List of downloaded files
            successful_downloads: Number of successful downloads
            failed_downloads: Number of failed downloads
            extracted_folders: List of extracted folder information

        Returns:
            Formatted download response
        """
        return DownloadResponse(
            success=successful_downloads > 0,
            message=f"Downloaded {successful_downloads} files, {failed_downloads} failed",
            total_downloads=len(decoded_data),
            successful_downloads=successful_downloads,
            failed_downloads=failed_downloads,
            downloaded_files=downloaded_files,
            extracted_folders=extracted_folders,
            total_extracted_folders=len(extracted_folders),
        )
