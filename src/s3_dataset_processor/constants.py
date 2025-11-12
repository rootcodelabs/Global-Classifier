from pathlib import Path

# --- Configuration ---
DATASET_UPDATE_URL = "http://ruuter-public:8086/global-classifier/datasets/update"
STATUS_UPDATE_URL = (
    "http://ruuter-public:8086/global-classifier/agencies/data/generation"
)
PROGRESS_UPDATE_URL = (
    "http://ruuter-public:8086/global-classifier/datasets/progress/update"
)
SCRIPT_DIR = Path("/app/src/s3_dataset_processor")
AGGREGATED_CSV_FILE = "aggregated_dataset.csv"
SYNCED_WITH_CKB = "Synced_with_CKB"
SYNC_WITH_CKB_FAILED = "Sync_with_CKB_Failed"
OUTPUT_DATA_DIR = "/app/output_datasets"
DATA_DIRECTORY = "/app/data"
