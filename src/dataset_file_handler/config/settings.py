"""Application configuration settings."""

import os
import configparser

# Service endpoints come from constants.ini (shared with Ruuter and the CronManager scripts).
_CONSTANTS_FILE = os.environ.get("CONSTANTS_FILE", "/app/constants.ini")
_config = configparser.ConfigParser(interpolation=None)
_config.optionxform = str
if not _config.read(_CONSTANTS_FILE):
    raise RuntimeError(f"Constants file not found: {_CONSTANTS_FILE}")
_dsl = _config["DSL"]


class Settings:
    """Application settings and configuration."""

    # API Configuration
    API_TITLE = "S3 Dataset Processor API"
    API_DESCRIPTION = "API for decoding and processing S3 presigned URLs"
    API_VERSION = "1.0.0"

    # Service endpoints
    S3_FERRY_URL = _dsl["GLOBAL_CLASSIFIER_S3_FERRY"]

    # Directory Configuration
    DATA_DIR = "/app/data"

    # Download Configuration
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    CHUNK_SIZE = 8192

    def __init__(self):
        """Initialize settings and create necessary directories."""
        os.makedirs(self.DATA_DIR, exist_ok=True)


# Global settings instance
settings = Settings()
