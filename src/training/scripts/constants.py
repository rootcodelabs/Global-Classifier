# Constants
MODEL_CONFIG = {
    "bert": {
        "name": "bert-base-uncased",
        "max_length": 128,
    },
    "roberta": {
        "name": "roberta-base",
        "max_length": 128,
    },
    "xlm": {
        "name": "xlm-roberta-base",
        "max_length": 128,
    },
}
LOG_DIRECTORY = "/app/src/training/logs"
DATASETS_ARTIFACTS_DIR = "/app/src/training/dataset_artifacts"
MODELS_DIR = "/app/models"
TRAINING_DATASET_FOLDER_NAME = "training_datasets"
PROCESSED_DATASET_FOLDER_NAME = "processed_datasets"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOG_FILE_NAME = "train.log"
ROTATION_SIZE = "100 MB"
RETENTION_PERIOD = "10 days"
LOG_FILE_HANDLER_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)
SEED = 42  # For reproducibility
REQUIRED_TRAINING_FILES = ["train.json", "val.json", "test.json", "label_mappings.json"]
TEST_SIZE = 0.2  # Proportion of the dataset to include in the test split
VALIDATION_SIZE = 0.1  # Proportion of the dataset to include in the
RANDOM_STATE = 42  # Random state for reproducibility in train-test split
PROCESSED_DATASET_DIR = "/app/src/training/dataset_artifacts/processed_datasets"
S3_FERRY_BASE_URL = "http://gc-s3-ferry:3000"
TRAINING_JOB_STATUS_UPDATE_URL = (
    "http://resql:8082/global-classifier/update-training-job-status"
)
DATA_MODEL_TRAINING_UPDATE_URL = (
    "http://localhost:8088/global-classifier/datamodels/update-training"
)
