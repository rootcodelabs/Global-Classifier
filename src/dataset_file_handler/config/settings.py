"""Application configuration settings."""

import os


class Settings:
    """Application settings and configuration."""

    # API Configuration
    API_TITLE = "S3 Dataset Processor API"
    API_DESCRIPTION = "API for decoding and processing S3 presigned URLs"
    API_VERSION = "1.0.0"

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
