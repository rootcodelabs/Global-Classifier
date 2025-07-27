#!/usr/bin/env python3
"""
Global Classifier Model Deployment Script
This script handles model deployment using S3-Ferry service
"""

# Importing required default libraries
import argparse
import configparser
import sys
import zipfile
import shutil
from pathlib import Path

import requests
from loguru import logger

# Configure loguru logging
logger.add("deployment_logs.log", level="DEBUG", rotation="10 MB")
logger.add(sys.stderr, level="INFO")

CONSTANTS_INI_FILE_PATH = "/app/inference_scripts/constants.ini"

def read_constants_ini(constants_file_path: str = CONSTANTS_INI_FILE_PATH) -> dict:
    """Read configuration values from constants.ini file"""
    config = configparser.ConfigParser()

    try:
        logger.debug(f"Reading constants from {constants_file_path}")
        config.read(constants_file_path)
    except Exception as e:
        logger.error(f"Error reading constants file {constants_file_path}: {e}")
        sys.exit(1)

    # Check if file was actually read (configparser.read() doesn't raise exception for missing files)
    if not config.sections():
        logger.error(f"Constants file {constants_file_path} not found or is empty")
        sys.exit(1)

    if "DSL" not in config:
        logger.error(f"No [DSL] section found in {constants_file_path}")
        sys.exit(1)

    dsl_section = config["DSL"]

    # Required configuration keys
    required_keys = [
        "GLOBAL_CLASSIFIER_S3_FERRY",
        "GLOBAL_CLASSIFIER_RUUTER_PRIVATE",
        "GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER",
        "GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER",
    ]

    logger.debug(f"Loaded DSL section: {[constant for constant in dsl_section]}")

    # Check if all required keys exist
    missing_keys = [key for key in required_keys if key not in dsl_section]
    if missing_keys:
        logger.error(
            f"Missing required configuration keys in {constants_file_path}: {missing_keys}"
        )
        sys.exit(1)

    constants = {
        "s3_ferry_url": dsl_section.get("GLOBAL_CLASSIFIER_S3_FERRY"),
        "ruuter_private_url": dsl_section.get("GLOBAL_CLASSIFIER_RUUTER_PRIVATE"),
        "triton_test_url": dsl_section.get(
            "GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER"
        ),
        "triton_prod_url": dsl_section.get(
            "GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER"
        ),
    }

    logger.info(f"Successfully loaded constants from {constants_file_path}")
    return constants


