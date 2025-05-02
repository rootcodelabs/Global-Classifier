import os

# Status messages
UPLOAD_FAILED = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": ""
}

UPLOAD_SUCCESS = {
    "upload_status": 200,
    "operation_successful": True,
    "saved_file_path": ""
}

EXPORT_TYPE_ERROR = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": "export_type should be either json, xlsx or yaml."
}

IMPORT_TYPE_ERROR = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": "import_type should be either minor or major."
}

S3_UPLOAD_FAILED = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": "Failed to upload to S3"
}

S3_DOWNLOAD_FAILED = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": "Failed to download from S3"
}

DATASET_DELETION_SUCCESS = {
    "status_code": 200,
    "message": "Dataset deletion completed successfully.",
    "files_deleted": []
}

DATASET_DELETION_FAILED = {
    "status_code": 500,
    "message": "Dataset deletion failed.",
    "files_deleted": []
}

# File extensions
JSON_EXT = ".json"
YAML_EXT = ".yaml"
YML_EXT = ".yml"
XLSX_EXT = ".xlsx"

# S3 Ferry payload
def GET_S3_FERRY_PAYLOAD(destinationFilePath: str, destinationStorageType: str, sourceFilePath: str, sourceStorageType: str):
    return {
        "destinationFilePath": destinationFilePath,
        "destinationStorageType": destinationStorageType,
        "sourceFilePath": sourceFilePath,
        "sourceStorageType": sourceStorageType
    }

# Directories
UPLOAD_DIRECTORY = os.getenv("UPLOAD_DIRECTORY", "/shared")
CHUNK_UPLOAD_DIRECTORY = os.getenv("CHUNK_UPLOAD_DIRECTORY", "/shared/chunks")
JSON_FILE_DIRECTORY = os.path.join("..", "shared")
TEMP_COPY_FILE = "temp_copy.json"

# URLs
RUUTER_PRIVATE_URL = os.getenv("RUUTER_PRIVATE_URL")
S3_FERRY_URL = os.getenv("S3_FERRY_URL")
IMPORT_STOPWORDS_URL = os.getenv("IMPORT_STOPWORDS_URL")
DELETE_STOPWORDS_URL = os.getenv("DELETE_STOPWORDS_URL")
DATAGROUP_DELETE_CONFIRMATION_URL = os.getenv("DATAGROUP_DELETE_CONFIRMATION_URL")
DATAMODEL_DELETE_CONFIRMATION_URL = os.getenv("DATAMODEL_DELETE_CONFIRMATION_URL")
JIRA_ACTIVE_MODEL_DELETE_URL = os.getenv("JIRA_ACTIVE_MODEL_DELETE_URL")
OUTLOOK_ACTIVE_MODEL_DELETE_URL = os.getenv("OUTLOOK_ACTIVE_MODEL_DELETE_URL")
TEST_MODEL_DELETE_URL = os.getenv("TEST_MODEL_DELETE_URL")
MODEL_METADATA_DELETE_URL = os.getenv("MODEL_METADATA_DELETE_URL")
CORRECTED_TEXT_EXPORT = os.getenv("CORRECTED_TEXT_EXPORT")

# Dataset locations
TEMP_DATASET_LOCATION = "/dataset/{dg_id}/temp/temp_dataset.json"
PRIMARY_DATASET_LOCATION = "/dataset/{dg_id}/primary_dataset/dataset_{dg_id}_aggregated.json"
CHUNK_DATASET_LOCATION = "/dataset/{dg_id}/chunks/{chunk_id}.json"
NEW_DATASET_LOCATION = "/dataset/{new_dg_id}/"
