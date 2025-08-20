"""Service for handling multiple chunk downloads and aggregation from S3."""

import json
import os
import traceback
from typing import List, Dict, Any
from loguru import logger

from services.s3_ferry_service import S3Ferry


class MultiChunkService:
    """Service class for handling multiple chunk operations."""

    def __init__(self):
        """Initialize the multi-chunk service."""
        self.s3_ferry_service = S3Ferry()
        logger.info("MultiChunkService initialized")

    def download_single_chunk_from_s3(
        self, dataset_id: str, chunk_id: int
    ) -> Dict[str, Any]:
        """
        Download a single chunk from S3 bucket.

        Args:
            dataset_id: Dataset ID
            chunk_id: Chunk ID to download

        Returns:
            Dictionary containing download result
        """
        try:
            logger.info(f"Downloading chunk {chunk_id} for dataset {dataset_id}")

            # Define S3 source path and local destination
            chunk_filename = f"{chunk_id}.json"
            s3_source_path = f"{dataset_id}/{chunk_filename}"
            local_dest_path = f"temp_chunks/{chunk_filename}"

            # Create the temp_chunks directory if it doesn't exist
            os.makedirs("temp_chunks", exist_ok=True)

            # Download chunk from S3 using S3Ferry service
            response = self.s3_ferry_service.transfer_file(
                destination_file_path=local_dest_path,
                destination_storage_type="FS",
                source_file_path=s3_source_path,
                source_storage_type="S3",
            )

            logger.info(
                f"S3Ferry response status for chunk {chunk_id}: {response.status_code}"
            )

            if response.status_code in [200, 201]:
                # Read the downloaded chunk file
                local_file_path = f"/app/{local_dest_path}"

                if os.path.exists(local_file_path):
                    logger.info(
                        f"Successfully downloaded chunk {chunk_id} to: {local_file_path}"
                    )

                    # Read and parse the chunk data
                    with open(local_file_path, "r", encoding="utf-8") as f:
                        chunk_data = json.load(f)

                    # Clean up the downloaded file
                    os.remove(local_file_path)
                    logger.info(f"Cleaned up downloaded file: {local_file_path}")

                    return {
                        "success": True,
                        "chunk_id": chunk_id,
                        "chunk_data": chunk_data,
                        "message": f"Successfully downloaded chunk {chunk_id}",
                    }
                else:
                    return {
                        "success": False,
                        "chunk_id": chunk_id,
                        "error": f"Downloaded file not found at: {local_file_path}",
                        "message": f"Chunk {chunk_id} download completed but file not accessible",
                    }
            else:
                return {
                    "success": False,
                    "chunk_id": chunk_id,
                    "error": f"S3 download failed: HTTP {response.status_code}",
                    "response_body": response.text,
                    "message": f"Failed to download chunk {chunk_id} from S3",
                }

        except Exception as e:
            logger.error(f"Error downloading chunk {chunk_id}: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "chunk_id": chunk_id,
                "error": str(e),
                "message": f"Internal error during chunk {chunk_id} download",
            }

    def download_multiple_chunks(
        self, dataset_id: str, chunk_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Download multiple chunks from S3 and aggregate them.

        Args:
            dataset_id: Dataset ID
            chunk_ids: List of chunk IDs to download

        Returns:
            Dictionary containing aggregated chunk data or error information
        """
        try:
            logger.info(
                f"Starting multi-chunk download - Dataset ID: {dataset_id}, Chunks: {chunk_ids}"
            )

            download_results = []
            successful_chunks = []
            failed_chunks = []
            aggregated_data = []
            total_items = 0

            # Download each chunk
            for chunk_id in chunk_ids:
                result = self.download_single_chunk_from_s3(dataset_id, chunk_id)
                download_results.append(result)

                if result["success"]:
                    successful_chunks.append(chunk_id)
                    chunk_data = result["chunk_data"]

                    # Extract data array from chunk
                    chunk_items = chunk_data.get("data", [])
                    aggregated_data.extend(chunk_items)
                    total_items += len(chunk_items)

                    logger.info(
                        f"✅ Chunk {chunk_id}: {len(chunk_items)} items added to aggregation"
                    )
                else:
                    failed_chunks.append(chunk_id)
                    logger.error(
                        f"❌ Chunk {chunk_id}: Download failed - {result.get('error', 'Unknown error')}"
                    )

            # Prepare chunk info from the first successful chunk (if any)
            chunk_info = {}
            if successful_chunks and download_results:
                first_successful = next(
                    (r for r in download_results if r["success"]), None
                )
                if first_successful:
                    original_chunk_info = first_successful["chunk_data"].get(
                        "chunk_info", {}
                    )
                    chunk_info = {
                        "original_dataset": original_chunk_info.get(
                            "original_dataset", dataset_id
                        ),
                        "requested_chunks": chunk_ids,
                        "successful_chunks": successful_chunks,
                        "failed_chunks": failed_chunks,
                        "total_chunks_requested": len(chunk_ids),
                        "successful_downloads": len(successful_chunks),
                        "failed_downloads": len(failed_chunks),
                        "total_aggregated_items": total_items,
                        "aggregation_range": f"chunks {min(successful_chunks)}-{max(successful_chunks)}"
                        if successful_chunks
                        else "none",
                    }

            # Prepare the final aggregated payload
            if successful_chunks:
                aggregated_payload = {
                    "success": True,
                    "dataset_id": dataset_id,
                    "chunk_info": chunk_info,
                    "aggregated_data": aggregated_data,
                    "download_summary": {
                        "total_requested": len(chunk_ids),
                        "successful_downloads": len(successful_chunks),
                        "failed_downloads": len(failed_chunks),
                        "successful_chunk_ids": successful_chunks,
                        "failed_chunk_ids": failed_chunks,
                        "total_items_aggregated": total_items,
                    },
                    "download_details": download_results,
                    "message": f"Successfully aggregated {len(successful_chunks)} out of {len(chunk_ids)} requested chunks",
                }
            else:
                aggregated_payload = {
                    "success": False,
                    "dataset_id": dataset_id,
                    "chunk_info": chunk_info,
                    "aggregated_data": [],
                    "download_summary": {
                        "total_requested": len(chunk_ids),
                        "successful_downloads": 0,
                        "failed_downloads": len(failed_chunks),
                        "successful_chunk_ids": [],
                        "failed_chunk_ids": failed_chunks,
                        "total_items_aggregated": 0,
                    },
                    "download_details": download_results,
                    "error": "All chunk downloads failed",
                    "message": f"Failed to download any of the {len(chunk_ids)} requested chunks",
                }

            logger.info(
                f"Multi-chunk aggregation completed - Success: {aggregated_payload['success']}"
            )
            logger.info(f"Total items aggregated: {total_items}")

            return aggregated_payload

        except Exception as e:
            logger.error(f"Error during multi-chunk aggregation: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "dataset_id": dataset_id,
                "chunk_info": {},
                "aggregated_data": [],
                "download_summary": {
                    "total_requested": len(chunk_ids),
                    "successful_downloads": 0,
                    "failed_downloads": len(chunk_ids),
                    "successful_chunk_ids": [],
                    "failed_chunk_ids": chunk_ids,
                    "total_items_aggregated": 0,
                },
                "error": str(e),
                "message": "Internal error during multi-chunk aggregation",
            }

    def parse_chunk_ids(self, chunk_ids_str: str) -> List[int]:
        """
        Parse chunk IDs from string format.

        Args:
            chunk_ids_str: Space-separated chunk IDs (e.g., "1 2 3")

        Returns:
            List of chunk IDs as integers
        """
        try:
            chunk_ids = [
                int(x.strip()) for x in chunk_ids_str.split() if x.strip().isdigit()
            ]
            logger.info(f"Parsed chunk IDs: {chunk_ids}")
            return chunk_ids
        except Exception as e:
            logger.error(f"Error parsing chunk IDs '{chunk_ids_str}': {str(e)}")
            return []
