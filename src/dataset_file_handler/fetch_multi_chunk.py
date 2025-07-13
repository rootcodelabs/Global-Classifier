#!/usr/bin/env python3
"""
Python script to download multiple chunks from S3 bucket, aggregate them, and return as JSON.
Used by CronManager endpoint to fetch and combine multiple chunks.
"""

import sys
import json
import argparse
import logging
import os
from pathlib import Path
import traceback
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],  # Log to stderr to keep stdout clean
)
logger = logging.getLogger(__name__)

# Add the s3_dataset_processor to Python path to import modules
script_dir = Path("/app/src/s3_dataset_processor")
sys.path.insert(0, str(script_dir))


def log(message):
    """Log to stderr to keep stdout clean for JSON output"""
    logger.info(f"📦 [MULTI CHUNK] {message}")


try:
    from services.s3_ferry_service import S3Ferry

    s3_ferry_service = S3Ferry()
    log("Successfully imported S3FerryService")
except ImportError as e:
    log(f"Failed to import S3FerryService: {e}")
    sys.exit(1)


def download_single_chunk_from_s3(dataset_id: str, chunk_id: int) -> Dict[str, Any]:
    """
    Download a single chunk from S3 bucket.

    Args:
        dataset_id: Dataset ID
        chunk_id: Chunk ID/number

    Returns:
        Dictionary containing chunk data or error information
    """
    try:
        log(f"Downloading chunk {chunk_id} from dataset {dataset_id}")

        # Define S3 source path and local destination
        chunk_filename = f"{chunk_id}.json"
        s3_source_path = f"{dataset_id}/{chunk_filename}"
        local_dest_path = f"temp_chunks/{chunk_filename}"

        # Create the temp_chunks directory if it doesn't exist
        temp_chunks_dir = "/app/temp_chunks"
        os.makedirs(temp_chunks_dir, exist_ok=True)

        log(f"S3 source path: {s3_source_path}")
        log(f"Local destination: {local_dest_path}")

        # Download chunk from S3 using S3Ferry service
        response = s3_ferry_service.transfer_file(
            destination_file_path=local_dest_path,
            destination_storage_type="FS",
            source_file_path=s3_source_path,
            source_storage_type="S3",
        )

        log(f"S3Ferry response status for chunk {chunk_id}: {response.status_code}")

        if response.status_code in [200, 201]:
            # Read the downloaded chunk file
            local_file_path = f"/app/{local_dest_path}"

            if os.path.exists(local_file_path):
                log(f"Successfully downloaded chunk {chunk_id} to: {local_file_path}")

                # Read and parse the chunk data
                with open(local_file_path, "r", encoding="utf-8") as f:
                    chunk_data = json.load(f)

                # Clean up the downloaded file
                os.remove(local_file_path)
                log(f"Cleaned up downloaded file: {local_file_path}")

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
        log(f"Error downloading chunk {chunk_id}: {str(e)}")
        traceback.print_exc()
        return {
            "success": False,
            "chunk_id": chunk_id,
            "error": str(e),
            "message": f"Internal error during chunk {chunk_id} download",
        }


def download_multiple_chunks(dataset_id: str, chunk_ids: List[int]) -> Dict[str, Any]:
    """
    Download multiple chunks from S3 and aggregate them.

    Args:
        dataset_id: Dataset ID
        chunk_ids: List of chunk IDs to download

    Returns:
        Dictionary containing aggregated chunk data or error information
    """
    try:
        log(
            f"Starting multi-chunk download - Dataset ID: {dataset_id}, Chunks: {chunk_ids}"
        )

        download_results = []
        successful_chunks = []
        failed_chunks = []
        aggregated_data = []
        total_items = 0

        # Download each chunk
        for chunk_id in chunk_ids:
            result = download_single_chunk_from_s3(dataset_id, chunk_id)
            download_results.append(result)

            if result["success"]:
                successful_chunks.append(chunk_id)
                chunk_data = result["chunk_data"]

                # Extract data array from chunk
                chunk_items = chunk_data.get("data", [])
                aggregated_data.extend(chunk_items)
                total_items += len(chunk_items)

                log(
                    f"✅ Chunk {chunk_id}: {len(chunk_items)} items added to aggregation"
                )
            else:
                failed_chunks.append(chunk_id)
                log(
                    f"❌ Chunk {chunk_id}: Download failed - {result.get('error', 'Unknown error')}"
                )

        # Prepare chunk info from the first successful chunk (if any)
        chunk_info = {}
        if successful_chunks and download_results:
            first_successful = next((r for r in download_results if r["success"]), None)
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

        log(
            f"Multi-chunk aggregation completed - Success: {aggregated_payload['success']}"
        )
        log(f"Total items aggregated: {total_items}")

        return aggregated_payload

    except Exception as e:
        log(f"Error during multi-chunk aggregation: {str(e)}")
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


def parse_chunk_ids(chunk_ids_str: str) -> List[int]:
    """
    Parse chunk IDs from string format "1 2 3" to list [1, 2, 3].

    Args:
        chunk_ids_str: String containing space-separated chunk IDs

    Returns:
        List of integer chunk IDs
    """
    try:
        # Split by spaces and convert to integers
        chunk_ids = [
            int(chunk_id.strip())
            for chunk_id in chunk_ids_str.split()
            if chunk_id.strip()
        ]
        log(f"Parsed chunk IDs: {chunk_ids}")
        return chunk_ids
    except ValueError as e:
        log(f"Error parsing chunk IDs '{chunk_ids_str}': {str(e)}")
        raise ValueError(
            f"Invalid chunk IDs format. Expected space-separated integers, got: '{chunk_ids_str}'"
        )


def main():
    """Main function to handle multi-chunk download and aggregation process."""
    parser = argparse.ArgumentParser(
        description="Download and aggregate multiple chunks from S3"
    )
    parser.add_argument("--dataset-id", required=True, help="Dataset ID")
    parser.add_argument(
        "--chunk-ids", required=True, help='Space-separated chunk IDs (e.g., "1 2 3")'
    )
    parser.add_argument("--output-json", help="Output file path for results JSON")

    args = parser.parse_args()

    try:
        log(
            f"Processing multi-chunk request - Dataset: {args.dataset_id}, Chunk IDs: {args.chunk_ids}"
        )

        # Parse chunk IDs
        chunk_ids = parse_chunk_ids(args.chunk_ids)

        if not chunk_ids:
            raise ValueError("No valid chunk IDs provided")

        # Download and aggregate chunks
        result = download_multiple_chunks(args.dataset_id, chunk_ids)

        # Output results
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(result, f, indent=2)
            log(f"Results written to {args.output_json}")
        else:
            # Output ONLY the JSON to stdout (this goes to CronManager)
            print(json.dumps(result))

        log(f"Multi-chunk processing completed - Success: {result['success']}")

        # Exit with appropriate code
        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        log(f"Internal error: {str(e)}")
        traceback.print_exc()

        error_result = {
            "success": False,
            "dataset_id": args.dataset_id,
            "chunk_ids": args.chunk_ids,
            "error": str(e),
            "message": "Script execution failed",
        }

        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(error_result, f, indent=2)
        else:
            print(json.dumps(error_result))

        sys.exit(1)


if __name__ == "__main__":
    main()
