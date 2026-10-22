import configparser
import os

# Service endpoints come from constants.ini (shared with Ruuter and the CronManager scripts).
_CONSTANTS_FILE = os.environ.get("CONSTANTS_FILE", "/app/constants.ini")
_config = configparser.ConfigParser(interpolation=None)
_config.optionxform = str
if not _config.read(_CONSTANTS_FILE):
    raise RuntimeError(f"Constants file not found: {_CONSTANTS_FILE}")
_dsl = _config["DSL"]


DATA_URL_INSERT_URL = f"{_dsl['GLOBAL_CLASSIFIER_RESQL']}/insert-agency-presigned-url"
DATA_URL_UPDATE_URL = f"{_dsl['GLOBAL_CLASSIFIER_RESQL']}/update-agency-presigned-url"
MINIO_ENDPOINT = _dsl["GLOBAL_CLASSIFIER_MINIO"]
MINIO_USER_ID = "minioadmin"
MINIO_USER_KEY = "minioadmin"
REGION_NAME = "us-east-1"
SIGNATURE_VERSION = "s3v4"
BUCKET_NAME = "ckb"