class ModelDeploymentOrchestrator:
    """Handles model deployment operations using S3-Ferry service"""

    def __init__(
        self,
        s3_ferry_url: str,
        ruuter_private_url: str,
        triton_test_url: str,
        triton_prod_url: str,
        model_id: str,
        current_env: str,
        target_env: str,
        first_deployment: bool = False,
    ):
        """Initialize the ModelDeployer with configuration

        Args:
            s3_ferry_url: URL for S3-Ferry service
            ruuter_private_url: URL for Ruuter private service
            triton_test_url: URL for Triton testing environment
            triton_prod_url: URL for Triton production environment
            model_id: ID of the model to deploy
            current_env: Current environment (e.g., 'undeployed')
            target_env: Target environment (e.g., 'testing', 'production')
            first_deployment: Whether this is the first deployment
        """
        self.s3_ferry_url = s3_ferry_url
        self.ruuter_private_url = ruuter_private_url
        self.triton_test_url = triton_test_url
        self.triton_prod_url = triton_prod_url
        self.model_id = model_id
        self.current_env = current_env
        self.target_env = target_env
        self.first_deployment = first_deployment

        # Set up directories based on model_id
        self.extract_dir = Path(
            f"/app/data/temp_extracted_models/model_id_{self.model_id}"
        )

        # S3 Ferry local file path same as above with /app removed since s3 Ferry already adds this from config
        self.s3_ferry_local_download_path = (
            f"data/temp_extracted_models/model_id_{self.model_id}"
        )

        # Define model files to upload
        self.model_files = [
            f"{self.model_id}-classifier-ensemble/config.pbtxt",
            f"{self.model_id}-pre-processing/config.pbtxt",
            f"{self.model_id}-pre-processing/1/model.py",
            f"{self.model_id}-pre-processing/1/label_mappings.json",
            f"{self.model_id}-post-processing/config.pbtxt",
            f"{self.model_id}-post-processing/1/model.py",
            f"{self.model_id}-post-processing/1/label_mappings.json",
            f"{self.model_id}-text-classifier/config.pbtxt",
            f"{self.model_id}-text-classifier/1/model.onnx",
        ]

    def log_message(self, message: str, level: str = "INFO"):
        """Log a message using loguru"""
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "DEBUG":
            logger.debug(message)
        else:
            logger.info(message)

    def log_error(self, message: str):
        """Log an error message"""
        logger.error(message)

    def call_s3_ferry(
        self, source_path: str, source_type: str, dest_path: str, dest_type: str
    ) -> bool:
        """Call S3-Ferry API for file transfer"""
        payload = {
            "sourceFilePath": source_path,
            "sourceStorageType": source_type,
            "destinationFilePath": dest_path,
            "destinationStorageType": dest_type,
        }

        self.log_message(
            f"S3-Ferry transfer: {source_path} ({source_type}) -> {dest_path} ({dest_type})"
        )

        try:
            # Make the request with timeout
            response = requests.post(
                f"{self.s3_ferry_url}/v1/files/copy",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300,
            )

            if response.status_code in [200, 201]:
                self.log_message(
                    f"S3-Ferry transfer successful (HTTP {response.status_code})"
                )
                return True
            else:
                self.log_error(
                    f"S3-Ferry transfer failed (HTTP {response.status_code}): {response.text}"
                )
                return False

        except requests.exceptions.HTTPError as e:
            self.log_error(f"S3-Ferry HTTP error: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            self.log_error(f"S3-Ferry connection error: {e}")
            return False
        except requests.exceptions.Timeout as e:
            self.log_error(f"S3-Ferry timeout error: {e}")
            return False
        except requests.exceptions.RequestException as e:
            self.log_error(f"S3-Ferry API call failed: {e}")
            return False
        except Exception as e:
            self.log_error(f"Unexpected error during S3-Ferry call: {e}")
            return False

    def create_working_directory(self):
        """Create the working directory for model extraction"""
        try:
            self.extract_dir.mkdir(parents=True, exist_ok=True)
            self.log_message(f"Created working directory: {self.extract_dir}")
            self.log_message(
                f"Path sent to S3 Ferry: {self.s3_ferry_local_download_path}"
            )
        except OSError as e:
            self.log_error(f"Failed to create working directory: {e}")
            sys.exit(1)

    def download_model_from_undeployed(self) -> str:
        """Download the model zip file from undeployed bucket"""
        self.log_message("Step 1: Downloading model from undeployed bucket...")

        model_zip_name = f"{self.model_id}.zip"
        local_zip_path = f"{self.s3_ferry_local_download_path}/{model_zip_name}"
        s3_source_path = f"models/undeployed/{model_zip_name}"

        self.log_message(f"MODEL S3 LOCATION - {s3_source_path}")
        self.log_message(f"MODEL LOCAL PATH - {local_zip_path}")

        if not self.call_s3_ferry(s3_source_path, "S3", local_zip_path, "FS"):
            self.log_error("Failed to download model from undeployed bucket")
            sys.exit(1)

        return local_zip_path

    def verify_and_extract_model(self, local_zip_path: str):
        """Verify the zip file was downloaded and extract it"""
        full_zip_path = Path(f"/app/{local_zip_path}")

        # Verify the zip file was downloaded
        if not full_zip_path.exists():
            self.log_error(f"Model zip file not found at {full_zip_path}")
            sys.exit(1)

        try:
            # Get file size for logging
            file_size = full_zip_path.stat().st_size
            self.log_message(
                f"Model zip file downloaded successfully: {file_size} bytes"
            )
        except OSError as e:
            self.log_error(f"Could not get file stats: {e}")

        # Extract model files
        self.log_message("Step 2: Extracting model files...")
        try:
            with zipfile.ZipFile(full_zip_path, "r") as zip_ref:
                zip_ref.extractall(self.extract_dir)
            self.log_message("Model files extracted successfully")
        except (zipfile.BadZipFile, OSError) as e:
            self.log_error(f"Failed to extract model zip file: {e}")
            sys.exit(1)

    def upload_model_files(self, environment: str, s3_base_path: str) -> bool:
        """Upload files to specified environment"""
        self.log_message(f"Uploading model files to {environment} environment...")

        for file in self.model_files:
            local_file_path = f"{self.s3_ferry_local_download_path}/{file}"
            s3_dest_path = f"{s3_base_path}/{file}"

            if not self.call_s3_ferry(local_file_path, "FS", s3_dest_path, "S3"):
                self.log_error(f"Failed to upload {file} to {environment} environment")
                return False

        self.log_message(
            f"Successfully uploaded all files to {environment} environment"
        )
        return True

    def upload_to_model_repository(self):
        """Upload model files to both testing and production repositories"""
        self.log_message("Step 3: Uploading model files to model repository...")

        # Define S3 destination base paths
        s3_testing_base = f"models/testing/modelId-{self.model_id}"
        s3_production_base = f"models/production/modelId-{self.model_id}"

        # Upload to testing environment
        if not self.upload_model_files("testing", s3_testing_base):
            self.log_error("Failed to upload model to testing environment")
            sys.exit(1)

        # Upload to production environment
        if not self.upload_model_files("production", s3_production_base):
            self.log_error("Failed to upload model to production environment")
            sys.exit(1)

    def cleanup_temp_files(self) -> None:
        """Clean up temporary files and directories"""
        try:
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                self.log_message(f"Cleaned up temporary directory: {self.extract_dir}")
        except OSError as e:
            self.log_error(f"Failed to clean up temporary files: {e}")

    def load_model_to_repository(self):
        """Main deployment process"""
        try:
            self.log_message(
                f"Starting deployment for model ID: {self.model_id} from {self.current_env} to {self.target_env}"
            )

            # Create working directory
            self.create_working_directory()

            # Download model from undeployed bucket
            local_zip_path = self.download_model_from_undeployed()

            # Verify and extract model
            self.verify_and_extract_model(local_zip_path)

            # Upload to model repository
            self.upload_to_model_repository()

            self.log_message(
                "Model deployment completed successfully for both environments"
            )

        except KeyboardInterrupt:
            self.log_error("Deployment interrupted by user")
            sys.exit(1)
        except Exception as e:
            self.log_error(f"Unexpected error during deployment: {e}")
            sys.exit(1)
        finally:
            # Always attempt cleanup
            self.cleanup_temp_files()


def main():
    """Main entry point"""
    # Read constants from ini file
    constants = read_constants_ini()

    parser = argparse.ArgumentParser(
        description="Deploy Global Classifier models using S3-Ferry service"
    )

    # Required arguments
    parser.add_argument("--model-id", required=True, help="ID of the model to deploy")
    parser.add_argument(
        "--current-env", required=True, help="Current environment (e.g., 'undeployed')"
    )
    parser.add_argument(
        "--target-env",
        required=True,
        help="Target environment (e.g., 'testing', 'production')",
    )
    parser.add_argument(
        "--first-deployment",
        required=True,
        choices=["true", "false"],
        help="Whether this is the first deployment (true/false)",
    )

    # Optional arguments with default values from constants.ini
    parser.add_argument(
        "--s3-ferry-url",
        default=constants["s3_ferry_url"],
        help=f"URL for S3-Ferry service (default: {constants['s3_ferry_url']})",
    )
    parser.add_argument(
        "--ruuter-private-url",
        default=constants["ruuter_private_url"],
        help=f"URL for Ruuter private service (default: {constants['ruuter_private_url']})",
    )
    parser.add_argument(
        "--triton-test-url",
        default=constants["triton_test_url"],
        help=f"URL for Triton testing environment (default: {constants['triton_test_url']})",
    )
    parser.add_argument(
        "--triton-prod-url",
        default=constants["triton_prod_url"],
        help=f"URL for Triton production environment (default: {constants['triton_prod_url']})",
    )

    args = parser.parse_args()

    # Log all passed arguments for debugging
    logger.info(f"Starting deployment with arguments: {vars(args)}")

    try:
        deployer = ModelDeploymentOrchestrator(
            s3_ferry_url=args.s3_ferry_url,
            ruuter_private_url=args.ruuter_private_url,
            triton_test_url=args.triton_test_url,
            triton_prod_url=args.triton_prod_url,
            model_id=args.model_id,
            current_env=args.current_env,
            target_env=args.target_env,
            first_deployment=args.first_deployment.lower() == "true",
        )
        deployer.load_model_to_repository()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
