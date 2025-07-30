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
from loki_logger import LokiLogger

CONSTANTS_INI_FILE_PATH = "/app/inference_scripts/constants.ini"

# Initialize global logger instance with service name
logger = LokiLogger(service_name="model-deployment-orchestrator")


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
        first_deployment: bool,
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
            f"{self.model_id}-classifier-ensemble/1/README.txt",
            f"{self.model_id}-pre-processing/config.pbtxt",
            f"{self.model_id}-pre-processing/1/model.py",
            f"{self.model_id}-pre-processing/1/label_mappings.json",
            f"{self.model_id}-post-processing/config.pbtxt",
            f"{self.model_id}-post-processing/1/model.py",
            f"{self.model_id}-post-processing/1/label_mappings.json",
            f"{self.model_id}-text-classifier/config.pbtxt",
            f"{self.model_id}-text-classifier/1/model.onnx",
        ]

    def log_message(self, message: str, level: str = "INFO", **extra_fields):
        """Log a message using Loki API with optional extra fields"""
        # Add model context to all logs
        context = {
            "model_id": self.model_id,
            "current_env": self.current_env,
            "target_env": self.target_env,
            "first_deployment": str(self.first_deployment),
            **extra_fields,
        }

        # Send log to appropriate level
        if level == "ERROR":
            logger.error(message, **context)
        elif level == "WARNING":
            logger.warning(message, **context)
        elif level == "DEBUG":
            logger.debug(message, **context)
        else:
            logger.info(message, **context)

    def log_error(self, message: str, **extra_fields):
        """Log an error message with context"""
        self.log_message(message, "ERROR", **extra_fields)

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
        s3_testing_base = "models/testing"
        s3_production_base = "models/production"

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

    def get_triton_server_url(self, environment: str) -> str:
        """Get the appropriate Triton server URL for the environment"""
        if environment == "testing":
            return self.triton_test_url
        elif environment == "production":
            return self.triton_prod_url
        else:
            raise ValueError(f"Invalid environment: {environment}")

    def get_ensemble_model_names(self) -> list:
        """Get all model names for the ensemble (including sub-models)"""
        return [
            f"{self.model_id}-classifier-ensemble",
            f"{self.model_id}-pre-processing",
            f"{self.model_id}-post-processing",
            f"{self.model_id}-text-classifier",
        ]

    def check_server_health(self, server_url: str) -> bool:
        """Check if Triton server is healthy and ready"""
        try:
            # Check server liveness
            live_response = requests.get(f"{server_url}/v2/health/live", timeout=10)
            if live_response.status_code != 200:
                self.log_error(f"Server not live at {server_url}")
                return False

            # Check server readiness
            ready_response = requests.get(f"{server_url}/v2/health/ready", timeout=10)
            if ready_response.status_code != 200:
                self.log_error(f"Server not ready at {server_url}")
                return False

            self.log_message(f"Server healthy and ready at {server_url}")
            return True

        except requests.exceptions.RequestException as e:
            self.log_error(f"Health check failed for {server_url}: {e}")
            return False

    def load_model_to_triton(self, server_url: str, model_name: str) -> bool:
        """Load a model to Triton server"""
        try:
            self.log_message(f"Loading model {model_name} to {server_url}")

            response = requests.post(
                f"{server_url}/v2/repository/models/{model_name}/load"
            )

            if response.status_code in [200, 201]:
                self.log_message(f"Successfully loaded model {model_name}")
                return True
            else:
                self.log_error(
                    f"Failed to load model {model_name}: HTTP {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error loading model {model_name}: {e}")
            return False

    def unload_model_from_triton(
        self, server_url: str, model_name: str, unload_dependents: bool = False
    ) -> bool:
        """Unload a model from Triton server"""
        try:
            self.log_message(f"Unloading model {model_name} from {server_url}")

            payload = {}
            if unload_dependents:
                payload["unload_dependents"] = True

            response = requests.post(
                f"{server_url}/v2/repository/models/{model_name}/unload",
                json=payload if payload else None,
                timeout=60,
            )

            if response.status_code in [200, 201]:
                self.log_message(f"Successfully unloaded model {model_name}")
                return True
            else:
                self.log_error(
                    f"Failed to unload model {model_name}: HTTP {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error unloading model {model_name}: {e}")
            return False

    def get_loaded_models(self, server_url: str) -> list:
        """Get list of currently loaded models from Triton server"""
        try:
            # Use repository index endpoint with ready=true to get only loaded models
            payload = {"ready": True}
            response = requests.post(
                f"{server_url}/v2/repository/index", json=payload, timeout=30
            )

            if response.status_code == 200:
                models_data = response.json()
                loaded_models = []

                # The response is an array of model objects
                for model in models_data:
                    if model.get("state") == "READY":
                        loaded_models.append(model.get("name"))

                return loaded_models
            else:
                self.log_error(
                    f"Failed to get models list: HTTP {response.status_code}"
                )
                return []

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error getting models list: {e}")
            return []

    def test_model_inference(
        self, server_url: str, max_retries: int = 10, retry_delay: int = 5
    ) -> bool:
        """Test if the ensemble model can perform inference"""
        ensemble_model_name = f"{self.model_id}-classifier-ensemble"

        # Simple test input for text classification
        test_payload = {
            "inputs": [
                {
                    "name": "TEXT",
                    "datatype": "BYTES",
                    "shape": [1, 1],
                    "data": ["This is a test message for classification."],
                }
            ]
        }

        for attempt in range(max_retries):
            try:
                self.log_message(
                    f"Testing inference for {ensemble_model_name} (attempt {attempt + 1}/{max_retries})"
                )

                response = requests.post(
                    f"{server_url}/v2/models/{ensemble_model_name}/infer",
                    json=test_payload,
                    timeout=30,
                )

                if response.status_code == 200:
                    self.log_message(
                        f"Inference test successful for {ensemble_model_name}"
                    )
                    return True
                else:
                    self.log_error(
                        f"Inference test failed: HTTP {response.status_code} - {response.text}"
                    )

            except requests.exceptions.RequestException as e:
                self.log_error(f"Inference test error (attempt {attempt + 1}): {e}")

            if attempt < max_retries - 1:
                self.log_message(f"Waiting {retry_delay} seconds before retry...")
                import time

                time.sleep(retry_delay)

        self.log_error(f"Inference test failed after {max_retries} attempts")
        return False

    def unload_existing_models(self, server_url: str) -> bool:
        """Unload any existing models with the same model ID"""
        model_names = self.get_ensemble_model_names()
        loaded_models = self.get_loaded_models(server_url)

        models_to_unload = [
            model
            for model in loaded_models
            if any(model.startswith(f"{self.model_id}-") for model in model_names)
        ]

        if not models_to_unload:
            self.log_message("No existing models to unload")
            return True

        self.log_message(f"Found existing models to unload: {models_to_unload}")

        # Unload ensemble first (with dependents) to avoid conflicts
        ensemble_name = f"{self.model_id}-classifier-ensemble"
        if ensemble_name in models_to_unload:
            if not self.unload_model_from_triton(
                server_url, ensemble_name, unload_dependents=True
            ):
                return False
            models_to_unload.remove(ensemble_name)

        # Unload remaining individual models
        for model_name in models_to_unload:
            if not self.unload_model_from_triton(server_url, model_name):
                return False

        return True

    def load_ensemble_models(self, server_url: str) -> bool:
        """Load all models for the ensemble in the correct order"""
        model_names = self.get_ensemble_model_names()

        # Load individual models first (dependencies)
        individual_models = [
            name for name in model_names if not name.endswith("-classifier-ensemble")
        ]
        ensemble_model = f"{self.model_id}-classifier-ensemble"

        # Load individual models first
        for model_name in individual_models:
            if not self.load_model_to_triton(server_url, model_name):
                self.log_error(f"Failed to load dependency model {model_name}")
                return False

        # Load ensemble model last
        if not self.load_model_to_triton(server_url, ensemble_model):
            self.log_error(f"Failed to load ensemble model {ensemble_model}")
            return False

        return True

    def deploy_model(self) -> bool:
        """
        Deploy model based on current and target environments.

        Returns:
            bool: True if deployment was successful, False otherwise
        """
        self.log_message(
            f"Starting model deployment from {self.current_env} to {self.target_env}"
        )

        # Case 1: undeployed -> undeployed (no-op)
        if self.current_env == "undeployed" and self.target_env == "undeployed":
            self.log_message(
                "Both current and target environments are 'undeployed'. No deployment needed."
            )
            return True

        # Case 2: testing -> production
        elif self.current_env == "testing" and self.target_env == "production":
            self.log_message("Deploying from testing to production")

            # Check production server health
            prod_url = self.get_triton_server_url("production")
            if not self.check_server_health(prod_url):
                self.log_error("Production server health check failed")
                return False

            # Unload existing models in production
            if not self.unload_existing_models(prod_url):
                self.log_error("Failed to unload existing models from production")
                return False

            # Load models to production
            if not self.load_ensemble_models(prod_url):
                self.log_error("Failed to load models to production")
                return False

            # Test inference
            if not self.test_model_inference(prod_url):
                self.log_error("Production inference test failed")
                return False

            self.log_message("Successfully deployed model from testing to production")
            return True

        # Case 3: testing -> undeployed
        elif self.current_env == "testing" and self.target_env == "undeployed":
            self.log_message("Undeploying model from testing")

            test_url = self.get_triton_server_url("testing")
            if not self.check_server_health(test_url):
                self.log_error("Testing server health check failed")
                return False

            # Unload models from testing
            if not self.unload_existing_models(test_url):
                self.log_error("Failed to unload models from testing")
                return False

            self.log_message("Successfully undeployed model from testing")
            return True

        # Case 4: production -> testing
        elif self.current_env == "production" and self.target_env == "testing":
            self.log_message("Moving model from production to testing")

            # Unload from production
            prod_url = self.get_triton_server_url("production")
            if not self.check_server_health(prod_url):
                self.log_error("Production server health check failed")
                return False

            if not self.unload_existing_models(prod_url):
                self.log_error("Failed to unload models from production")
                return False

            # Load to testing
            test_url = self.get_triton_server_url("testing")
            if not self.check_server_health(test_url):
                self.log_error("Testing server health check failed")
                return False

            if not self.unload_existing_models(test_url):
                self.log_error("Failed to unload existing models from testing")
                return False

            if not self.load_ensemble_models(test_url):
                self.log_error("Failed to load models to testing")
                return False

            if not self.test_model_inference(test_url):
                self.log_error("Testing inference test failed")
                return False

            self.log_message("Successfully moved model from production to testing")
            return True

        # Case 5: undeployed -> testing
        elif self.current_env == "undeployed" and self.target_env == "testing":
            self.log_message("Deploying model to testing")

            test_url = self.get_triton_server_url("testing")
            if not self.check_server_health(test_url):
                self.log_error("Testing server health check failed")
                return False

            if not self.unload_existing_models(test_url):
                self.log_error("Failed to unload existing models from testing")
                return False

            if not self.load_ensemble_models(test_url):
                self.log_error("Failed to load models to testing")
                return False

            if not self.test_model_inference(test_url):
                self.log_error("Testing inference test failed")
                return False

            self.log_message("Successfully deployed model to testing")
            return True

        # Case 6: undeployed -> production
        elif self.current_env == "undeployed" and self.target_env == "production":
            self.log_message("Deploying model directly to production")

            prod_url = self.get_triton_server_url("production")
            if not self.check_server_health(prod_url):
                self.log_error("Production server health check failed")
                return False

            if not self.unload_existing_models(prod_url):
                self.log_error("Failed to unload existing models from production")
                return False

            if not self.load_ensemble_models(prod_url):
                self.log_error("Failed to load models to production")
                return False

            if not self.test_model_inference(prod_url):
                self.log_error("Production inference test failed")
                return False

            self.log_message("Successfully deployed model directly to production")
            return True

        # Invalid case
        else:
            self.log_error(
                f"Invalid deployment path: {self.current_env} -> {self.target_env}"
            )
            return False

    def load_model_to_repository(self):
        """Main model repository upload process"""
        try:
            self.log_message(f"Starting model upload for model ID: {self.model_id}")

            # Step 1: Create working directory
            self.create_working_directory()

            # Step 2: Download model from undeployed bucket
            local_zip_path = self.download_model_from_undeployed()

            # Step 3: Verify and extract model
            self.verify_and_extract_model(local_zip_path)

            # Step 4: Upload to model repository
            self.upload_to_model_repository()

            self.log_message("Model files uploaded successfully to both environments")

        except KeyboardInterrupt:
            self.log_error("Model upload interrupted by user")
            sys.exit(1)
        except Exception as e:
            self.log_error(f"Unexpected error during model upload: {e}")
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
        help="Whether this is the first deployment",
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

    try:
        args = parser.parse_args()
    except SystemExit as e:
        logger.error(
            f"Argument parsing failed with error arparse error code: {e} - Check the INFO logs for more details."
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during argument parsing error code: {e}  - Check the INFO logs for more details."
        )
        raise

    # Log all passed arguments for debugging
    logger.info(
        f"Starting deployment with arguments: {vars(args)}", model_id=args.model_id
    )

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

        # Step 1: Upload model files to repository (only on first deployment)
        if args.first_deployment.lower() == "true":
            logger.info(
                "First deployment detected - uploading model files to repository",
                model_id=args.model_id,
            )
            deployer.load_model_to_repository()
        else:
            logger.info(
                "Not a first deployment - skipping model repository upload",
                model_id=args.model_id,
            )

        # Step 2: Deploy model to Triton inference servers
        if not deployer.deploy_model():
            logger.error(
                "Model deployment to Triton servers failed", model_id=args.model_id
            )
            sys.exit(1)

        logger.info("Model deployment completed successfully", model_id=args.model_id)

    except Exception as e:
        logger.error(f"Fatal error: {e}", model_id=getattr(args, "model_id", None))
        sys.exit(1)


if __name__ == "__main__":
    main()
