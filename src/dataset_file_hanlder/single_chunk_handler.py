"""Service for handling single chunk downloads from S3."""

import json
import os
import tempfile
import traceback
from typing import Dict, Any
from loguru import logger

from services.s3_ferry_service import S3Ferry


class ChunkService:
    """Service class for handling single chunk operations."""
    
    def __init__(self):
        """Initialize the chunk service."""
        self.s3_ferry_service = S3Ferry()
        logger.info("ChunkService initialized")
    
    def download_chunk_from_s3(self, dataset_id: str, page_num: int) -> Dict[str, Any]:
        """
        Download a specific chunk from S3 bucket.
        
        Args:
            dataset_id: Dataset ID
            page_num: Page number (chunk number)
        
        Returns:
            Dictionary containing chunk data or error information
        """
        try:
            logger.info(f"Starting chunk download - Dataset ID: {dataset_id}, Page: {page_num}")
            
            # Create temporary directory for download
            temp_dir = tempfile.mkdtemp(prefix="chunk_download_")
            logger.info(f"Created temporary directory: {temp_dir}")
            
            # Define S3 source path and local destination
            chunk_filename = f"{page_num}.json"
            s3_source_path = f"{dataset_id}/{chunk_filename}"
            local_dest_path = f"temp_chunks/{chunk_filename}"

            # Create the temp_chunks directory if it doesn't exist
            temp_chunks_dir = "temp_chunks"
            os.makedirs(temp_chunks_dir, exist_ok=True)
            logger.info(f"Created/verified temp directory: {temp_chunks_dir}")
            
            logger.info(f"S3 source path: {s3_source_path}")
            logger.info(f"Local destination: {local_dest_path}")
            
            # Download chunk from S3 using S3Ferry service
            response = self.s3_ferry_service.transfer_file(
                destination_file_path=local_dest_path,
                destination_storage_type="FS",
                source_file_path=s3_source_path,
                source_storage_type="S3"
            )
            
            logger.info(f"S3Ferry response status: {response.status_code}")
            logger.info(f"S3Ferry response body: {response.text}")
            
            if response.status_code in [200, 201]:
                # Read the downloaded chunk file
                local_file_path = f"/app/{local_dest_path}"
                
                if os.path.exists(local_file_path):
                    logger.info(f"Successfully downloaded chunk to: {local_file_path}")
                    
                    # Read and parse the chunk data
                    with open(local_file_path, 'r', encoding='utf-8') as f:
                        chunk_data = json.load(f)
                    
                    # Clean up the downloaded file
                    os.remove(local_file_path)
                    logger.info(f"Cleaned up downloaded file: {local_file_path}")
                    
                    # Remove empty directory if it exists
                    try:
                        os.rmdir(os.path.dirname(local_file_path))
                    except OSError:
                        pass  # Directory not empty or doesn't exist
                    
                    return {
                        "success": True,
                        "dataset_id": dataset_id,
                        "page_num": page_num,
                        "chunk_data": chunk_data,
                        "message": f"Successfully downloaded chunk {page_num} for dataset {dataset_id}"
                    }
                else:
                    return {
                        "success": False,
                        "dataset_id": dataset_id,
                        "page_num": page_num,
                        "error": f"Downloaded file not found at: {local_file_path}",
                        "message": "File download completed but file not accessible"
                    }
            else:
                return {
                    "success": False,
                    "dataset_id": dataset_id,
                    "page_num": page_num,
                    "error": f"S3 download failed: HTTP {response.status_code}",
                    "response_body": response.text,
                    "message": f"Failed to download chunk {page_num} from S3"
                }
                
        except Exception as e:
            logger.error(f"Error during chunk download: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "dataset_id": dataset_id,
                "page_num": page_num,
                "error": str(e),
                "message": "Internal error during chunk download"
            }