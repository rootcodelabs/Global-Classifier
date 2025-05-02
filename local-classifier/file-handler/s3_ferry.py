import requests
from constants import GET_S3_FERRY_PAYLOAD

class S3Ferry:
    def __init__(self, url):
        self.url = url

    def transfer_file(self, destinationFilePath, destinationStorageType, sourceFilePath, sourceStorageType):
        payload = GET_S3_FERRY_PAYLOAD(destinationFilePath, destinationStorageType, sourceFilePath, sourceStorageType)

        response = requests.post(self.url, json=payload)
        return response
