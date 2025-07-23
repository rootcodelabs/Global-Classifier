import requests
from loguru import logger
from constants import S3_FERRY_ENDPOINT

import sys

logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


class S3Ferry:
    def __init__(self):
        # Updated to use correct Docker service name
        self.url = S3_FERRY_ENDPOINT

    def transfer_file(
        self,
        destination_file_path,
        destination_storage_type,
        source_file_path,
        source_storage_type,
    ):
        payload = self.get_s3_ferry_payload(
            destination_file_path,
            destination_storage_type,
            source_file_path,
            source_storage_type,
        )

        response = requests.post(self.url, json=payload)
        return response

    def get_s3_ferry_payload(
        self,
        destination_file_path: str,
        destination_storage_type: str,
        source_file_path: str,
        source_storage_type: str,
    ):
        S3_FERRY_PAYLOAD = {
            "destinationFilePath": destination_file_path,
            "destinationStorageType": destination_storage_type,
            "sourceFilePath": source_file_path,
            "sourceStorageType": source_storage_type,
        }
        return S3_FERRY_PAYLOAD
