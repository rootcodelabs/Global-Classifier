#!/usr/bin/env python3
"""
Standalone script for processing dataset generation callbacks.
Replaces the FastAPI background task with direct synchronous execution.
"""
import sys
import json
import argparse
import logging
import re
import requests
import traceback
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add the s3_dataset_processor to Python path to import modules
script_dir = Path('/app/src/s3_dataset_processor')
sys.path.insert(0, str(script_dir))

logger.info(f"🔍 Script directory: {script_dir}")
logger.info(f"🔍 Script directory exists: {script_dir.exists()}")
logger.info(f"🔍 Python path: {sys.path}")

try:
    from services.url_decoder_service import URLDecoderService
    from services.s3_ferry_service import S3Ferry
    url_decoder_service = URLDecoderService()
    s3_ferry_service = S3Ferry()
    logger.info("✅ Successfully imported URLDecoderService")
except ImportError as e:
    logger.error(f"❌ Failed to import URLDecoderService: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(f"Script directory exists: {script_dir.exists()}")
    if script_dir.exists():
        logger.error(f"Contents of script directory: {list(script_dir.iterdir())}")
        # Try to check services directory
        services_dir = script_dir / 'services'
        if services_dir.exists():
            logger.error(f"Contents of services directory: {list(services_dir.iterdir())}")
    traceback.print_exc()
    sys.exit(1)

def chunk_dataset(dataset_path: str, chunk_size: int = 5):
    """
    Chunk the generated dataset into smaller files with specified number of records.
    
    Args:
        dataset_path: Path to the generated dataset JSON file
        chunk_size: Number of records per chunk (default: 5)
    
    Returns:
        List of chunk file paths created
    """
    try:
        logger.info(f"[CHUNKING] Starting chunking for: {dataset_path}")
        
        # Read the original dataset
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        
        aggregated_data = dataset.get('aggregated_data', [])
        total_items = len(aggregated_data)
        
        logger.info(f"[CHUNKING] Total items to chunk: {total_items}")
        logger.info(f"[CHUNKING] Chunk size: {chunk_size}")
        
        if total_items == 0:
            logger.warning("[CHUNKING] No data to chunk")
            return []
        
        # Create chunks directory
        dataset_name = Path(dataset_path).stem
        chunks_dir = Path(dataset_path).parent / f"{dataset_name}_chunks"
        chunks_dir.mkdir(exist_ok=True)
        
        chunk_files = []
        
        # Create chunks with incremental naming (1.json, 2.json, etc.)
        for i in range(0, total_items, chunk_size):
            chunk_data = aggregated_data[i:i + chunk_size]
            chunk_number = (i // chunk_size) + 1
            
            # Use simple incremental naming: 1.json, 2.json, 3.json, etc.
            chunk_filename = f"{chunk_number}.json"
            chunk_path = chunks_dir / chunk_filename
            
            # Create chunk with metadata
            chunk_content = {
                "chunk_info": {
                    "original_dataset": dataset_name,
                    "chunk_number": chunk_number,
                    "total_chunks": (total_items + chunk_size - 1) // chunk_size,
                    "items_in_chunk": len(chunk_data),
                    "chunk_range": f"{i + 1}-{min(i + chunk_size, total_items)}"
                },
                "data": chunk_data
            }
            
            # Write chunk file
            with open(chunk_path, 'w', encoding='utf-8') as f:
                json.dump(chunk_content, f, indent=2, ensure_ascii=False)
            
            chunk_files.append(str(chunk_path))
            logger.info(f"[CHUNKING] Created chunk {chunk_number}: {chunk_filename} ({len(chunk_data)} items)")
        
        logger.info(f"[CHUNKING] ✅ Created {len(chunk_files)} chunk files in: {chunks_dir}")
        return chunk_files
        
    except Exception as e:
        logger.error(f"[CHUNKING] ❌ Error during chunking: {str(e)}")
        traceback.print_exc()
        raise

def upload_chunks_to_s3(chunk_files: list, dataset_id: str):
    """
    Upload chunk files to S3 using S3Ferry service.
    
    Args:
        chunk_files: List of chunk file paths to upload
        dataset_id: Dataset ID for organizing uploads
    
    Returns:
        List of upload results with S3 URLs
    """
    try:
        logger.info(f"[S3_UPLOAD] Starting S3 upload for {len(chunk_files)} chunks using S3Ferry service")
        
        upload_results = []
        
        for chunk_file in chunk_files:
            # Extract just the filename (e.g., "1.json", "2.json")
            chunk_filename = Path(chunk_file).name
            
            logger.info(f"[S3_UPLOAD] Processing chunk file: {chunk_file}")
            logger.info(f"[S3_UPLOAD] Chunk filename: {chunk_filename}")
            
            # Create the exact payload format you specified
            # destinationFilePath: "/{dataset_id}/{filename}" (e.g., "/3/2.json")
            destination_file_path = f"/{dataset_id}/{chunk_filename}"
            
            # sourceFilePath: relative path from gc-s3-ferry's volume mount (e.g., "output_datasets/3_chunks/2.json")
            source_file_path = f"output_datasets/{dataset_id}_chunks/{chunk_filename}"
            
            logger.info(f"[S3_UPLOAD] Destination path: {destination_file_path}")
            logger.info(f"[S3_UPLOAD] Source path: {source_file_path}")
            
            try:
                # Use S3Ferry service with exact payload format
                response = s3_ferry_service.transfer_file(
                    destination_file_path=destination_file_path,     # "/3/2.json"
                    destination_storage_type="S3",                  # "S3"
                    source_file_path=source_file_path,              # "output_datasets/3_chunks/2.json"
                    source_storage_type="FS"                        # "FS"
                )
                
                logger.info(f"[S3_UPLOAD] S3Ferry response status: {response.status_code}")
                logger.info(f"[S3_UPLOAD] S3Ferry response body: {response.text}")
                
                # Accept both 200 (OK) and 201 (Created) as success
                if response.status_code in [200, 201]:
                    # Parse response if needed
                    response_data = {}
                    try:
                        response_data = response.json() if response.text else {}
                    except Exception:
                        pass
            
                    
                    upload_results.append({
                        "chunk_file": chunk_filename,
                        "destination_path": destination_file_path,
                        "source_path": source_file_path,
                        "success": True,
                        "response": response_data,
                        "status_code": response.status_code
                    })
                    logger.info(f"[S3_UPLOAD] ✅ Uploaded: {chunk_filename} ->  (HTTP {response.status_code})")
                else:
                    upload_results.append({
                        "chunk_file": chunk_filename,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "success": False,
                        "source_path": source_file_path,
                        "status_code": response.status_code
                    })
                    logger.error(f"[S3_UPLOAD] ❌ Failed to upload {chunk_filename}: HTTP {response.status_code}")
                    logger.error(f"[S3_UPLOAD] Response: {response.text}")
            
            except requests.exceptions.RequestException as e:
                upload_results.append({
                    "chunk_file": chunk_filename,
                    "error": str(e),
                    "success": False,
                    "source_path": source_file_path
                })
                logger.error(f"[S3_UPLOAD] ❌ Request failed for {chunk_filename}: {str(e)}")
                traceback.print_exc()
            
            except Exception as e:
                upload_results.append({
                    "chunk_file": chunk_filename,
                    "error": str(e),
                    "success": False,
                    "source_path": source_file_path
                })
                logger.error(f"[S3_UPLOAD] ❌ Unexpected error for {chunk_filename}: {str(e)}")
                traceback.print_exc()
        
        successful_uploads = [r for r in upload_results if r.get('success', False)]
        failed_uploads = [r for r in upload_results if not r.get('success', False)]
        
        logger.info(f"[S3_UPLOAD] ✅ Upload complete: {len(successful_uploads)} successful, {len(failed_uploads)} failed")
        
        # Log detailed results
        if successful_uploads:
            logger.info("[S3_UPLOAD] 📊 Successful uploads:")
            for result in successful_uploads:
                status_code = result.get('status_code', 'unknown')
                logger.info(f"[S3_UPLOAD]   - {result['chunk_file']}: {result['s3_url']} (HTTP {status_code})")
        
        if failed_uploads:
            logger.warning("[S3_UPLOAD] ⚠️ Failed uploads:")
            for result in failed_uploads:
                logger.warning(f"[S3_UPLOAD]   - {result['chunk_file']}: {result['error']}")
        
        return upload_results
        
    except Exception as e:
        logger.error(f"[S3_UPLOAD] ❌ Error during S3 upload: {str(e)}")
        traceback.print_exc()
        raise

def update_chunk_metadata(chunk_file_path: str, dataset_id: str, chunk_number: int):
    """
    Update chunk metadata in the database after successful S3 upload.
    
    Args:
        chunk_file_path: Path to the chunk file to extract agency information
        dataset_id: Dataset ID 
        chunk_number: Chunk number (1, 2, 3, etc.)
    
    Returns:
        Response from the metadata update endpoint
    """
    try:
        logger.info(f"[CHUNK_METADATA] Updating metadata for chunk {chunk_number} of dataset {dataset_id}")
        
        # Read the chunk file to extract agency information
        with open(chunk_file_path, 'r', encoding='utf-8') as f:
            chunk_data = json.load(f)
        
        # Extract agency IDs from the chunk data
        chunk_items = chunk_data.get('data', [])
        agency_ids = []
        
        for item in chunk_items:
            agency_id = item.get('agency_id', 'unknown')
            agency_ids.append(agency_id)
        
        logger.info(f"[CHUNK_METADATA] Extracted {len(agency_ids)} agency IDs: {agency_ids}")
        
        # Create the payload for the metadata endpoint
        metadata_payload = {
            "datasetId": int(dataset_id),
            "chunkId": chunk_number,
            "includedAgencies": json.dumps(agency_ids)  # Convert array to JSON string
        }
        
        logger.info(f"[CHUNK_METADATA] Payload: {json.dumps(metadata_payload, indent=2)}")
        
        # Send POST request to the chunk metadata endpoint
        CHUNK_METADATA_URL = "http://resql:8082/global-classifier/update-data-chunk-metadata"
        
        response = requests.post(
            CHUNK_METADATA_URL,
            json=metadata_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        logger.info(f"[CHUNK_METADATA] Response status: {response.status_code}")
        logger.info(f"[CHUNK_METADATA] Response body: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"[CHUNK_METADATA] ✅ Successfully updated metadata for chunk {chunk_number}")
        else:
            logger.warning(f"[CHUNK_METADATA] ⚠️ Metadata update failed for chunk {chunk_number}: HTTP {response.status_code}")
        
        return response
        
    except Exception as e:
        logger.error(f"[CHUNK_METADATA] ❌ Error updating chunk metadata: {str(e)}")
        traceback.print_exc()
        raise

def process_callback_background(file_path: str, encoded_results: str):
    """
    Process the dataset generation callback with chunking and S3 upload.
    This is the same function from s3_processor_api.py but now runs synchronously.
    """
    try:
        print(f"[CALLBACK] Starting processing for: {file_path}")

        # Extract dataset ID from file path (e.g., output_datasets/single_question/12.json -> 12)
        dataset_id_match = re.search(r"/([^/]+)\.json$", file_path)
        dataset_id = dataset_id_match.group(1) if dataset_id_match else "unknown"

        logger.info(f"[CALLBACK] Extracted dataset ID: {dataset_id}")

        # Step 1: Decode the results using the existing service
        decoded_results = url_decoder_service.decode_signed_urls(encoded_results)
        logger.info(f"[CALLBACK] Decoded {len(decoded_results)} results")

        # Step 2: Chunk the generated dataset
        full_dataset_path = f"/app/output_datasets/{dataset_id}.json"
        if os.path.exists(full_dataset_path):
            logger.info(f"[CALLBACK] Found dataset file: {full_dataset_path}")
            # Step 2.1: Upload the original aggregated dataset file
            logger.info("[CALLBACK] 📤 Starting upload of original aggregated dataset...")
            try:
                # Upload the original dataset file to S3
                original_dataset_response = s3_ferry_service.transfer_file(
                    destination_file_path=f"/{dataset_id}/aggregated_dataset.json",  # "/3/aggregated_dataset.json"
                    destination_storage_type="S3",
                    source_file_path=f"output_datasets/{dataset_id}.json",          # "output_datasets/3.json"
                    source_storage_type="FS"
                )
                
                logger.info(f"[CALLBACK] Original dataset upload status: {original_dataset_response.status_code}")
                logger.info(f"[CALLBACK] Original dataset upload response: {original_dataset_response.text}")
                
                if original_dataset_response.status_code in [200, 201]:
                    original_s3_url = f"s3://global-classifier/{dataset_id}/aggregated_dataset.json"
                    logger.info(f"[CALLBACK] ✅ Original dataset uploaded: {original_s3_url}")
                    
                else:
                    logger.error(f"[CALLBACK] ❌ Failed to upload original dataset: HTTP {original_dataset_response.status_code}")
                    
                    
            except Exception as e:
                logger.error(f"[CALLBACK] ❌ Error uploading original dataset: {str(e)}")
                traceback.print_exc()

            # Step 2.2: Chunk the generated dataset
            chunk_files = chunk_dataset(full_dataset_path, chunk_size=5)
            
            # Step 3: Upload chunks to S3
            if chunk_files:
                upload_results = upload_chunks_to_s3(chunk_files, dataset_id)
                
                # Log upload summary
                successful_uploads = [r for r in upload_results if r.get('success', False)]
                logger.info(f"[CALLBACK] 📊 S3 Upload Summary:")
                logger.info(f"[CALLBACK]   - Total chunks: {len(chunk_files)}")
                logger.info(f"[CALLBACK]   - Successful uploads: {len(successful_uploads)}")
                logger.info(f"[CALLBACK]   - Failed uploads: {len(upload_results) - len(successful_uploads)}")
                
                # Log S3 URLs
                for result in successful_uploads:
                    logger.info(f"[CALLBACK]   - {result['chunk_file']}: {result['s3_url']}")

                # Step 3.5: Update chunk metadata for successfully uploaded chunks
                logger.info("[CALLBACK] 🔄 Starting chunk metadata updates...")
                metadata_results = []
                for i, chunk_file in enumerate(chunk_files):
                    chunk_number = i + 1  # Chunks are numbered 1, 2, 3, etc.
                    
                    # Only update metadata for successfully uploaded chunks
                    chunk_filename = Path(chunk_file).name
                    upload_success = any(
                        result['chunk_file'] == chunk_filename and result['success'] 
                        for result in upload_results
                    )
                    
                    if upload_success:
                        try:
                            metadata_response = update_chunk_metadata(
                                chunk_file_path=chunk_file,
                                dataset_id=dataset_id,
                                chunk_number=chunk_number
                            )
                            
                            metadata_results.append({
                                "chunk_number": chunk_number,
                                "chunk_file": chunk_filename,
                                "success": metadata_response.status_code == 200,
                                "response": metadata_response.text
                            })
                            
                        except Exception as e:
                            logger.error(f"[CALLBACK] ❌ Failed to update metadata for chunk {chunk_number}: {str(e)}")
                            metadata_results.append({
                                "chunk_number": chunk_number,
                                "chunk_file": chunk_filename,
                                "success": False,
                                "error": str(e)
                            })
                    else:
                        logger.warning(f"[CALLBACK] ⚠️ Skipping metadata update for chunk {chunk_number} (upload failed)")
                        metadata_results.append({
                            "chunk_number": chunk_number,
                            "chunk_file": chunk_filename,
                            "success": False,
                            "error": "Upload failed"
                        })       
                
            else:
                logger.warning("[CALLBACK] No chunks created, skipping S3 upload")
        else:
            logger.warning(f"[CALLBACK] Dataset file not found: {full_dataset_path}")

        # Step 4: Process the decoded results to create the required payload
        agencies = []
        overall_success = True

        for i, result in enumerate(decoded_results):
            # Extract agency_id from dataset_metadata
            dataset_metadata = result.get("dataset_metadata", {})
            agency_id = dataset_metadata.get("agency_id", "unknown")
            success = result.get("success", False)

            sync_status = "Synced_with_CKB" if success else "Sync_with_CKB_Failed"

            agencies.append({"agencyId": agency_id, "syncStatus": sync_status})

            logger.info(
                f"[CALLBACK] Agency {i + 1}: ID={agency_id}, Success={success}, Status={sync_status}"
            )

            if not success:
                overall_success = False

        generation_status = (
            "Generation_Success" if overall_success else "Generation_Failed"
        )

        # Create the exact payload format requested
        callback_payload = {
            "agencies": agencies,
            "datasetId": dataset_id,
            "generationStatus": generation_status,
        }

        # Log the processed callback
        logger.info(f"[CALLBACK] {json.dumps(callback_payload, indent=2)}")
        logger.info(f"[CALLBACK] Dataset ID: {dataset_id}")
        logger.info(f"[CALLBACK] Generation Status: {generation_status}")
        logger.info(f"[CALLBACK] Total Agencies: {len(agencies)}")
        logger.info(
            f"[CALLBACK] Successful Agencies: {len([a for a in agencies if a['syncStatus'] == 'Synced_with_CKB'])}"
        )
        logger.info(
            f"[CALLBACK] Failed Agencies: {len([a for a in agencies if a['syncStatus'] == 'Sync_with_CKB_Failed'])}"
        )

        # Step 5: Send status update to Ruuter
        STATUS_UPDATE_URL = (
            "http://ruuter-public:8086/global-classifier/agencies/data/generation"
        )

        logger.info(f"[CALLBACK] Sending callback payload to: {STATUS_UPDATE_URL}")

        try:
            # Send POST request to the status update endpoint
            response = requests.post(
                STATUS_UPDATE_URL,
                json=callback_payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            logger.info(
                f"[CALLBACK] Status update response - HTTP Status: {response.status_code}"
            )
            logger.info(f"[CALLBACK] Status update response body: {response.text}")

            if response.status_code == 200:
                logger.info(
                    "[CALLBACK] ✅ Successfully sent callback payload to status update endpoint"
                )
            else:
                logger.warning(
                    f"[CALLBACK] ⚠️ Status update endpoint returned non-200 status: {response.status_code}"
                )
                logger.info(f"[CALLBACK] Response: {response.text}")

        except requests.exceptions.RequestException as webhook_error:
            logger.error(
                f"[CALLBACK] ❌ Error sending callback to status update endpoint: {str(webhook_error)}"
            )
            logger.debug(f"[CALLBACK] URL: {STATUS_UPDATE_URL}")
            logger.debug(
                f"[CALLBACK] Payload: {json.dumps(callback_payload, indent=2)}"
            )
            traceback.print_exc()

        except Exception as unexpected_error:
            logger.error(
                f"[CALLBACK] ❌ Unexpected error during status update: {str(unexpected_error)}"
            )
            traceback.print_exc()

        logger.info("[CALLBACK] Processing completed successfully")

    except Exception as e:
        logger.error(f"[CALLBACK] Error in processing: {str(e)}")
        traceback.print_exc()
        raise

def main():
    """Main function to handle callback processing."""
    parser = argparse.ArgumentParser(description='Process dataset generation callback')
    parser.add_argument('--file-path', required=True, help='File path of the generated dataset')
    parser.add_argument('--encoded-results', required=True, help='Encoded results string')
    parser.add_argument('--output-json', help='Output JSON file path for response')
    
    args = parser.parse_args()
    
    try:
        logger.info("🔄 Starting callback processing...")
        logger.info(f"File path: {args.file_path}")
        logger.info(f"Encoded results length: {len(args.encoded_results)} characters")
        
        # Process the callback directly (synchronous execution)
        process_callback_background(args.file_path, args.encoded_results)
        
        # Create response
        response = {
            "message": "Callback processing completed successfully",
            "status": "completed",
            "file_path": args.file_path
        }
        
        # Output response to file if specified
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(response, f, indent=2)
            logger.info(f"✅ Response written to: {args.output_json}")
        
        # Also output to stdout for shell script
        print(json.dumps(response))
        
        logger.info("✅ Callback processing completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error processing callback: {str(e)}")
        traceback.print_exc()
        error_response = {
            "message": f"Callback processing failed: {str(e)}",
            "status": "error",
            "file_path": args.file_path
        }
        
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(error_response, f, indent=2)
        
        print(json.dumps(error_response))
        sys.exit(1)

if __name__ == "__main__":
    main()