from pathlib import Path
import configparser
import os

# Service endpoints come from constants.ini (shared with Ruuter and the CronManager scripts).
_CONSTANTS_FILE = os.environ.get("CONSTANTS_FILE", "/app/constants.ini")
_config = configparser.ConfigParser(interpolation=None)
_config.optionxform = str
if not _config.read(_CONSTANTS_FILE):
    raise RuntimeError(f"Constants file not found: {_CONSTANTS_FILE}")
_dsl = _config["DSL"]


# --- Configuration ---
DATASET_UPDATE_URL = f"{_dsl['GLOBAL_CLASSIFIER_RUUTER_PUBLIC']}/datasets/update"
STATUS_UPDATE_URL = (
    f"{_dsl['GLOBAL_CLASSIFIER_RUUTER_PUBLIC']}/agencies/data/generation"
)
PROGRESS_UPDATE_URL = (
    f"{_dsl['GLOBAL_CLASSIFIER_RUUTER_PUBLIC']}/datasets/progress/update"
)
AGENCIES_IN_NETWORK_URL = f"{_dsl['GLOBAL_CLASSIFIER_RESQL']}/get-agencies-in-network"
LATEST_SUCCESSFUL_DATASET_URL = (
    f"{_dsl['GLOBAL_CLASSIFIER_RESQL']}/get-latest-successful-dataset-version"
)
GENERATION_STATUS_UPDATE_URL = (
    f"{_dsl['GLOBAL_CLASSIFIER_RESQL']}/update-data-generation-status"
)
SCRIPT_DIR = Path("/app/src/s3_dataset_processor")
AGGREGATED_CSV_FILE = "aggregated_dataset.csv"
SYNCED_WITH_CKB = "Synced_with_CKB"
SYNC_WITH_CKB_FAILED = "Sync_with_CKB_Failed"
OUTPUT_DATA_DIR = "/app/output_datasets"
DATA_DIRECTORY = "/app/data"

S3_FERRY_URL = _dsl["GLOBAL_CLASSIFIER_S3_FERRY"]
