"""
Constants and configuration values for the Global-Classifier project.
"""

# MLflow connection settings
MLFLOW_TRACKING_URI = "http://localhost:5000"
MLFLOW_USERNAME = "mlflowadmin"
MLFLOW_PASSWORD = "null"

# Experiment settings
DEFAULT_EXPERIMENT_NAME = "test_experiment"

# Artifact settings
ARTIFACT_PATH = "mlflow_artifacts/test_artifacts.txt"

# Run configuration
RUN_NAME_FORMAT = "test_run_%Y%m%d_%H%M%S"

# Parameter names
PARAM_TEST = "test_param"
PARAM_TEST_VALUE = "test_value"
PARAM_RANDOM_INTEGER = "random_integer"

# Metric names
METRIC_ACCURACY = "accuracy"
METRIC_ACCURACY_MIN = 0.7
METRIC_ACCURACY_MAX = 0.99
METRIC_LOSS = "loss"
METRIC_LOSS_MIN = 0.01
METRIC_LOSS_MAX = 0.3

# Messages
MSG_ARTIFACT_CONTENT = "This is a test artifact created at {}"
MSG_SUCCESS = "\nTest completed successfully! Check the MLflow UI at {}"

# Logging settings
LOGS_DIR = "logs"
LOG_FILE = "test_mlflow_connection.log"
