from pathlib import Path

# --- Configuration ---
DATASET_UPDATE_URL = "http://ruuter-public:8086/global-classifier/datasets/update"
STATUS_UPDATE_URL = (
    "http://ruuter-public:8086/global-classifier/agencies/data/generation"
)
PROGRESS_UPDATE_URL = (
    "http://ruuter-public:8086/global-classifier/datasets/progress/update"
)
AGENCIES_IN_NETWORK_URL = "http://resql:8082/global-classifier/get-agencies-in-network"
LATEST_SUCCESSFUL_DATASET_URL = (
    "http://resql:8082/global-classifier/get-latest-successful-dataset-version"
)
GENERATION_STATUS_UPDATE_URL = (
    "http://resql:8082/global-classifier/update-data-generation-status"
)
SCRIPT_DIR = Path("/app/src/s3_dataset_processor")
AGGREGATED_CSV_FILE = "aggregated_dataset.csv"
SYNCED_WITH_CKB = "Synced_with_CKB"
SYNC_WITH_CKB_FAILED = "Sync_with_CKB_Failed"
OUTPUT_DATA_DIR = "/app/output_datasets"
DATA_DIRECTORY = "/app/data"
