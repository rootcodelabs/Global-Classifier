"""
Test script to verify MLflow connection and functionality.
"""
import sys
import os
import random
import mlflow
import traceback
from datetime import datetime

# Add the parent directory to sys.path to import constants
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (
    MLFLOW_TRACKING_URI, MLFLOW_USERNAME, MLFLOW_PASSWORD,
    DEFAULT_EXPERIMENT_NAME, ARTIFACT_PATH, RUN_NAME_FORMAT,
    PARAM_TEST, PARAM_TEST_VALUE, PARAM_RANDOM_INTEGER,
    METRIC_ACCURACY, METRIC_ACCURACY_MIN, METRIC_ACCURACY_MAX,
    METRIC_LOSS, METRIC_LOSS_MIN, METRIC_LOSS_MAX,
    MSG_ARTIFACT_CONTENT, MSG_SUCCESS
)

print("Starting MLflow connection test...")

try:
    print("Setting tracking URI...")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    
    print("Setting environment variables...")
    os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_USERNAME
    os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_PASSWORD
    
    # Test basic connectivity
    print("Testing connection by listing experiments...")
    experiments = mlflow.search_experiments()
    print(f"Found {len(experiments)} experiments")
    
    # Create or get experiment
    experiment_name = DEFAULT_EXPERIMENT_NAME
    print(f"Creating/getting experiment '{experiment_name}'...")
    try:
        experiment_id = mlflow.create_experiment(experiment_name)
        print(f"Created new experiment with ID: {experiment_id}")
    except Exception as e:
        print(f"Could not create experiment: {str(e)}")
        print("Trying to retrieve existing experiment...")
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            experiment_id = experiment.experiment_id
            print(f"Using existing experiment with ID: {experiment_id}")
        else:
            print("ERROR: Could not create or find experiment")
            sys.exit(1)
    
    print(f"Setting active experiment to {experiment_name}...")
    mlflow.set_experiment(experiment_name)
    
    # Start a run
    run_name = datetime.now().strftime(RUN_NAME_FORMAT)
    print(f"Starting a new run with name: {run_name}...")
    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id
        print(f"Started run with ID: {run_id}")
        
        # Log parameters
        print("Logging parameters...")
        mlflow.log_param(PARAM_TEST, PARAM_TEST_VALUE)
        mlflow.log_param(PARAM_RANDOM_INTEGER, random.randint(1, 100))
        
        # Log metrics
        print("Logging metrics...")
        mlflow.log_metric(METRIC_ACCURACY, random.uniform(METRIC_ACCURACY_MIN, METRIC_ACCURACY_MAX))
        mlflow.log_metric(METRIC_LOSS, random.uniform(METRIC_LOSS_MIN, METRIC_LOSS_MAX))
        
        # Create and log an artifact
        print("Creating artifact...")
        with open(ARTIFACT_PATH, "w") as f:
            f.write(MSG_ARTIFACT_CONTENT.format(datetime.now().isoformat()))
        
        print(f"Logging artifact: {ARTIFACT_PATH}")
        mlflow.log_artifact(ARTIFACT_PATH)
        
        print("Successfully logged parameters, metrics, and artifacts")
    
    print(MSG_SUCCESS.format(MLFLOW_TRACKING_URI))
    print(f"Experiment: {experiment_name}, Run ID: {run_id}")
    
except Exception as e:
    print(f"ERROR: An unexpected error occurred: {type(e).__name__}: {str(e)}")
    traceback.print_exc()