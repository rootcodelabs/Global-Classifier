import requests
from loguru import logger
from constants import TRAINING_LOGS_PATH

logger.add(sink=TRAINING_LOGS_PATH)

class S3Ferry:
    def __init__(self):
        self.url = "http://s3-ferry:3000/v1/files/copy"

    def transfer_file(self, destination_file_path, destination_storage_type, source_file_path, source_storage_type):
        payload = self.get_s3_ferry_payload(destination_file_path, destination_storage_type, source_file_path, source_storage_type)

        response = requests.post(self.url, json=payload)
        return response

    def get_s3_ferry_payload(self, destination_file_path:str, destination_storage_type:str, source_file_path:str, source_storage_type:str):
        S3_FERRY_PAYLOAD = {
                "destinationFilePath": destination_file_path,
                "destinationStorageType": destination_storage_type,
                "sourceFilePath": source_file_path,
                "sourceStorageType": source_storage_type
            }
        return S3_FERRY_PAYLOAD
