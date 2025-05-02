import requests
from utils import get_s3_payload
from loguru import logger
from constants  import INFERENCE_LOGS_PATH

logger.add(sink=INFERENCE_LOGS_PATH)

class S3Ferry:
    def __init__(self, url):
        self.url = url

    def transfer_file(self, destination_file_path, destination_storage_type, source_file_path, source_storage_type):
        
        logger.info("Transfer File Method Calling")
        logger.info(f"Destination Path :{destination_file_path}")
        logger.info(f"Destination Storage  :{destination_storage_type}")
        logger.info(f"Source File Path :{source_file_path}")
        logger.info(f"Source Storage Type :{source_storage_type}")

        payload = get_s3_payload(destination_file_path, destination_storage_type, source_file_path, source_storage_type)
        logger.info(payload)
        logger.info(f"url : {self.url}")
        response = requests.post(self.url, json=payload)
        logger.info(f"RESPONSE STATUS CODE INSIDE TRANSFER FILE - {response.status_code}")

        return response
