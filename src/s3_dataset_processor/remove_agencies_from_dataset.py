#!/usr/bin/env python3
"""
Standalone script that creates a dataset version without the agencies that left the network.
Copies the previous successful version's aggregated CSV, drops those agencies' rows,
saves the result as the new version and sets its generation status.
"""

import sys
import argparse
import logging
import os
import requests
import traceback
import pandas as pd
from constants import (
    AGGREGATED_CSV_FILE,
    GENERATION_STATUS_UPDATE_URL,
    OUTPUT_DATA_DIR,
)
from dataset_generation_callback_processor import (
    notify_dataset_update,
    s3_ferry_service,
    update_dataset_version_id,
    update_item_ids,
    upload_csv_to_s3,
)

logger = logging.getLogger(__name__)


def download_previous_csv(previous_dataset_id: int) -> str:
    """Download the previous version's aggregated CSV from S3 and return its local path."""
    local_path = f"{OUTPUT_DATA_DIR}/{previous_dataset_id}_prev.csv"
    s3_path = f"datasets/{previous_dataset_id}/{AGGREGATED_CSV_FILE}"
    logger.info(f"Downloading previous CSV from S3: {s3_path}")
    response = s3_ferry_service.transfer_file(
        destination_file_path=local_path.replace("/app/", ""),
        destination_storage_type="FS",
        source_file_path=s3_path,
        source_storage_type="S3",
    )
    if response.status_code not in [200, 201] or not os.path.exists(local_path):
        raise RuntimeError(
            f"Previous CSV for version {previous_dataset_id} could not be downloaded"
        )
    return local_path


def remove_agencies(
    prev_csv_path: str, agency_ids: set, dataset_id: int, output_path: str
) -> int:
    """Drop the given agencies' rows, renumber for the new version and save. Returns rows removed."""
    df = pd.read_csv(prev_csv_path, dtype={"agency_id": str})
    filtered_df = df[~df["agency_id"].isin(agency_ids)]
    filtered_df = update_item_ids(filtered_df, dataset_id)
    filtered_df = update_dataset_version_id(filtered_df, dataset_id)
    filtered_df.to_csv(output_path, index=False)
    return len(df) - len(filtered_df)


def set_generation_status(dataset_id: int, generation_status: str) -> None:
    """Set dataset_versions.generation_status for the new version."""
    response = requests.post(
        GENERATION_STATUS_UPDATE_URL,
        json={"datasetId": str(dataset_id), "generationStatus": generation_status},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if response.status_code not in [200, 201]:
        raise RuntimeError(f"Failed to set generation status: {response.text}")
    logger.info(f"Dataset version {dataset_id} set to {generation_status}")


def remove_agencies_from_dataset(
    dataset_id: int, previous_dataset_id: int, agency_ids: set
) -> None:
    """Create the new version from the previous one without the given agencies."""
    prev_csv_path = None
    output_path = f"{OUTPUT_DATA_DIR}/{dataset_id}_aggregated.csv"
    try:
        prev_csv_path = download_previous_csv(previous_dataset_id)
        removed = remove_agencies(prev_csv_path, agency_ids, dataset_id, output_path)
        logger.info(
            f"Removed {removed} rows of {len(agency_ids)} agencies "
            f"from version {previous_dataset_id}"
        )
        notify_dataset_update(output_path)
        upload_csv_to_s3(output_path, dataset_id)
        set_generation_status(dataset_id, "Generation_Success")
    except Exception:
        set_generation_status(dataset_id, "Generation_Failed")
        raise
    finally:
        for path in [prev_csv_path, output_path]:
            if path and os.path.exists(path):
                os.remove(path)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create a dataset version without agencies that left the network"
    )
    parser.add_argument(
        "--dataset-id", required=True, type=int, help="ID of the new dataset version"
    )
    parser.add_argument(
        "--previous-dataset-id",
        required=True,
        type=int,
        help="ID of the latest successful dataset version to copy from",
    )
    parser.add_argument(
        "--agency-ids", required=True, help="Comma-separated agency IDs to remove"
    )
    return parser.parse_args()


def main():
    """Main function to create the dataset version."""
    args = parse_args()
    agency_ids = {agency_id for agency_id in args.agency_ids.split(",") if agency_id}
    try:
        logger.info(
            f"Creating dataset version {args.dataset_id} from version "
            f"{args.previous_dataset_id} without {len(agency_ids)} agencies"
        )
        remove_agencies_from_dataset(
            args.dataset_id, args.previous_dataset_id, agency_ids
        )
        logger.info("Dataset version created successfully")
    except Exception as e:
        logger.error(f"Error creating dataset version: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
