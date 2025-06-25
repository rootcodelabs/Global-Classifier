#!/usr/bin/env python3
"""
Python script to download a specific chunk from S3 bucket and return as JSON.
Used by CronManager endpoint to fetch individual chunks.
"""
import sys
import json
import argparse
import logging
import os
import tempfile
from pathlib import Path
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stderr)]  # Log to stderr to keep stdout clean
)
logger = logging.getLogger(__name__)

# Add the s3_dataset_processor to Python path to import modules
script_dir = Path('/app/src/s3_dataset_processor')
sys.path.insert(0, str(script_dir))

def log(message):
    """Log to stderr to keep stdout clean for JSON output"""
    logger.info(f"🔍 [CHUNK DOWNLOAD] {message}")

try:
    from services.s3_ferry_service import S3Ferry
    s3_ferry_service = S3Ferry()
    log("Successfully imported S3FerryService")
except ImportError as e:
    log(f"Failed to import S3FerryService: {e}")
    sys.exit(1)

def download_chunk_from_s3(dataset_id: str, page_num: int) -> dict:
    """
    Download a specific chunk from S3 bucket.
    
    Args:
        dataset_id: Dataset ID
        page_num: Page number (chunk number)
    
    Returns:
        Dictionary containing chunk data or error information
    """
    try:
        log(f"Starting chunk download - Dataset ID: {dataset_id}, Page: {page_num}")
        
        # Create temporary directory for download
        temp_dir = tempfile.mkdtemp(prefix="chunk_download_")
        log(f"Created temporary directory: {temp_dir}")
        
        # Define S3 source path and local destination
        chunk_filename = f"{page_num}.json"
        s3_source_path = f"{dataset_id}/{chunk_filename}"
        local_dest_path = f"temp_chunks/{chunk_filename}"

        # Create the temp_chunks directory if it doesn't exist
        temp_chunks_dir = "temp_chunks"
        os.makedirs(temp_chunks_dir, exist_ok=True)
        log(f"Created/verified temp directory: {temp_chunks_dir}")
        
        log(f"S3 source path: {s3_source_path}")
        log(f"Local destination: {local_dest_path}")
        
        # Download chunk from S3 using S3Ferry service
        response = s3_ferry_service.transfer_file(
            destination_file_path=local_dest_path,
            destination_storage_type="FS",
            source_file_path=s3_source_path,
            source_storage_type="S3"
        )
        
        log(f"S3Ferry response status: {response.status_code}")
        log(f"S3Ferry response body: {response.text}")
        
        if response.status_code in [200, 201]:
            # Read the downloaded chunk file
            local_file_path = f"/app/{local_dest_path}"
            
            if os.path.exists(local_file_path):
                log(f"Successfully downloaded chunk to: {local_file_path}")
                
                # Read and parse the chunk data
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    chunk_data = json.load(f)
                
                # Clean up the downloaded file
                os.remove(local_file_path)
                log(f"Cleaned up downloaded file: {local_file_path}")
                
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
        log(f"Error during chunk download: {str(e)}")
        traceback.print_exc()
        return {
            "success": False,
            "dataset_id": dataset_id,
            "page_num": page_num,
            "error": str(e),
            "message": "Internal error during chunk download"
        }

def main():
    """Main function to handle chunk download process."""
    parser = argparse.ArgumentParser(description='Download a specific chunk from S3')
    parser.add_argument('--dataset-id', required=True, help='Dataset ID')
    parser.add_argument('--page-num', required=True, type=int, help='Page number (chunk number)')
    parser.add_argument('--output-json', help='Output file path for results JSON')
    
    args = parser.parse_args()
    
    try:
        log(f"Processing chunk download request - Dataset: {args.dataset_id}, Page: {args.page_num}")
        
        # Download the chunk
        result = download_chunk_from_s3(args.dataset_id, args.page_num)
        
        # Output results
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(result, f, indent=2)
            log(f"Results written to {args.output_json}")
        else:
            # Output ONLY the JSON to stdout (this goes to CronManager)
            print(json.dumps(result))
        
        log(f"Chunk download completed - Success: {result['success']}")
        
        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        log(f"Internal error: {str(e)}")
        traceback.print_exc()
        
        error_result = {
            "success": False,
            "dataset_id": args.dataset_id,
            "page_num": args.page_num,
            "error": str(e),
            "message": "Script execution failed"
        }
        
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(error_result, f, indent=2)
        else:
            print(json.dumps(error_result))
        
        sys.exit(1)

if __name__ == "__main__":
    main()