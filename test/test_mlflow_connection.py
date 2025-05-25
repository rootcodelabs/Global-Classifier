"""
Test script to verify MLflow connection and functionality.
"""

import sys
import os
import random
import mlflow
import traceback
from datetime import datetime
from loguru import logger

# Add the parent directory to sys.path to import constants
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (
    MLFLOW_TRACKING_URI,
    MLFLOW_USERNAME,
    MLFLOW_PASSWORD,
    DEFAULT_EXPERIMENT_NAME,
    ARTIFACT_PATH,
    RUN_NAME_FORMAT,
    PARAM_TEST,
    PARAM_TEST_VALUE,
    PARAM_RANDOM_INTEGER,
    METRIC_ACCURACY,
    METRIC_ACCURACY_MIN,
    METRIC_ACCURACY_MAX,
    METRIC_LOSS,
    METRIC_LOSS_MIN,
    METRIC_LOSS_MAX,
    MSG_ARTIFACT_CONTENT,
    MSG_SUCCESS,
    LOGS_DIR,
    LOG_FILE,
)

# Configure Loguru
log_file = os.path.join(os.path.dirname(__file__), LOGS_DIR, LOG_FILE)
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Remove default handler and add custom handlers
logger.remove()
# Add console handler
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
# Add file handler with rotation
logger.add(
    log_file,
    rotation="10 MB",  # Rotate file when it reaches 10MB
    retention="1 month",  # Keep logs for 1 month
    compression="zip",  # Compress rotated logs
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

logger.info("Starting MLflow connection test...")

try:
    logger.info("Setting tracking URI...")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    logger.info("Setting environment variables...")
    os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_USERNAME
    os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_PASSWORD

    # Test basic connectivity
    logger.info("Testing connection by listing experiments...")
    experiments = mlflow.search_experiments()
    logger.info(f"Found {len(experiments)} experiments")

    # Create or get experiment
    experiment_name = DEFAULT_EXPERIMENT_NAME
    logger.info(f"Creating/getting experiment '{experiment_name}'...")
    try:
        experiment_id = mlflow.create_experiment(experiment_name)
        logger.success(f"Created new experiment with ID: {experiment_id}")
    except Exception as e:
        logger.warning(f"Could not create experiment: {str(e)}")
        logger.info("Trying to retrieve existing experiment...")
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            experiment_id = experiment.experiment_id
            logger.info(f"Using existing experiment with ID: {experiment_id}")
        else:
            logger.error("ERROR: Could not create or find experiment")
            sys.exit(1)

    logger.info(f"Setting active experiment to {experiment_name}...")
    mlflow.set_experiment(experiment_name)

    # Start a run
    run_name = datetime.now().strftime(RUN_NAME_FORMAT)
    logger.info(f"Starting a new run with name: {run_name}...")
    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id
        logger.info(f"Started run with ID: {run_id}")

        # Log parameters
        logger.info("Logging parameters...")
        mlflow.log_param(PARAM_TEST, PARAM_TEST_VALUE)
        mlflow.log_param(PARAM_RANDOM_INTEGER, random.randint(1, 100))

        # Log metrics
        logger.info("Logging metrics...")
        mlflow.log_metric(
            METRIC_ACCURACY, random.uniform(METRIC_ACCURACY_MIN, METRIC_ACCURACY_MAX)
        )
        mlflow.log_metric(METRIC_LOSS, random.uniform(METRIC_LOSS_MIN, METRIC_LOSS_MAX))

        # Create and log an artifact
        logger.info("Creating artifact...")
        # Ensure the directory exists
        artifact_dir = os.path.dirname(ARTIFACT_PATH)
        if artifact_dir and not os.path.exists(artifact_dir):
            logger.info(f"Creating directory for artifact: {artifact_dir}")
            os.makedirs(artifact_dir, exist_ok=True)

        with open(ARTIFACT_PATH, "w") as f:
            f.write(MSG_ARTIFACT_CONTENT.format(datetime.now().isoformat()))

        logger.info(f"Logging artifact: {ARTIFACT_PATH}")
        mlflow.log_artifact(ARTIFACT_PATH)

        logger.success("Successfully logged parameters, metrics, and artifacts")

    logger.success(MSG_SUCCESS.format(MLFLOW_TRACKING_URI))
    logger.info(f"Experiment: {experiment_name}, Run ID: {run_id}")

except Exception as e:
    logger.error(f"An unexpected error occurred: {type(e).__name__}: {str(e)}")
    logger.error(traceback.format_exc())
