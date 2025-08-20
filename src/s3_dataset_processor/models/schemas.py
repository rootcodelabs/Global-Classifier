"""Pydantic models for API requests and responses."""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class DownloadRequest(BaseModel):
    """Request model for downloading files from signed URLs."""

    encoded_data: str
    extract_files: Optional[bool] = True


class DownloadedFile(BaseModel):
    """Model for downloaded file information."""

    agency_id: str
    agency_name: str
    original_filename: str
    local_path: str
    file_size: int
    extracted_path: Optional[str] = None
    extraction_success: bool = False


class DownloadResponse(BaseModel):
    """Response model for download operation."""

    success: bool
    message: str
    total_downloads: int
    successful_downloads: int
    failed_downloads: int
    downloaded_files: List[DownloadedFile]
    extracted_folders: List[Dict[str, str]]
    total_extracted_folders: int


class ChunkDownloadRequest(BaseModel):
    """Request model for downloading a single chunk."""

    dataset_id: str
    page_num: int


class MultiChunkDownloadRequest(BaseModel):
    """Request model for downloading multiple chunks."""

    dataset_id: str
    chunk_ids: List[int]


class ChunkDownloadResponse(BaseModel):
    """Response model for single chunk download."""

    success: bool
    dataset_id: str
    page_num: Optional[int] = None
    chunk_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: str


class MultiChunkDownloadResponse(BaseModel):
    """Response model for multi-chunk download and aggregation."""

    success: bool
    dataset_id: str
    chunk_info: Optional[Dict[str, Any]] = None
    aggregated_data: List[Dict[str, Any]]
    download_summary: Dict[str, Any]
    download_details: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    message: str
