#!/usr/bin/env python3
"""
Standalone script for processing dataset generation callbacks.
Uploads only the aggregated CSV, merging with previous if needed.
"""

import sys
import json
import argparse
import logging
import re
import requests
import traceback
import os
import pandas as pd
from constants import (
    DATASET_UPDATE_URL,
    STATUS_UPDATE_URL,
    AGGREGATED_CSV_FILE,
    OUTPUT_DATA_DIR,
    SYNCED_WITH_CKB,
    SYNC_WITH_CKB_FAILED,
    SCRIPT_DIR,
    PROGRESS_UPDATE_URL,
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# --- Python Path Setup ---
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from services.url_decoder_service import URLDecoderService
    from services.s3_ferry_service import S3Ferry

    url_decoder_service = URLDecoderService()
    s3_ferry_service = S3Ferry()
except ImportError as e:
    logger.error(f"Failed to import services: {e}")
    traceback.print_exc()
    sys.exit(1)


def update_item_ids(df: pd.DataFrame, dataset_id: int) -> pd.DataFrame:
    """Update item_id column to format {dataset_id}_{row_number} (1-based)."""
    if "item_id" in df.columns:
        df = df.copy()
        df["item_id"] = [f"{dataset_id}_{i + 1}" for i in range(len(df))]
    return df


def update_dataset_version_id(df: pd.DataFrame, dataset_id: int) -> pd.DataFrame:
    """Update dataset_version_id column to the current dataset_id."""
    if "dataset_version_id" in df.columns:
        df = df.copy()
        df["dataset_version_id"] = dataset_id
    return df


def combine_csvs_and_update_ids(
    prev_csv_path: str, curr_csv_path: str, dataset_id: int, output_path: str
) -> str:
    """Combine previous and current CSVs, update item_id and dataset_version_id, and save to output_path."""
    try:
        prev_df = pd.read_csv(prev_csv_path)
        curr_df = pd.read_csv(curr_csv_path)
        combined_df = pd.concat([prev_df, curr_df], ignore_index=True)
        combined_df = update_item_ids(combined_df, dataset_id)
        combined_df = update_dataset_version_id(combined_df, dataset_id)
        combined_df.to_csv(output_path, index=False)
        logger.info(f"Combined CSV saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error combining CSVs: {e}")
        raise


def upload_csv_to_s3(local_csv_path: str, dataset_id: int) -> None:
    """Upload the CSV file to S3 using S3Ferry."""
    destination_file_path = f"/datasets/{dataset_id}/{AGGREGATED_CSV_FILE}"
    source_file_path = local_csv_path.replace("/app/", "")
    logger.info(f"Uploading {local_csv_path} to S3 as {destination_file_path}")
    response = s3_ferry_service.transfer_file(
        destination_file_path=destination_file_path,
        destination_storage_type="S3",
        source_file_path=source_file_path,
        source_storage_type="FS",
    )
    logger.info(f"S3 upload status: {response.status_code}")
    logger.info(f"S3 upload response: {response.text}")
    if response.status_code not in [200, 201]:
        raise RuntimeError(f"Failed to upload CSV to S3: {response.text}")


def notify_progress_uploading_to_s3(session_id: int) -> None:
    """Notify progress update: New Dataset Uploading to S3."""
    payload = {
        "sessionId": session_id,
        "generationStatus": "Success",
        "generationMessage": "Dataset has been uploaded to S3 and Dataset Generation is completed.",
        "progressPercentage": 100,
        "processComplete": True,
    }
    try:
        logger.info(
            f"Calling progress update endpoint: {PROGRESS_UPDATE_URL} with payload={payload}"
        )
        response = requests.post(
            PROGRESS_UPDATE_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        logger.info(f"Progress update response - HTTP Status: {response.status_code}")
        logger.info(f"Progress update response body: {response.text}")
        if response.status_code not in [200, 201]:
            logger.warning(f"Progress update endpoint returned error: {response.text}")
    except Exception as e:
        logger.error(f"Error calling progress update endpoint: {e}")
        traceback.print_exc()


def notify_dataset_update(output_csv_path: str) -> None:
    """Notify local dataset update endpoint before uploading to S3."""
    update_payload = {"filePath": output_csv_path}
    try:
        logger.info(
            f"Calling dataset update endpoint: {DATASET_UPDATE_URL} with filePath={output_csv_path}"
        )
        update_response = requests.post(
            DATASET_UPDATE_URL,
            json=update_payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        logger.info(
            f"Dataset update response - HTTP Status: {update_response.status_code}"
        )
        logger.info(f"Dataset update response body: {update_response.text}")
        if update_response.status_code not in [200, 201]:
            logger.warning(
                f"Dataset update endpoint returned error: {update_response.text}"
            )
    except Exception as e:
        logger.error(f"Error calling dataset update endpoint: {e}")
        traceback.print_exc()


def send_status_update(dataset_id: int, encoded_results: str) -> None:
    """Send status update to Ruuter."""
    decoded_results = url_decoder_service.decode_signed_urls(encoded_results)
    agencies = []
    overall_success = True
    for result in decoded_results:
        dataset_metadata = result.get("dataset_metadata", {})
        agency_id = dataset_metadata.get("agency_id", "unknown")
        success = result.get("success", False)
        sync_status = SYNCED_WITH_CKB if success else SYNC_WITH_CKB_FAILED
        agencies.append({"agencyId": agency_id, "syncStatus": sync_status})
        if not success:
            overall_success = False

    generation_status = "Generation_Success" if overall_success else "Generation_Failed"
    callback_payload = {
        "agencies": agencies,
        "datasetId": dataset_id,
        "generationStatus": generation_status,
    }

    logger.info(f"Sending callback payload to: {STATUS_UPDATE_URL}")
    try:
        response = requests.post(
            STATUS_UPDATE_URL,
            json=callback_payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        logger.info(f"Status update response - HTTP Status: {response.status_code}")
        logger.info(f"Status update response body: {response.text}")
    except Exception as e:
        logger.error(f"Error sending callback to status update endpoint: {e}")
        traceback.print_exc()


def process_callback_background(
    file_path: str, encoded_results: str, session_id: int
) -> None:
    """Process the dataset generation callback: upload CSV to S3 and send status update."""
    try:
        logger.info(f"Starting processing for: {file_path}")

        # Extract dataset ID from file path (e.g., output_datasets/12.csv -> 12)
        dataset_id_match = re.search(r"/([^/]+)\.csv$", file_path)
        dataset_id = int(dataset_id_match.group(1)) if dataset_id_match else None
        if not dataset_id:
            logger.error("Could not extract dataset_id from file path.")
            raise ValueError("Invalid file path format, could not extract dataset_id.")

        logger.info(f"Extracted dataset ID: {dataset_id}")

        current_csv_path = file_path
        output_csv_path = f"{OUTPUT_DATA_DIR}/{dataset_id}_aggregated.csv"

        if dataset_id <= 1:
            logger.info("No previous dataset. Using current CSV only.")
            df = pd.read_csv(current_csv_path)
            df = update_item_ids(df, dataset_id)
            df = update_dataset_version_id(df, dataset_id)
            df.to_csv(output_csv_path, index=False)
        else:
            prev_dataset_id = dataset_id - 1
            prev_csv_local = f"{OUTPUT_DATA_DIR}/{prev_dataset_id}_prev.csv"
            prev_csv_s3_path = f"datasets/{prev_dataset_id}/{AGGREGATED_CSV_FILE}"
            logger.info(
                f"Attempting to download previous CSV from S3: {prev_csv_s3_path}"
            )
            try:
                response = s3_ferry_service.transfer_file(
                    destination_file_path=prev_csv_local.replace("/app/", ""),
                    destination_storage_type="FS",
                    source_file_path=prev_csv_s3_path,
                    source_storage_type="S3",
                )
                logger.info(f"S3 download status: {response.status_code}")
                if response.status_code in [200, 201] and os.path.exists(
                    prev_csv_local
                ):
                    logger.info(f"Previous CSV downloaded to {prev_csv_local}")
                    combine_csvs_and_update_ids(
                        prev_csv_local, current_csv_path, dataset_id, output_csv_path
                    )
                else:
                    logger.warning("Previous CSV not found in S3, using current only.")
                    df = pd.read_csv(current_csv_path)
                    df = update_item_ids(df, dataset_id)
                    df = update_dataset_version_id(df, dataset_id)
                    df.to_csv(output_csv_path, index=False)
            except Exception as e:
                logger.warning(
                    f"Failed to download previous CSV: {e}. Using current only."
                )
                df = pd.read_csv(current_csv_path)
                df = update_item_ids(df, dataset_id)
                df = update_dataset_version_id(df, dataset_id)
                df.to_csv(output_csv_path, index=False)

        notify_dataset_update(output_csv_path)
        upload_csv_to_s3(output_csv_path, dataset_id)
        send_status_update(dataset_id, encoded_results)

        logger.info("Processing completed successfully")
        notify_progress_uploading_to_s3(session_id)

    except Exception as e:
        logger.error(f"Error in processing: {str(e)}")
        traceback.print_exc()
        raise RuntimeError(f"Callback processing failed: {str(e)}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Process dataset generation callback")
    parser.add_argument(
        "--file-path", required=True, help="File path of the generated dataset CSV"
    )
    parser.add_argument(
        "--encoded-results", required=True, help="Encoded results string"
    )
    parser.add_argument("--output-json", help="Output JSON file path for response")
    parser.add_argument(
        "--session-id", required=True, help="Session ID for the callback"
    )
    return parser.parse_args()


def main():
    """Main function to handle callback processing."""
    args = parse_args()
    try:
        logger.info("Starting callback processing...")
        logger.info(f"File path: {args.file_path}")
        logger.info(f"Encoded results length: {len(args.encoded_results)} characters")

        process_callback_background(
            args.file_path, args.encoded_results, args.session_id
        )

        response = {
            "message": "Callback processing completed successfully",
            "status": "completed",
            "file_path": args.file_path,
        }

        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(response, f, indent=2)
            logger.info(f"Response written to: {args.output_json}")

        print(json.dumps(response))
        logger.info("Callback processing completed successfully")

    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        traceback.print_exc()
        error_response = {
            "message": f"Callback processing failed: {str(e)}",
            "status": "error",
            "file_path": args.file_path,
        }
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(error_response, f, indent=2)
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == "__main__":
    main()
