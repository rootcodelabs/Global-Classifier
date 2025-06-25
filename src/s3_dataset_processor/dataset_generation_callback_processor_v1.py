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
from pathlib import Path
import traceback

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

try:
    from services.url_decoder_service import URLDecoderService
    url_decoder_service = URLDecoderService()
    logger.info("✅ Successfully imported URLDecoderService")
except ImportError as e:
    logger.error(f"❌ Failed to import URLDecoderService: {e}")
    traceback.print_exc()
    sys.exit(1)

def process_callback_background(file_path: str, encoded_results: str):
    """
    Process the dataset generation callback.
    This is the same function from s3_processor_api.py but now runs synchronously.
    """
    try:
        print(f"[CALLBACK] Starting processing for: {file_path}")

        # Extract dataset ID from file path (e.g., output_datasets/single_question/12.json -> 12)
        dataset_id_match = re.search(r"/([^/]+)\.json$", file_path)
        dataset_id = dataset_id_match.group(1) if dataset_id_match else "unknown"

        logger.info(f"[CALLBACK] Extracted dataset ID: {dataset_id}")

        # Decode the results using the existing service
        decoded_results = url_decoder_service.decode_signed_urls(encoded_results)

        logger.info(f"[CALLBACK] Decoded {len(decoded_results)} results")

        # Process the decoded results to create the required payload
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

        except Exception as unexpected_error:
            logger.error(
                f"[CALLBACK] ❌ Unexpected error during status update: {str(unexpected_error)}"
            )

        logger.info("[CALLBACK] Processing completed successfully")

    except Exception as e:
        logger.error(f"[CALLBACK] Error in processing: {str(e)}")
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
        error_response = {
            "message": f"Callback processing failed: {str(e)}",
            "status": "error",
            "file_path": args.file_path
        }
        
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(error_response, f, indent=2)
        
        print(json.dumps(error_response))
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()